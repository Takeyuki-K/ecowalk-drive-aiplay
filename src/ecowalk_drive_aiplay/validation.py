"""Reject invalid spatial plans before changing the active follower."""
import math
from .navigation import clearance, segments

def number(v, lo, hi, name):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError(f'invalid {name}')
    return v

def route_parameters(b, course):
    allowed={'points','speed','lookahead','corridor','lease','tuning','seen','note','image_use','model_identity','expected_route_id'}
    if set(b)-allowed: raise ValueError('unknown route fields')
    points=b.get('points')
    if not isinstance(points,list) or not 2 <= len(points) <= 2048: raise ValueError('2..2048 points required')
    bounds=course['bounds']
    for p in points:
        if not isinstance(p,list) or len(p)!=2: raise ValueError('points must be [x,y]')
        number(p[0],bounds[0],bounds[1],'x'); number(p[1],bounds[2],bounds[3],'y')
    if not segments(points): raise ValueError('zero length route')
    if sum(math.dist(a,z) for a,z in zip(points,points[1:]))>500: raise ValueError('route too long')
    p=dict(points=points,speed=number(b.get('speed'),.001,1.5,'speed'),
           lookahead=number(b.get('lookahead',1),.05,5,'lookahead'),
           corridor=number(b.get('corridor',.7),.01,5,'corridor'),
           lease=number(b.get('lease',120),.001,180,'lease'))
    tuning=b.get('tuning',{})
    limits={'corner_floor':(.01,1),'corner_divisor':(.01,1000),'slow_distance':(.01,20),'end_base':(0,1.5),'end_gain':(0,5)}
    if not isinstance(tuning,dict) or set(tuning)-set(limits): raise ValueError('invalid tuning keys')
    for k,v in tuning.items(): number(v,*limits[k],k)
    p['tuning']=tuning
    minimum=1000
    for a,z in zip(points,points[1:]):
        n=max(2,int(math.dist(a,z)/.05)+1)
        for i in range(n):
            minimum=min(minimum,clearance([a[k]+(z[k]-a[k])*i/(n-1) for k in (0,1)],course))
    if minimum<.30: raise ValueError(f'route clearance {minimum} < 0.30m')
    return p,minimum
