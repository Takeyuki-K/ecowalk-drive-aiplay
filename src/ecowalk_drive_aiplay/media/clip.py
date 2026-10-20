"""Convenience action excerpts; full trial videos and their provenance remain intact."""
import argparse
import json
import subprocess
from pathlib import Path
from ..provenance import sha
from ..recording import write_json
from .validate import validate_video

def action_clips(folder,ffmpeg):
    folder=Path(folder); manifest=json.loads((folder/'render-manifest.json').read_text())
    session=Path(manifest['session']); name=manifest['name']
    controls=[json.loads(l) for l in (session/'logs/controls.jsonl').read_text().splitlines()]
    moving=next((x['sim_t'] for x in controls if x['name']==name and any(x['command'][k] for k in ('v','w'))),None)
    if moving is None: raise ValueError('no movement command; do not label a stationary trial an action excerpt')
    outputs={}
    for view in ('first','third'):
        source=folder/f'{view}.mp4'; target=folder/f'{view}-action.mp4'
        mapping=folder/f'{view}-action.frame_map.jsonl'
        if target.exists() or mapping.exists(): raise FileExistsError(target)
        rows=[json.loads(l) for l in (folder/f'{view}.frame_map.jsonl').read_text().splitlines()]
        start=next((i for i,r in enumerate(rows) if r['sim_t']>=max(rows[0]['sim_t'],moving-1)),0)
        subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-n','-i',str(source),
            '-vf',f'trim=start_frame={start},setpts=PTS-STARTPTS','-fps_mode','passthrough',
            '-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',
            '-movflags','+faststart',str(target)],check=True)
        with mapping.open('x') as f:
            for i,row in enumerate(rows[start:]):
                f.write(json.dumps(row|dict(original_video_frame=row['video_frame'],original_pts_seconds=row['pts_seconds'],
                    video_frame=i,pts_seconds=i/row['fps']))+'\n')
        validation=validate_video(target,mapping,ffmpeg,folder/f'{view}-action.validation.json')
        outputs[view]=dict(file=str(target),full_video_sha256=sha(source),first_full_video_frame=start,
            first_movement_sim_s=moving,excerpt_start_sim_s=rows[start]['sim_t'],validation=validation)
    write_json(folder/'action-clips.json',outputs)
    return outputs

def main():
    p=argparse.ArgumentParser();p.add_argument('--video-directory',type=Path,required=True);p.add_argument('--ffmpeg',type=Path,required=True)
    a=p.parse_args();action_clips(a.video_directory,a.ffmpeg)

if __name__=='__main__':main()
