import json
import urllib.request

NEUTRAL = dict(v=0, w=0, brake=False)

class Client:
    def __init__(self, url, timeout=1):
        self.url, self.timeout = url.rstrip('/'), timeout
    def request(self, path, body=None, timeout=None, raw=False):
        q = urllib.request.Request(self.url+path,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(q, timeout=self.timeout if timeout is None else timeout) as f:
            b=f.read()
        return b if raw else json.loads(b)
