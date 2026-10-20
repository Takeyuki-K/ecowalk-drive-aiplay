"""Experiment 11 lifecycle/transport adapter. Follower mathematics are unchanged."""
import copy
import hashlib
import json
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .game_client import Client, NEUTRAL
from .navigation import Follower, clearance
from .recording import Journal, write_json
from .validation import number, route_parameters

class Controller:
    def __init__(self, session, config, client=None):
        self.root=Path(session); self.cfg=config; self.game=client or Client(config['game_url'],config['request_timeout'])
        self.journal=Journal(session); self.lock=threading.RLock(); self.done=threading.Event()
        self.active=None; self.generation=0; self.decision_id=0; self.threads=[]
        self.reset()
    def reset(self):
        self.route=None; self.state={}; self.latest={}; self.frames={}; self.frame=0
        self.cmd=NEUTRAL.copy(); self.navigation={}; self.selected_points=None
        self.objective='initial map and first-person observation'
        self.camera=dict(mode='first',yaw=0,pitch=-16)
        self.last_image=0; self.previous_tick=None; self.prev_collision=0; self.prev_sim=None
        self.last_sim_change=time.monotonic(); self.started=time.monotonic(); self.start_wall=time.time()
        self.last_stop=None; self.fall_count=0; self.was_fallen=False; self.transport_error_since=None
    def log(self, file, **b):
        self.journal.log(file,name=self.active,**b)
    def neutral(self, reason):
        # Caller holds lock: no stale nonzero command can be sent after this ACK.
        self.route=None; self.cmd=NEUTRAL.copy(); self.navigation={'reason':reason}
        started=time.time()
        try:
            self.game.request('/command',NEUTRAL)
            record=dict(reason=reason,acknowledged=True,command_wall=started,ack_wall=time.time())
        except Exception as e:
            record=dict(reason=reason,acknowledged=False,command_wall=started,error=str(e))
        self.last_stop=record
        self.log('events.jsonl',kind='neutral',**record)
        return record
    def start(self,b):
        stage=b.get('stage'); name=b.get('name')
        if type(stage) is not int or stage not in (1,2,3): raise ValueError('invalid stage')
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name): raise ValueError('invalid trial name')
        with self.lock:
            if self.active is not None: raise ValueError('end previous trial first')
            folder=self.root/'observations'/name
            folder.mkdir(exist_ok=False)
            self.reset(); self.generation+=1; self.active=name
            try:
                self.game.request('/start',{'stage':stage},timeout=self.cfg['startup_timeout'])
                self.game.request('/camera',self.camera)
                self.started=time.monotonic()
                self.log('events.jsonl',kind='start',stage=stage)
            except Exception:
                self.neutral('start_error')
                try: self.game.request('/abort',{})
                except Exception: pass
                self.log('events.jsonl',kind='start_failed',stage=stage)
                self.active=None
                raise
        # Retain the experiment's initial one-second observation window.
        self.done.wait(1)
        return self.snapshot()
    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.latest | dict(active=self.active,state=self.state,
                navigation=self.navigation,last_stop=self.last_stop,
                active_route=None if self.route is None else dict(id=self.route.id,progress=self.route.progress,total=self.route.total)))
    def decision(self,b,kind):
        seen=b.get('seen'); note=b.get('note')
        if not isinstance(note,str) or not note.strip() or len(note)>10000: raise ValueError('note required')
        if not isinstance(seen,str) or seen not in self.frames: raise ValueError('current trial image ID required')
        use=b.get('image_use','model_viewed')
        if use not in ('model_viewed','automated_reference'): raise ValueError('invalid image_use')
        f=self.frames[seen]
        self.decision_id+=1
        self.log('decisions.jsonl',id=self.decision_id,kind=kind,seen=seen,
            image_use=use,source_image=f['source_image'],image_sha256=f['image_sha256'],
            capture_wall=f['wall'],reference_sim_t=f['sim']['t'],
            image_to_decision_s=time.time()-f['wall'],reason=note,
            parameters={k:v for k,v in b.items() if k not in ('note','seen')},
            model_identity=b.get('model_identity','not independently verified'))
        return self.decision_id
    def apply_route(self,b):
        with self.lock:
            if not self.active or not self.state: raise ValueError('start and observe first')
            if self.state['result']['outcome']!='playing': raise ValueError('game is terminal')
            if time.monotonic()-self.state['received_monotonic']>self.cfg['state_watchdog']:
                raise ValueError('stale state')
            if not self.last_image or time.monotonic()-self.last_image>self.cfg['image_watchdog']:
                raise ValueError('stale image')
            current=None if self.route is None else self.route.id
            if b.get('expected_route_id',current)!=current: raise ValueError('route changed since observation')
            params,minimum=route_parameters(b,self.state['course'])
            # Validate observation and complete candidate before affecting the current route.
            if b.get('seen') not in self.frames or not isinstance(b.get('note'),str) or not b['note'].strip():
                raise ValueError('current trial image and note required')
            ident=self.decision(b,'route')
            follower=Follower(wall=time.monotonic(),ident=ident,**params)
            if self.route is not None:
                if not self.neutral('route_replaced')['acknowledged']:
                    raise ConnectionError('replacement stopped: neutral not acknowledged')
            self.route=follower; self.selected_points=params['points']; self.objective=b['note']
            self.log('events.jsonl',kind='route_active',decision_id=ident,map_minimum_clearance=minimum,parameters=params)
            return self.snapshot()
    def end(self,reason='trial_end'):
        with self.lock:
            if not self.active: raise ValueError('no active trial')
            stop=self.neutral(reason)
            result=None; error=None
            try:
                s=self.game.request('/status')
                if s['result']['outcome']=='playing':
                    self.game.request('/abort',{})
                    s=self.game.request('/status')
                result=s['result']
                directory=Path(s['directory']).resolve()
                if directory.parent != (self.root/'game-runs').resolve():
                    raise ValueError('game output is outside this session')
                record=dict(result=result,run_id=directory.name)
            except Exception as e:
                error=str(e); record=dict(result=result,run_id=None)
            record.update(name=self.active,start_wall=self.start_wall,end_wall=time.time(),
                          recorded_frames=self.frame,stop=stop,error=error,fall_events=self.fall_count)
            self.log('results.jsonl',**{k:v for k,v in record.items() if k!='name'})
            write_json(self.root/'observations'/self.active/'result.json',record)
            self.active=None; self.generation+=1
            return record
    def tick(self):
        with self.lock:
            if not self.active: return
            t=time.monotonic(); begin=time.time()
            try:
                s=self.game.request('/status'); received=time.time(); now=time.monotonic()
                sim=s['sim']; result=s['result']
                if Path(s['directory']).resolve().parent != (self.root/'game-runs').resolve():
                    raise ValueError('game --output must equal session/game-runs')
                for k in ('t','x','y','yaw','w_meas'): number(sim[k],-1e9,1e9,k)
                if self.prev_sim is None or sim['t']!=self.prev_sim: self.last_sim_change=now
                self.state=s|dict(received_wall=received,received_monotonic=now,status_request_wall=begin)
                self.log('localization.jsonl',request_wall=begin,received_wall=received,sim=sim,result=result,real_time_factor=s['real_time_factor'])
                fallen=bool(sim.get('fallen')); self.fall_count+=int(fallen and not self.was_fallen); self.was_fallen=fallen
                rt=self.route; v=self.cmd['v']; w=self.cmd['w']; ident=None if rt is None else rt.id
                dt=.05 if self.previous_tick is None else max(.01,min(.15,t-self.previous_tick))
                nav=self.navigation
                if rt:
                    reason=None
                    if result['outcome']!='playing': reason='terminal'
                    elif t>rt.deadline: reason='route_deadline'
                    elif not self.last_image or now-self.last_image>self.cfg['image_watchdog']: reason='image_watchdog'
                    elif now-self.last_sim_change>self.cfg['state_watchdog']: reason='state_watchdog'
                    elif fallen: reason='fallen'
                    elif self.prev_sim is not None and sim['t']>=self.prev_sim and result['collisions']>self.prev_collision: reason='collision_guard'
                    if reason:
                        self.neutral(reason); v=w=0; nav=self.navigation
                    else:
                        v,w,nav,finished=rt.update(sim,v,w,dt,t)
                        cl=clearance([sim['x'],sim['y']],s['course']); nav['clearance_m']=cl
                        if cl<.28:
                            self.neutral('clearance_guard'); v=w=0; nav=self.navigation|dict(clearance_m=cl)
                        elif finished:
                            self.neutral(nav['reason'])
                else: v=w=0
                self.cmd=dict(v=v,w=w,brake=False); self.navigation=nav
                sent=time.time(); self.game.request('/command',self.cmd); ack=time.time()
                self.log('controls.jsonl',status_request_wall=begin,status_received_wall=received,
                    command_wall=sent,ack_wall=ack,control_monotonic=t,dt=dt,sim_t=sim['t'],
                    decision_id=ident,command=self.cmd,navigation=nav,mode=sim['mode'],
                    source_frame=self.latest.get('image_id'),source_capture_wall=self.latest.get('wall'),
                    image_age_at_command_s=sent-self.latest.get('wall',sent),pose_to_command_s=sent-received,ack_latency_s=ack-sent)
                self.prev_collision=result['collisions']; self.prev_sim=sim['t']; self.previous_tick=t
                self.transport_error_since=None
                if not self.last_image and now-self.started>self.cfg['image_timeout']:
                    self.end('initial_image_timeout')
                elif now-self.started>self.cfg['trial_timeout']+self.cfg['image_timeout']:
                    self.end('trial_timeout')
            except Exception as e:
                self.neutral('control_exception'); self.log('events.jsonl',kind='control_error',error=str(e))
                if self.transport_error_since is None: self.transport_error_since=time.monotonic()
                if time.monotonic()-self.transport_error_since>self.cfg['state_watchdog']:
                    self.end('communication_timeout')
    def capture(self):
        from .display import compose
        with self.lock:
            if not self.active or not self.state: return
            a=self.active; gen=self.generation; i=self.frame
            s=copy.deepcopy(self.state); cc=self.cmd.copy(); nav=copy.deepcopy(self.navigation)
            cam=self.camera.copy(); obj=self.objective; pts=copy.deepcopy(self.selected_points)
            ident=None if self.route is None else self.route.id
        begin=time.time(); raw=self.game.request('/frame.jpg',raw=True); received=time.time(); mono=time.monotonic()
        folder=self.root/'observations'/a
        z=s|dict(wall=received,image_request_wall=begin,image_received_wall=received,
            state_received_wall=s['received_wall'],state_image_gap_s=received-s['received_wall'],
            frame=i,name=a,image_id=f'{a}:{i:06d}',command=cc,camera=cam,navigation=nav,objective=obj,
            route=dict(id=ident,points=pts),source_image=str(folder/f'{i:06d}.jpg'),
            raw_image=str(folder/f'{i:06d}_pov.jpg'),raw_sha256=hashlib.sha256(raw).hexdigest())
        composed=compose(raw,z)
        with self.lock:
            if gen!=self.generation or a!=self.active: return
            Path(z['raw_image']).write_bytes(raw); composed.save(z['source_image'],quality=86)
            z['image_sha256']=hashlib.sha256(Path(z['source_image']).read_bytes()).hexdigest()
            with (folder/'frames.jsonl').open('a') as f: f.write(json.dumps(z)+'\n')
            self.latest=z; self.frame+=1; self.last_image=mono; self.frames[z['image_id']]=z
    def run_loop(self, fn, period):
        while not self.done.is_set():
            t=time.monotonic()
            try: fn()
            except Exception as e:
                with self.lock: self.log('events.jsonl',kind='record_error',error=str(e))
            self.done.wait(max(.001,period-(time.monotonic()-t)))
    def start_threads(self):
        for fn,period in ((self.tick,self.cfg['period']),(self.capture,self.cfg['frame_period'])):
            t=threading.Thread(target=self.run_loop,args=(fn,period),daemon=True); t.start(); self.threads.append(t)
    def close(self):
        with self.lock:
            if self.active: self.end('shutdown')
            else: self.neutral('shutdown')
            self.done.set()
        for t in self.threads: t.join(timeout=self.cfg['request_timeout']+2)
    def action(self,path,b):
        if path=='/start': return self.start(b)
        if path=='/route': return self.apply_route(b)
        if path=='/snap': return self.snapshot()
        if path=='/end': return self.end()
        if path in ('/stop','/observe','/camera'):
            with self.lock:
                if path=='/stop': self.neutral('upper_requested')
                if b.get('seen'): self.decision(b,path[1:])
                elif path!='/stop': raise ValueError('seen and note required')
                if path=='/camera':
                    cam=self.camera|{k:number(b[k],*limits,k) for k,limits in [('yaw',(-90,90)),('pitch',(-65,45))] if k in b}
                    self.game.request('/camera',cam); self.camera=cam
                return self.snapshot()
        raise ValueError('unknown endpoint')

