import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from .config import load, DATA
from .game_client import Client
from .provenance import environment, external, sha
from .recording import create_session, write_json

EXPECTED={'game':'1a4e9e747d8c71e5200c7badf91944c090a6883d','public':'04b1c0fded94dcde76411e6bd9d914a56d41102a','teleop':'a5ea3dbf4f97501c18ff090f86ff4cd413f6aaea'}

def launch(session,cfg,args):
    from .server import Controller, serve
    from . import display
    if cfg['font']: display.FONT=cfg['font']
    # Check font before launching physics.
    resolved_font=display.font(16)
    font_path=getattr(resolved_font,'path',None)
    game=None; game_log=None
    with (session/'server.started').open('x') as f: f.write(str(os.getpid()))
    manifest=environment()|dict(runtime=cfg,source_sha256={str(p.relative_to(Path(__file__).parent)):sha(p) for p in Path(__file__).parent.rglob('*.py')})
    if not args.game_root or not args.game_python: raise ValueError('serve requires --game-root and --game-python')
    root=Path(args.game_root).expanduser().resolve(); python=Path(args.game_python).expanduser().absolute()
    manifest['font']=dict(path=font_path if isinstance(font_path,str) else 'Pillow built-in',sha256=sha(font_path) if isinstance(font_path,str) else None)
    manifest['external']=external(root)
    for key,value in manifest['external'].items():
        if value['commit']!=EXPECTED[key] or value['status']:
            raise ValueError(f'{key}: require clean experiment 11 commit {EXPECTED[key]}')
    write_json(session/'manifest.json',manifest)
    # Refuse occupied ports rather than attaching to an unrelated game's output.
    for key in ('game_url','controller_url'):
        with socket.socket() as sock: sock.bind(('127.0.0.1',urlparse(cfg[key]).port))
    env=os.environ|dict(MUJOCO_GL='egl',PYTHONDONTWRITEBYTECODE='1')
    cmd=[str(python),'-c','from k1_ecowalk_game.app import main; main()','--ecowalk-root',str(root/'vendor/k1-mp-ecowalk-public'),
         '--teleop-root',str(root/'vendor/k1-mp-ecowalk-teleop'),'--render-fps','30',
         '--port',str(urlparse(cfg['game_url']).port),'--output',str(session/'game-runs')]
    write_json(session/'launch.json',dict(argv=cmd,environment={'MUJOCO_GL':'egl','PYTHONDONTWRITEBYTECODE':'1'}))
    probe="import json,platform,sys,importlib.metadata; print(json.dumps(dict(python=sys.version,platform=platform.platform(),dependencies=[dict(name=d.metadata['Name'],version=d.version) for d in importlib.metadata.distributions()])))"
    info=json.loads(subprocess.check_output([str(python),'-c',probe],cwd=root,env=env,text=True))
    write_json(session/'environment-game.json',info)
    try:
        game_log=(session/'logs/game.log').open('w')
        game=subprocess.Popen(cmd,cwd=root,env=env,stdout=game_log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+cfg['startup_timeout']; client=Client(cfg['game_url'],cfg['request_timeout'])
        while True:
            if game.poll() is not None: raise RuntimeError('game process exited: see logs/game.log')
            try: client.request('/status'); break
            except Exception:
                if time.monotonic()>deadline: raise TimeoutError('game startup timeout')
                time.sleep(.2)
        print(json.dumps(dict(session=str(session),controller_url=cfg['controller_url'],game_url=cfg['game_url'])),flush=True)
        serve(Controller(session,cfg))
    finally:
        if game is not None and game.poll() is None:
            try: Client(cfg['game_url']).request('/command',dict(v=0,w=0,brake=False))
            except Exception: pass
            game.terminate()
            try: game.wait(timeout=10)
            except subprocess.TimeoutExpired: game.kill(); game.wait(timeout=5)
        if game_log: game_log.close()
        write_json(session/'external-after.json',external(root))

def main(argv=None):
    p=argparse.ArgumentParser(description='EcoWalk external controller (local HTTP only)')
    subs=p.add_subparsers(dest='command',required=True)
    subs.add_parser('resources',help='show bundled docs, prompts, configs and references')
    init=subs.add_parser('init'); init.add_argument('--output',required=True); init.add_argument('--config',type=Path)
    for name in ('serve','reproduce','api','report','video'):
        sp=subs.add_parser(name); sp.add_argument('--session',required=True,type=Path)
        if name=='serve':
            sp.add_argument('--game-root'); sp.add_argument('--game-python')
        elif name=='video':
            sp.add_argument('--trial',required=True); sp.add_argument('--game-root',required=True,type=Path)
            sp.add_argument('--ffmpeg',required=True,type=Path); sp.add_argument('--output',type=Path)
            sp.add_argument('--action-only',action='store_true')
        elif name=='reproduce':
            sp.add_argument('--stages',type=int,nargs='+',choices=(1,2,3),default=[1,2,3]); sp.add_argument('--repeats',type=int,choices=(1,2,3),default=3)
        elif name=='api':
            sp.add_argument('action',choices=('start','snap','route','observe','camera','stop','end','shutdown'))
            sp.add_argument('--json',default='{}'); sp.add_argument('--file',type=Path); sp.add_argument('--brief',action='store_true')
    args=p.parse_args(argv)
    if args.command=='resources': print(DATA); return 0
    if args.command=='init':
        config=json.loads(args.config.read_text()) if args.config else {}
        session=create_session(args.output,config); load(session); print(session); return 0
    session=args.session.expanduser().resolve(); cfg=load(session)
    if args.command=='serve': launch(session,cfg,args)
    elif args.command=='reproduce':
        import signal
        def interrupted(*unused): raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM,interrupted)
        from .batch import run
        return run(session,cfg,args.stages,args.repeats)
    elif args.command=='api':
        b=json.loads(args.file.read_text() if args.file else args.json)
        response=Client(cfg['controller_url'],cfg['startup_timeout']+5).request('/'+args.action,b)
        if args.brief and 'state' in response:
            response={k:v for k,v in response.items() if k in ('active','image_id','source_image','raw_image','navigation','last_stop','active_route','image_received_wall','state_received_wall')} | {'state':{k:v for k,v in response['state'].items() if k in ('sim','result')}}
        print(json.dumps(response,ensure_ascii=False,indent=2))
    elif args.command=='video':
        from .media.render import render_trial
        print(render_trial(session,args.trial,args.game_root,args.ffmpeg,args.output,action_only=args.action_only))
    elif args.command=='report':
        from .analysis.metrics import report
        report(session); print(session/'analysis/comparison.md')
    return 0

if __name__=='__main__': sys.exit(main())
