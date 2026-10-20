"""Read-only replay of saved E11 pose/previous-command inputs into both followers.
Loop-entry time was not logged in E11: request time deltas are used identically
for both implementations, not claimed as exact replay of historical commands.
"""
import argparse
import hashlib
import json
from pathlib import Path
from ecowalk_drive_aiplay.navigation import Follower
from ecowalk_drive_aiplay.recording import write_json

def main():
    p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    namespace={}; source=(a.source/'controller/navigation.py').read_bytes(); exec(compile(source,'original-navigation','exec'),namespace)
    loc=[json.loads(x) for x in (a.source/'logs/localization.jsonl').read_text().splitlines()]
    controls=[json.loads(x) for x in (a.source/'logs/controls.jsonl').read_text().splitlines()]
    if len(loc)!=len(controls): raise ValueError('logs do not align')
    followers={}; prev={}; compared=0; mismatches=[]; reasons={}; maximum=0
    for l,c in zip(loc,controls):
        assert l['request_wall']==c['status_request_wall'] and l['sim']['t']==c['sim_t']
        if l['name']!=c['name']:
            assert c['decision_id'] is None  # historical end race: no active follower
            continue
        name=c['name']; wall=c['status_request_wall']; last=prev.get(name)
        prev[name]=c
        if c['decision_id'] is None: continue
        if name not in followers:
            plan=json.loads((a.source/'optimization'/(name.split('/')[-1]+'_executed.json')).read_text())['executed_parameters']
            args=dict(points=plan['points'],speed=plan['speed'],lookahead=plan.get('lookahead',1),corridor=plan.get('corridor',.7),wall=wall,lease=170,ident=c['decision_id'],tuning=plan.get('tuning'))
            followers[name]=(namespace['Follower'](**args),Follower(**args))
        old,new=followers[name]; command=last['command'] if last else dict(v=0,w=0)
        dt=max(.01,min(.15,wall-last['status_request_wall'])) if last else .05
        args=(l['sim'],command['v'],command['w'],dt,wall)
        x=old.update(*args); y=new.update(*args); compared+=1
        reasons[y[2]['reason']]=reasons.get(y[2]['reason'],0)+1
        maximum=max(maximum,abs(x[0]-y[0]),abs(x[1]-y[1]))
        if x!=y or old.__dict__!=new.__dict__: mismatches.append(dict(name=name,sim_t=l['sim']['t']))
    result=dict(trials=len(followers),pose_samples=compared,mismatches=mismatches,max_command_difference=maximum,reasons=reasons,
        original_sha256=hashlib.sha256(source).hexdigest(),
        time_note='Identical inputs to old/new: wall=request timestamp; dt=clipped request delta. E11 exact loop entry timestamp unavailable; not equivalence to historical sent commands.')
    write_json(a.output,result); print(json.dumps(result,indent=2)); return bool(mismatches)
if __name__=='__main__': raise SystemExit(main())
