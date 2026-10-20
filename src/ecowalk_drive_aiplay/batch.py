import json
from .trial import run_trial
from .analysis.metrics import report

def run(session,config,stages=(1,2,3),repeats=3):
    failures=[]
    for stage in stages:
        for index in range(1,repeats+1):
            try:
                r=run_trial(session,config,stage,index)
                print(json.dumps(r,ensure_ascii=False),flush=True)
            except Exception as e:
                failures.append(dict(stage=stage,index=index,error=str(e)))
                print(json.dumps(failures[-1],ensure_ascii=False),flush=True)
    report(session)
    return 1 if failures else 0
