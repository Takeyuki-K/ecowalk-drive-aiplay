"""Adapted from experiment 11: configurable font with portable fallback; rendering only."""
import math,io
from PIL import Image,ImageDraw,ImageFont
FONT=None

def font(size):
 for path in (FONT, '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
  if path:
   try:return ImageFont.truetype(path,size)
   except OSError:
    if path==FONT:raise
 return ImageFont.load_default(size=size)


def grade(r):
 if r['outcome']!='finished':return 'D'
 thresholds=[1700,1500,1200,900] if r['stage']==3 else [2000,1800,1500,1000]
 i=next((i for i,t in enumerate(thresholds) if r['score']>=t),4)
 return ['SS','S','A','B','C','D'][min(5,i+int(r['collisions']>0))]

def map_image(course,pose,path=None,target=None,size=(1600,280)):
 im=Image.new('RGB',size,'#08171d');d=ImageDraw.Draw(im);W,H=size;b=course['bounds'];scale=min((W-80)/(b[1]-b[0]+1),(H-60)/(b[3]-b[2]+1));cx=(b[0]+b[1])/2;cy=(b[2]+b[3])/2
 def pt(p):return (W/2+(p[0]-cx)*scale,H/2-(p[1]-cy)*scale)
 def poly(ps,color):d.polygon([pt(p) for p in ps],fill=color)
 def box(x,y,hx,hy,col):poly([[x-hx,y-hy],[x+hx,y-hy],[x+hx,y+hy],[x-hx,y+hy]],col)
 if course.get('corridor_half_width'):
  h=course['corridor_half_width'];poly([[x,y+h] for x,y in course['centerline']]+[[x,y-h] for x,y in reversed(course['centerline'])],'#25443f')
 else:box(cx,cy,(b[1]-b[0])/2,(b[3]-b[2])/2,'#25443f')
 d.line([pt(p) for p in course['centerline']],fill='#607570',width=1)
 for x,y,xx,yy,w,*_ in course['walls']:d.line([pt([x,y]),pt([xx,yy])],fill='#9ab0b8',width=max(2,round(w*scale)))
 for a in course['obstacles']:box(*a,'#e79863')
 box(*course['goal'],*course['goal_half_size'],'#91f5c0')
 if path:
  d.line([pt(p) for p in path],fill='#80bfff',width=2)
  for p in path:
   x,y=pt(p);d.ellipse((x-2,y-2,x+2,y+2),fill='white')
 if target:
  x,y=pt(target);d.ellipse((x-6,y-6,x+6,y+6),outline='#ff66cc',width=3)
 x,y=pt([pose['x'],pose['y']]);yaw=pose['yaw'];vs=[(12,0),(-7,6),(-4,0),(-7,-6)];d.polygon([(x+a*math.cos(yaw)-bb*math.sin(yaw),y-a*math.sin(yaw)-bb*math.cos(yaw)) for a,bb in vs],fill='#ffd166')
 d.text((15,8),'STANDARD COURSE DATA + TRUE POSE | blue: selected path | pink: next tracking target',font=font(16),fill='white');return im

def compose(raw,s):
 im=Image.new('RGB',(1600,1000),'#08131d');im.paste(Image.open(io.BytesIO(raw)).convert('RGB'),(0,0));sim=s['sim'];r=s['result'];nav=s.get('navigation')or{};route=s.get('route')or{};cmd=s['command'];cam=s['camera'];d=ImageDraw.Draw(im);large=font(20);small=font(16)
 texts=[s['name'],f"sim {r['elapsed_s']:.2f} s",r['outcome'].upper(),f"contacts {r['collisions']}",f"{r['energy_wh']:.3f} Wh",f"avg {r['average_power_w']:.1f} W",f"mode {sim['mode']}",f"v {cmd['v']:.3f} m/s",f"w {cmd['w']:+.3f} rad/s",f"measured v {sim['v_meas']:.3f}",f"X {sim['x']:.3f} Y {sim['y']:.3f}",f"yaw {math.degrees(sim['yaw']):+.1f} deg",f"camera {cam['yaw']:+.0f}/{cam['pitch']:+.0f}",f"plan {route.get('id','none')}",nav.get('reason','observe')]
 texts.insert(3, ('ランク 未確定' if r['outcome']=='playing' else '確定ランク '+grade(r)))
 texts.insert(4, ('score 未確定' if r['outcome']=='playing' else f"score {r['score']:.2f}"))
 for i,t in enumerate(texts):d.text((1290,12+i*31),t,font=large,fill='#91f5c0' if i==2 and t=='FINISHED' else 'white')
 import textwrap
 for i,t in enumerate(textwrap.wrap(s.get('objective',''),width=30)[:5]):d.text((1290,575+i*23),t,font=small,fill='#a9d6ff')
 d.rectangle((0,0,1280,25),fill='#08131d');d.text((10,3),f"LIVE FIRST PERSON | capture {s['frame']} | map and pose: simulation ground truth",font=small,fill='white');im.paste(map_image(s['course'],sim,route.get('points'),nav.get('target')),(0,720));return im
