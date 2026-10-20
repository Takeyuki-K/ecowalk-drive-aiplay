"""World-coordinate adaptation of experiment 07 path follower; no timed route replay."""
import math

def wrap(a):return (a+math.pi)%(2*math.pi)-math.pi
def segments(points):
 out=[];s=0
 for a,b in zip(points,points[1:]):
  n=math.dist(a,b)
  if n>1e-6:out.append((a,b,n,s,s+n));s+=n
 return out

def project(p,segs,lo=0,hi=1e20):
 best=None
 for a,b,n,s,e in segs:
  if e<lo or s>hi:continue
  u=((p[0]-a[0])*(b[0]-a[0])+(p[1]-a[1])*(b[1]-a[1]))/(n*n)
  u=max(max(0,(lo-s)/n),min(min(1,(hi-s)/n),u));q=[a[0]+u*(b[0]-a[0]),a[1]+u*(b[1]-a[1])];d=math.dist(p,q)
  if best is None or d<best[1]:best=(s+u*n,d,q)
 return best

def point_at(segs,t):
 a,b,n,s,e=next((g for g in segs if g[4]>=t),segs[-1]);u=max(0,min(1,(t-s)/n));return [a[0]+u*(b[0]-a[0]),a[1]+u*(b[1]-a[1])]

def clearance(p,course):
 ds=[]
 for x,y,hx,hy in course['obstacles']:ds.append(math.hypot(max(abs(p[0]-x)-hx,0),max(abs(p[1]-y)-hy,0)))
 for x,y,xx,yy,w,*_ in course['walls']:
  n=(xx-x)**2+(yy-y)**2;u=max(0,min(1,((p[0]-x)*(xx-x)+(p[1]-y)*(yy-y))/n));ds.append(math.hypot(p[0]-x-u*(xx-x),p[1]-y-u*(yy-y))-w/2)
 return min(ds) if ds else 1000

class Follower:
 def __init__(self,points,speed,lookahead,corridor,wall,lease,ident,tuning=None):
  self.cfg=tuning or {};self.points=points;self.segs=segments(points);self.total=self.segs[-1][4];self.progress=0;self.speed=speed;self.look=lookahead;self.corridor=corridor;self.deadline=wall+lease;self.id=ident;self.steer=0;self.reverse=None
 def update(self,s,vprev,wprev,dt,wall):
  p=[s['x'],s['y']];proj=project(p,self.segs,self.progress,min(self.total,self.progress+2))
  if proj is None or proj[1]>self.corridor:return 0,0,{'reason':'corridor_violation'},True
  self.progress=max(self.progress,proj[0]);remain=self.total-self.progress;gd=math.dist(p,self.points[-1])
  if remain<.35 and gd<.45:return 0,0,{'reason':'goal_neutral','remaining':remain},True
  look=self.look+vprev*.18-min(.2,abs(wprev)*.25);look=max(.2,look);target=point_at(self.segs,min(self.total,self.progress+look));angle=math.atan2(target[1]-p[1],target[0]-p[0]);error=wrap(angle-s['yaw'])
  ahead=point_at(self.segs,min(self.total,self.progress+look+.65));corner=abs(wrap(math.atan2(ahead[1]-target[1],ahead[0]-target[0])-angle)) if math.dist(ahead,target)>.01 else 0
  steer=math.degrees(error-s['w_meas']*.24);sign=1 if steer>0 else -1
  if self.steer==0:
   if abs(steer)>12:self.steer=sign
  elif sign!=self.steer:
   if abs(steer)>16:
    if self.reverse is None:self.reverse=wall
    if wall-self.reverse>=.25:self.steer=sign;self.reverse=None
   else:self.steer=0;self.reverse=None
  elif abs(steer)<5:self.steer=0;self.reverse=None
  w=max(-.65,min(.65,(steer-self.steer*5)/65)) if self.steer and sign==self.steer else 0
  v=self.speed*max(.14,math.cos(min(math.radians(85),abs(error))))*max(self.cfg.get('corner_floor',.4),1-math.degrees(corner)/self.cfg.get('corner_divisor',150))
  if remain<self.cfg.get('slow_distance',2):v=min(v,self.cfg.get('end_base',.22)+remain*self.cfg.get('end_gain',.38))
  if abs(error)>math.radians(80):v=.04
  # Conservative allowance for tight obstacle courses; limits are model-selected.
  v=vprev+max(-.8*dt,min(.8*dt,v-vprev));w=wprev+max(-1.1*dt,min(1.1*dt,w-wprev))
  return v,w,{'reason':'tracking','progress':self.progress,'remaining':remain,'target':target,'cross_track':proj[1],'heading_error':error,'corner_rad':corner},False
