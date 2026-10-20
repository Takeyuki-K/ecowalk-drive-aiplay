"""Real-game lifecycle smoke test; automatic references, no claim of model vision."""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
from pathlib import Path
from ecowalk_drive_aiplay.config import load
from ecowalk_drive_aiplay.game_client import Client
from ecowalk_drive_aiplay.recording import write_json

p=argparse.ArgumentParser(); p.add_argument('--session',type=Path,required=True); p.add_argument('--game-root',required=True); p.add_argument('--game-python',required=True); a=p.parse_args()
session=a.session.resolve(); cfg=load(session); client=Client(cfg['controller_url'],65)
env=os.environ|dict(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
cmd=[sys.executable,'-m','ecowalk_drive_aiplay.cli','serve','--session',str(session),'--game-root',a.game_root,'--game-python',a.game_python]
checks={}; proc=None
try:
    with (session/'logs/smoke-server.log').open('w') as log:
        proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
    deadline=time.monotonic()+60
    while True:
        if proc.poll() is not None: raise RuntimeError('server exited')
        try: client.request('/snap',{}); break
        except OSError:
            if time.monotonic()>deadline: raise TimeoutError('server startup')
            time.sleep(.2)
    client.request('/start',dict(stage=1,name='api_smoke'))
    deadline=time.monotonic()+15
    while True:
        s=client.request('/snap',{})
        if s.get('image_id'): break
        if time.monotonic()>deadline: raise TimeoutError('image startup')
        time.sleep(.2)
    plan=dict(points=[[0,0],[19.55,0]],speed=1.3,lookahead=1.3,corridor=.8,lease=60,
        seen=s['image_id'],note='Automated API lifecycle check; no claim of model image inspection',image_use='automated_reference')
    write_json(session/'config.requested.json',plan)
    s=client.request('/route',plan); old=s['active_route']['id']; time.sleep(2)
    try: client.request('/route',plan|dict(points=[[0,0],[0,0]]))
    except urllib.error.HTTPError as error:
        assert error.code==400; checks['invalid_route_rejected']=True
    else: raise AssertionError('invalid route accepted')
    s=client.request('/snap',{}); assert s['active_route']['id']==old; checks['invalid_preserves_route']=True
    sim=s['state']['sim']; plan.update(points=[[sim['x'],sim['y']],[19.55,0]],seen=s['image_id'],expected_route_id=old,
        note='Automated replacement from current true pose; neutral ACK required')
    write_json(session/'config.resolved.json',plan)
    s=client.request('/route',plan)
    assert s['active_route']['id']!=old and s['last_stop']['reason']=='route_replaced' and s['last_stop']['acknowledged']
    checks['replacement_neutral_ack']=True
    time.sleep(2); s=client.request('/snap',{})
    decision=dict(seen=s['image_id'],note='Automated camera API check',image_use='automated_reference')
    client.request('/camera',decision|dict(yaw=10,pitch=-20)); client.request('/observe',decision)
    s=client.request('/stop',{}); assert s['last_stop']['acknowledged']; checks['stop_ack']=True
    r=client.request('/end',{}); assert r['result']['outcome']=='aborted' and r['stop']['acknowledged']; checks['intentional_abort_saved']=True
    client.request('/shutdown',{}); proc.wait(timeout=20); assert proc.returncode==0
    checks['shutdown_process_exit']=True
    write_json(session/'analysis/api-smoke.json',dict(checks=checks,pass_all=all(checks.values()),result=r,model_invoked=False))
    print(json.dumps(checks,indent=2))
finally:
    if proc is not None and proc.poll() is None:
        try: client.request('/shutdown',{})
        except Exception: proc.terminate()
        proc.wait(timeout=20)
