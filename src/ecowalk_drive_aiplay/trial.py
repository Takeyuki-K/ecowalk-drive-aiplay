"""Fixed spatial plan application without a model call or command replay."""
import json
import time
from .config import DATA
from .game_client import Client
from .recording import write_json

def expand(parameters,course):
    p=json.loads(json.dumps(parameters))
    if p['points']=='centerline': p['points']=[q for q in course['centerline'] if 0<=q[0]<=28]
    if isinstance(p['points'],dict):
        spec=p['points']; p['points']=[[x,y*spec['amplitude']] for x,y in course['centerline'] if 0<=x<=28]
        if 'goal_x' in spec: p['points']=[q for q in p['points'] if q[0]<spec['goal_x']]+[[spec['goal_x'],0]]
    return p

def run_trial(session,cfg,stage,index):
    client=Client(cfg['controller_url'],cfg['startup_timeout']+5)
    name=f's{stage}_final{index}'
    template=json.loads((DATA/'configs/experiment11'/f'{name}.json').read_text())
    requested=session/f'{name}.requested.json'
    if requested.exists(): raise ValueError('trial already attempted: create a new session')
    write_json(requested,template)
    try:
        client.request('/start',dict(stage=stage,name=name))
        deadline=time.monotonic()+cfg['image_timeout']
        while True:
            s=client.request('/snap',{})
            if s.get('image_id'): break
            if time.monotonic()>deadline or not s.get('active'): raise TimeoutError('initial image unavailable')
            time.sleep(.2)
        expected=json.loads((DATA/'reference/experiment11/game-metadata.json').read_text())[str(stage)]
        if s['course']!=expected['course']: raise ValueError('course differs from experiment 11')
        p=expand(template['parameters'],s['course'])
        reference=json.loads((DATA/'reference/experiment11/expanded-routes'/f's{stage}_final1_executed.json').read_text())
        if p['points']!=reference['executed_parameters']['points']: raise ValueError('expanded route mismatch')
        p.update(seen=s['image_id'],note=template['hypothesis'],lease=170,
                 image_use='automated_reference',model_identity='none: fixed reproduction runner')
        write_json(session/f'{name}.resolved.json',dict(parameters=p,plan_application_wall=time.time()))
        client.request('/route',p)
        deadline=time.monotonic()+cfg['trial_timeout']
        while True:
            time.sleep(1)
            s=client.request('/snap',{})
            if not s.get('active'): raise RuntimeError('controller ended trial; inspect saved result')
            if s['state']['result']['outcome']!='playing': break
            if time.monotonic()>deadline: raise TimeoutError('trial timeout')
            if s.get('last_stop') and s['last_stop']['reason'] not in ('goal_neutral','terminal'):
                raise RuntimeError('stopped: '+s['last_stop']['reason'])
        time.sleep(2)
        record=client.request('/end',{})
        result=record['result'] or {}
        if (result.get('outcome')!='finished' or result.get('collisions')!=0 or record['fall_events']
                or not record['stop']['acknowledged'] or record['error']):
            raise RuntimeError('trial did not satisfy finish/collision/fall/stop requirements')
        return record
    except (Exception, KeyboardInterrupt) as e:
        write_json(session/f'{name}.failure.json',dict(error=str(e) or type(e).__name__,wall=time.time()))
        try: client.request('/stop',{}); client.request('/end',{})
        except Exception: pass
        raise
