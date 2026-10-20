"""Verify preserved experiment artifacts without writing to the source tree."""
import argparse
import hashlib
import json
from pathlib import Path
from ecowalk_drive_aiplay.recording import write_json
p=argparse.ArgumentParser(); p.add_argument('--source',required=True,type=Path); p.add_argument('--manifest',required=True,type=Path); p.add_argument('--output',required=True,type=Path); a=p.parse_args()
old=json.loads(a.manifest.read_text()); now={str(p.relative_to(a.source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.source.rglob('*') if p.is_file()}
result=dict(files_before=len(old),files_after=len(now),added=sorted(now.keys()-old.keys()),removed=sorted(old.keys()-now.keys()),changed=[p for p in old.keys()&now.keys() if old[p]!=now[p]])
write_json(a.output,result); print(json.dumps(result)); raise SystemExit(bool(result['added'] or result['removed'] or result['changed']))
