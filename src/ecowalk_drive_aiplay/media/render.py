"""Read-only state replay to two 720p H.264 streams; no policy inference/physics steps."""
import argparse
import bisect
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from ..recording import write_json
from ..provenance import sha, external
from .timeline import validate_times,sample_times,interpolate_state,SimulationFollowCamera
from .validate import validate_video

class Encoder:
    def __init__(self,ffmpeg,path,fps):
        self.path=Path(path); self.log=self.path.with_suffix('.encode.log').open('w')
        self.proc=subprocess.Popen([str(ffmpeg),'-hide_banner','-loglevel','error','-n',
            '-f','rawvideo','-pixel_format','rgb24','-video_size','1280x720','-framerate',str(fps),'-i','pipe:0',
            '-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','18',
            '-pix_fmt','yuv420p','-movflags','+faststart',str(path)],stdin=subprocess.PIPE,stderr=self.log)
    def write(self,im): self.proc.stdin.write(im.tobytes())
    def close(self):
        if not self.proc.stdin.closed: self.proc.stdin.close()
        code=self.proc.wait(timeout=60); self.log.close()
        if code: raise RuntimeError(f'encoder failed {code}: {self.path}')

def render_trial(session,name,game_root,ffmpeg,output=None,fps=30,clip_seconds=None,action_only=False):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name): raise ValueError('invalid trial name')
    if fps!=30: raise ValueError('this recording profile requires 30 fps')
    import numpy as np
    from PIL import Image,ImageDraw
    session=Path(session).resolve(); game_root=Path(game_root).resolve(); ffmpeg=Path(ffmpeg).resolve()
    if not ffmpeg.is_file(): raise ValueError('supply an existing FFmpeg executable; no auto installation')
    # No source edits, imports from the user-provided fixed game checkout.
    sys.path.insert(0,str(game_root))
    from k1_ecowalk_game.backend import Backend
    from k1_ecowalk_game.camera import FollowCamera
    expected_external=json.loads((session/'manifest.json').read_text())['external']
    if external(game_root)!=expected_external:
        raise ValueError('game/vendor source differs from recorded session manifest')
    result_path=session/'observations'/name/'result.json'
    record=json.loads(result_path.read_text())
    if not record.get('run_id'): raise ValueError('trial has no finalized game recording')
    run=session/'game-runs'/record['run_id']
    metadata=json.loads((run/'metadata.json').read_text())
    result=json.loads((run/'result.json').read_text())
    if result!=record['result']: raise ValueError('game/controller result mismatch')
    rows=[json.loads(l) for l in (run/'states.jsonl').read_text().splitlines()]
    times=validate_times(rows)
    if clip_seconds is not None and (not math.isfinite(clip_seconds) or clip_seconds<=0): raise ValueError('invalid clip duration')
    frames=[json.loads(l) for l in (session/'observations'/name/'frames.jsonl').read_text().splitlines()]
    frame_times=[f['sim']['t'] for f in frames]
    if any(b<a for a,b in zip(frame_times,frame_times[1:])): raise ValueError('observation sim timestamps regress')
    output=Path(output).resolve() if output else session/'video'/name
    output.mkdir(parents=True,exist_ok=False)
    source_paths=[run/'states.jsonl',run/'metadata.json',run/'result.json',result_path,session/'observations'/name/'frames.jsonl']
    source_hashes={str(p):sha(p) for p in source_paths}
    original_navigation=sha(Path(__file__).parents[1]/'navigation.py')
    encoder_version=subprocess.check_output([str(ffmpeg),'-version'],text=True).splitlines()[0]
    plan=list(sample_times(times,fps))
    moving=next((r['t'] for r in rows if any(r['command'][:2])),None)
    if action_only:
        if moving is None: raise ValueError('no movement state; cannot render an action excerpt')
        plan=[v for v in plan if v[1]>=max(times[0],moving-1)]
    # PTS starts at zero even when an explicit sim-time excerpt is requested.
    plan=[(i,*v[1:]) for i,v in enumerate(plan)]
    if clip_seconds is not None: plan=[v for v in plan if v[1]-plan[0][1]<clip_seconds]
    if len(plan)<3: raise ValueError('at least three display frames required')
    manifest=dict(mode='offline_state_rerender',not_live_observations=True,
        session=str(session),name=name,run_id=record['run_id'],stage=metadata['stage'],outcome=result['outcome'],
        fps=fps,width=1280,height=720,clock='simulation time, not wall time',
        physics_or_policy_stepped=False,interpolation='MuJoCo differentiatePos/integratePos for qpos, linear remaining FULLPHYSICS state',
        source_state_count=len(rows),source_mean_hz=(len(rows)-1)/(times[-1]-times[0]),
        source_max_gap_s=max(b-a for a,b in zip(times,times[1:])),render_frames=len(plan),
        action_only=action_only,source_sim_start=times[0],source_sim_end=times[-1],
        rendered_sim_start=plan[0][1],rendered_sim_end=plan[-1][1],
        source_hashes=source_hashes,original_navigation_sha256=original_navigation,
        ffmpeg_version=encoder_version,ffmpeg_sha256=sha(ffmpeg),
        render_source_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},
        third_camera=dict(distance_m=4,lookat_height_m=.85,elevation_deg=-12,position_tau_s=.30,yaw_tau_s=.45,
            filter_clock='output simulation timestamp',wall_obstacle_alpha='existing game rgba alpha 0.25; unchanged'),
        first_camera='existing game first-person formula; camera angles from preceding observation metadata',
        caveats=['Re-rendered images were not seen by Astra; actual observations remain under observations/',
                 'State interpolation is a display operation, not a new physics trajectory.',
                 'Camera-change timing is approximate at 5 Hz observation resolution; fixed angles avoid this uncertainty.'])
    write_json(output/'render-manifest.json',manifest)
    backend=None; encoders={}; maps={}; first_error=None; start=time.monotonic()
    try:
        backend=Backend(game_root/'vendor/k1-mp-ecowalk-public',game_root/'vendor/k1-mp-ecowalk-teleop',metadata['stage'],metadata['course'])
        filters={view:SimulationFollowCamera(FollowCamera) for view in ('first','third')}
        for view in filters:
            encoders[view]=Encoder(ffmpeg,output/f'{view}.mp4',fps)
            maps[view]=(output/f'{view}.frame_map.jsonl').open('w')
        moving=plan[0][1] if moving is None else moving
        picks={0,len(plan)//4,len(plan)//2,3*len(plan)//4,len(plan)-1}
        picks.update(min(len(plan)-1,max(0,round((moving+(plan[-1][1]-moving)*f-plan[0][1])*fps))) for f in (.1,.5,.9))
        for index,t,lower,upper,alpha in plan:
            a=rows[lower]; b=rows[upper]
            state=interpolate_state(backend.mj,backend.sim.m,a['state'],b['state'],alpha)
            mode=a['mode']
            fi=bisect.bisect_right(frame_times,t)-1
            obs=frames[fi] if fi>=0 else None
            camera=obs['camera'] if obs else dict(yaw=0,pitch=-16)
            for view in ('first','third'):
                backend.follow_camera=filters[view]; filters[view].time=t
                backend.camera_yaw=camera['yaw']; backend.camera_pitch=camera['pitch']
                im=backend.frame(state,mode,view)
                encoders[view].write(im)
                frame=dict(video_frame=index,fps=fps,pts_seconds=index/fps,sim_t=t,
                    state_row_lower=lower,state_row_upper=upper,state_t_lower=a['t'],state_t_upper=b['t'],
                    interpolation_alpha=alpha,state_gap_s=b['t']-a['t'],mode=mode,
                    state_sha256=hashlib.sha256(state.tobytes()).hexdigest(),
                    render_rgb_sha256=hashlib.sha256(im.tobytes()).hexdigest(),view=view,
                    preceding_observation_id=obs['image_id'] if obs else None,
                    observation_state_age_s=t-obs['sim']['t'] if obs else None,
                    camera_angles=camera if view=='first' else None,
                    camera_smoothed_xy_yaw=list(filters[view].last) if view=='third' else None,
                    ground_truth_xy_yaw=[float(backend.data.qpos[0]),float(backend.data.qpos[1]),
                        float(np.arctan2(2*(backend.data.qpos[3]*backend.data.qpos[6]+backend.data.qpos[4]*backend.data.qpos[5]),1-2*(backend.data.qpos[5]**2+backend.data.qpos[6]**2)))])
                maps[view].write(json.dumps(frame)+'\n')
                if index in picks: Image.fromarray(im).save(output/f'{view}-{index:06d}.jpg',quality=92)
            if index%300==0: print(json.dumps(dict(frame=index,total=len(plan),render_wall_s=time.monotonic()-start)),flush=True)
    except BaseException as e:
        first_error=e
    finally:
        for encoder in encoders.values():
            try: encoder.close()
            except Exception as e:
                if first_error is None: first_error=e
        for f in maps.values(): f.close()
        if backend: backend.close()
        manifest['render_wall_s']=time.monotonic()-start
        manifest['sources_unchanged']=source_hashes=={str(p):sha(p) for p in source_paths}
        manifest['external_unchanged']=external(game_root)==expected_external
        manifest['error']=str(first_error) if first_error else None
        write_json(output/'render-manifest.json',manifest)
    if first_error: raise first_error
    if not manifest['sources_unchanged'] or not manifest['external_unchanged']: raise RuntimeError('input artifacts changed during rendering')
    validations={}
    for view in ('first','third'):
        validations[view]=validate_video(output/f'{view}.mp4',output/f'{view}.frame_map.jsonl',ffmpeg,output/f'{view}.validation.json')
        thumbs=[]
        for p in sorted(output.glob(f'{view}-*.jpg')):
            im=Image.open(p).convert('RGB');im.thumbnail((426,240));thumbs.append((p.name,im))
        sheet=Image.new('RGB',(426*3,270*math.ceil(len(thumbs)/3)),'#10202c'); draw=ImageDraw.Draw(sheet)
        for i,(label,im) in enumerate(thumbs):
            x=(i%3)*426;y=(i//3)*270;sheet.paste(im,(x,y));draw.text((x+8,y+242),label,fill='white')
        sheet.save(output/f'{view}.contact-sheet.jpg',quality=92)
    camera_rows=[json.loads(l) for l in (output/'third.frame_map.jsonl').read_text().splitlines()]
    raw=np.array([x['ground_truth_xy_yaw'] for x in camera_rows])
    filtered=np.array([x['camera_smoothed_xy_yaw'] for x in camera_rows])
    def motion(values):
        yaw_steps=np.arctan2(np.sin(np.diff(values[:,2])),np.cos(np.diff(values[:,2])))
        accel=np.diff(values[:,:2],n=2,axis=0)*fps*fps
        return dict(max_yaw_step_deg=float(np.max(np.abs(yaw_steps)))*180/math.pi,
            rms_xy_acceleration_m_s2=float(np.sqrt(np.mean(accel**2))))
    camera_quality=dict(raw_robot=motion(raw),smoothed_chase=motion(filtered),
                        distance_m=4,lookat_height_m=.85,elevation_deg=-12)
    write_json(output/'validation.json',dict(views=validations,camera=camera_quality,pass_all=all(v['pass_all'] for v in validations.values())))
    return output

def main(argv=None):
    p=argparse.ArgumentParser(description='Offline two-view rendering from immutable game states')
    p.add_argument('--session',type=Path,required=True);p.add_argument('--trial',required=True)
    p.add_argument('--game-root',type=Path,required=True);p.add_argument('--ffmpeg',type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--fps',type=int,default=30);p.add_argument('--clip-seconds',type=float)
    p.add_argument('--action-only',action='store_true',help='render from one sim second before first movement; keep all source records')
    a=p.parse_args(argv)
    print(render_trial(a.session,a.trial,a.game_root,a.ffmpeg,a.output,a.fps,a.clip_seconds,a.action_only))

if __name__=='__main__':main()
