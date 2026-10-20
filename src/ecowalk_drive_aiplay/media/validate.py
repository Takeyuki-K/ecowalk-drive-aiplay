"""Full H.264 decode, timestamp and image-update checks using a supplied FFmpeg."""
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from ..recording import write_json

SAMPLE_W,SAMPLE_H=160,90

def parse_timestamps(text):
    match=re.search(r'config in time_base:\s*(\d+)/(\d+)',text)
    if not match: raise ValueError('decoded stream time base unavailable')
    scale=int(match[1])/int(match[2])
    return [int(x)*scale for x in re.findall(r'\bn:\s*\d+\s+pts:\s*(-?\d+)',text)]

def validate_video(video,mapping,ffmpeg,output):
    import numpy as np
    video=Path(video); output=Path(output)
    rows=[json.loads(l) for l in Path(mapping).read_text().splitlines()]
    if not rows: raise ValueError('empty frame map')
    # showinfo is before scale, so dimensions/PTS describe the actual decoded stream.
    args=[str(ffmpeg),'-hide_banner','-loglevel','info','-xerror','-i',str(video),
          '-map','0:v:0','-vf',f'showinfo,scale={SAMPLE_W}:{SAMPLE_H}',
          '-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','-']
    stderr_path=output.with_suffix('.decode.log')
    hashes=[]; changes=[]; lumas=[]; previous=None
    with stderr_path.open('w') as log:
        proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=log)
        try:
            size=SAMPLE_W*SAMPLE_H*3
            while True:
                raw=proc.stdout.read(size)
                if not raw: break
                if len(raw)!=size: raise ValueError('partial decoded frame')
                a=np.frombuffer(raw,dtype=np.uint8).astype(np.float32)
                hashes.append(hashlib.sha256(raw).hexdigest()); lumas.append(float(a.mean()))
                if previous is not None: changes.append(float(np.abs(a-previous).mean()))
                previous=a
        finally:
            proc.stdout.close()
            code=proc.wait(timeout=60)
    text=stderr_path.read_text()
    pts=parse_timestamps(text)
    decoded_checksums=re.findall(r'\bchecksum:([0-9A-F]+)\s+plane_checksum:',text)
    decoded_updates=sum(a!=b for a,b in zip(decoded_checksums,decoded_checksums[1:]))
    fps=rows[0]['fps']; expected=len(rows); intervals=[b-a for a,b in zip(pts,pts[1:])]
    source_updates=sum(a['render_rgb_sha256']!=b['render_rgb_sha256'] for a,b in zip(rows,rows[1:]))
    sample_updates=sum(a!=b for a,b in zip(hashes,hashes[1:]))
    duration=expected/fps
    checks=dict(full_decode_ok=code==0,frame_count_matches=len(hashes)==expected,
        timestamps_count_matches=len(pts)==expected,
        decoded_checksum_count_matches=len(decoded_checksums)==expected,
        timestamps_start_zero=bool(pts) and abs(pts[0])<1e-6,
        timestamps_monotonic=all(x>0 for x in intervals),
        timestamp_grid_matches=bool(pts) and max(abs(t-i/fps) for i,t in enumerate(pts))<1e-4,
        timestamp_interval_30fps=bool(intervals) and max(abs(x-1/fps) for x in intervals)<1e-4,
        h264=bool(re.search(r'Video: h264',text)),resolution_1280x720=bool(re.search(r'\bs:1280x720\b',text)),
        nonblack=bool(lumas) and min(lumas)>2,
        rendered_source_updates=source_updates==expected-1,
        no_missing_state_brackets=all(r['state_gap_s']<=.041+1e-8 for r in rows))
    result=dict(video=str(video),sha256=hashlib.sha256(video.read_bytes()).hexdigest(),checks=checks,
        validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        pass_all=all(checks.values()),fps=fps,width=1280,height=720,codec='h264' if checks['h264'] else 'unknown',
        frames_expected=expected,frames_decoded=len(hashes),duration_seconds=duration,
        pts_first=pts[0] if pts else None,pts_last=pts[-1] if pts else None,
        max_pts_interval_error=max((abs(x-1/fps) for x in intervals),default=None),
        duplicate_source_frames=expected-1-source_updates,duplicate_decoded_sample_frames=len(hashes)-1-sample_updates,
        duplicate_decoded_full_frames=len(decoded_checksums)-1-decoded_updates,
        decoded_full_update_hz=decoded_updates/((len(decoded_checksums)-1)/fps) if len(decoded_checksums)>1 else 0,
        source_update_hz=source_updates/((expected-1)/fps) if expected>1 else 0,
        decoded_sample_update_hz=sample_updates/((len(hashes)-1)/fps) if len(hashes)>1 else 0,
        mean_sample_pixel_difference=float(np.mean(changes)) if changes else None,
        minimum_frame_mean_rgb=min(lumas,default=None),missing_decoded_frames=max(0,expected-len(hashes)),
        note='Offline sim-time visualization, not the live observation stream. Full decoded duplicates use FFmpeg showinfo checksums before scaling; sample duplicates use 160x90 RGB SHA256; source duplicates use full 1280x720 RGB SHA256.')
    write_json(output,result)
    return result

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--video-directory',type=Path,required=True);p.add_argument('--ffmpeg',type=Path,required=True)
    a=p.parse_args();folder=a.video_directory
    aggregate=json.loads((folder/'validation.json').read_text()) if (folder/'validation.json').exists() else {}
    aggregate['views']={view:validate_video(folder/f'{view}.mp4',folder/f'{view}.frame_map.jsonl',a.ffmpeg,folder/f'{view}.validation.json') for view in ('first','third')}
    aggregate['pass_all']=all(v['pass_all'] for v in aggregate['views'].values())
    write_json(folder/'validation.json',aggregate)
    print(json.dumps({k:{'pass':v['pass_all'],'frames':v['frames_decoded'],'updates_hz':v['decoded_sample_update_hz']} for k,v in aggregate['views'].items()}))

if __name__=='__main__':main()
