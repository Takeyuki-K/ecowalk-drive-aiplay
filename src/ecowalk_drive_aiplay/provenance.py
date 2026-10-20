import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def environment():
    return dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
        dependencies=sorted([dict(name=d.metadata['Name'],version=d.version) for d in importlib.metadata.distributions()],key=lambda x:x['name']),
        MUJOCO_GL=os.environ.get('MUJOCO_GL'),model_identity='not independently verified')
def external(root):
    root=Path(root).resolve(); repos={}
    for name,p in [('game',root),('public',root/'vendor/k1-mp-ecowalk-public'),('teleop',root/'vendor/k1-mp-ecowalk-teleop')]:
        repos[name]=dict(commit=git(p,'rev-parse','HEAD'),status=git(p,'status','--porcelain'),
            tracked_sha256={f:sha(p/f) for f in git(p,'ls-files').splitlines() if (p/f).is_file()})
    return repos
