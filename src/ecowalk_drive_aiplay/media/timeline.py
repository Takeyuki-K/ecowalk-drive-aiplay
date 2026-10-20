"""30 Hz display sampling of the original full-physics state log."""
import bisect
import math

def validate_times(rows, max_gap=.041):
    if len(rows)<2: raise ValueError('at least two states required')
    times=[r['t'] for r in rows]
    if not all(isinstance(t,(float,int)) and math.isfinite(t) for t in times):
        raise ValueError('nonfinite state timestamp')
    gaps=[b-a for a,b in zip(times,times[1:])]
    if min(gaps)<=0: raise ValueError('state timestamps must strictly increase')
    if max(gaps)>max_gap: raise ValueError(f'state gap {max(gaps):.6f}s exceeds {max_gap}s; do not invent missing motion')
    return times

def sample_times(times,fps):
    if not isinstance(fps,int) or not 1<=fps<=60: raise ValueError('fps must be an integer 1..60')
    n=math.floor((times[-1]-times[0])*fps+1e-7)+1
    for index in range(n):
        t=min(times[-1],times[0]+index/fps)
        lower=max(0,bisect.bisect_right(times,t)-1); upper=min(lower+1,len(times)-1)
        alpha=0 if lower==upper else (t-times[lower])/(times[upper]-times[lower])
        yield index,t,lower,upper,alpha

def interpolate_state(mj,model,a,b,alpha):
    """Interpolate display qpos on MuJoCo's configuration manifold, not dynamics."""
    import numpy as np
    a=np.asarray(a,dtype=float); b=np.asarray(b,dtype=float)
    if a.shape!=b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('invalid full physics state')
    expected=mj.mj_stateSize(model,mj.mjtState.mjSTATE_FULLPHYSICS)
    if len(a)!=expected: raise ValueError('FULLPHYSICS state dimension mismatch')
    out=a+(b-a)*alpha
    qa=a[1:1+model.nq]; qb=b[1:1+model.nq]; q=qa.copy()
    velocity=np.empty(model.nv)
    mj.mj_differentiatePos(model,velocity,1.,qa,qb)
    mj.mj_integratePos(model,q,velocity,float(alpha))
    out[1:1+model.nq]=q
    return out

class SimulationFollowCamera:
    """Use the game's existing filter with sim time, independent of render speed."""
    def __init__(self,follow_class):
        self.filter=follow_class(); self.time=0.; self.last=None
    def reset(self): self.filter.reset()
    def follow(self,x,y,yaw):
        self.last=self.filter.follow(x,y,yaw,now=self.time)
        return self.last
