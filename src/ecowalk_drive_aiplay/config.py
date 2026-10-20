"""One runtime configuration shared by the CLI, server and trial runner."""
import json
from pathlib import Path
from urllib.parse import urlparse

DEFAULTS = dict(game_url='http://127.0.0.1:8128', controller_url='http://127.0.0.1:8129',
                request_timeout=1.0, startup_timeout=60.0, image_timeout=15.0,
                trial_timeout=175.0, period=.05, frame_period=.2,
                image_watchdog=1.2, state_watchdog=2.0, font=None)
DATA = Path(__file__).parent / 'data'

def load(session):
    c = DEFAULTS | json.loads((Path(session)/'runtime.json').read_text())
    for key in ('game_url', 'controller_url'):
        u = urlparse(c[key])
        if u.scheme != 'http' or u.hostname != '127.0.0.1' or not u.port or u.path or u.username:
            raise ValueError(f'{key}: require http://127.0.0.1:PORT')
    if c['game_url'] == c['controller_url']:
        raise ValueError('game and controller ports must differ')
    for key in ('request_timeout','startup_timeout','image_timeout','trial_timeout','period','frame_period','image_watchdog','state_watchdog'):
        if not isinstance(c[key], (float,int)) or not 0 < c[key] <= 300:
            raise ValueError(f'invalid {key}')
    return c
