import json
import threading
import time
import uuid
from pathlib import Path
from .config import DEFAULTS

def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)

def create_session(output, config=None):
    root = Path(output).expanduser().resolve()
    session = root / (time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:10])
    session.mkdir(parents=True, exist_ok=False)
    for d in ('logs','observations','game-runs','analysis'):
        (session/d).mkdir()
    write_json(session/'runtime.json', DEFAULTS | (config or {}))
    return session

class Journal:
    def __init__(self, session):
        self.root=Path(session); self.lock=threading.Lock()
    def log(self, file, **value):
        with self.lock:
            with (self.root/'logs'/file).open('a') as f:
                f.write(json.dumps(dict(wall=time.time(), monotonic=time.monotonic())|value,
                                   ensure_ascii=False, allow_nan=False)+'\n')