def serve(controller):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            self.reply(200,controller.snapshot()) if self.path=='/status' else self.reply(404,dict(error='unknown endpoint'))
        def reply(self,status,body):
            data=json.dumps(body,allow_nan=False).encode()
            self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers()
            try: self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError): pass
        def do_POST(self):
            try:
                if self.headers.get('Origin') and self.headers['Origin']!='http://'+self.headers.get('Host',''):
                    self.reply(403,dict(error='origin rejected')); return
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=131072: raise ValueError('invalid body size')
                self.connection.settimeout(3)
                b=json.loads(self.rfile.read(n),parse_constant=lambda s: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
                if not isinstance(b,dict): raise ValueError('object required')
                if self.path=='/shutdown':
                    controller.close(); self.reply(200,dict(stopped=True))
                    threading.Thread(target=self.server.shutdown,daemon=True).start(); return
                self.reply(200,controller.action(self.path,b))
            except Exception as e:
                controller.journal.log('events.jsonl',kind='handler_error',endpoint=self.path,error=str(e))
                self.reply(400,dict(error=str(e)))
    port=urlparse(controller.cfg['controller_url']).port
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    def shutdown(*args):
        threading.Thread(target=server.shutdown,daemon=True).start()
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,shutdown)
    controller.start_threads()
    try: server.serve_forever(poll_interval=.1)
    finally: controller.close(); server.server_close()
