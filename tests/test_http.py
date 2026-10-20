"""Opt-in real localhost HTTP integration (ECOWALK_HTTP_TESTS=1)."""
import json
import multiprocessing
import os
import socket
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from test_controller import Game
from ecowalk_drive_aiplay.config import DEFAULTS
from ecowalk_drive_aiplay.game_client import Client
from ecowalk_drive_aiplay.recording import create_session
from ecowalk_drive_aiplay.server import Controller, serve

def server_process(session,port):
    cfg=DEFAULTS|dict(controller_url=f'http://127.0.0.1:{port}')
    c=Controller(session,cfg,Game(session))
    serve(c)

@unittest.skipUnless(os.environ.get('ECOWALK_HTTP_TESTS')=='1','requires localhost socket permission')
class HTTP(unittest.TestCase):
    def test_contract_and_shutdown_process_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=create_session(tmp)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
            proc=multiprocessing.Process(target=server_process,args=(session,port)); proc.start()
            client=Client(f'http://127.0.0.1:{port}',3)
            try:
                for i in range(50):
                    try: client.request('/status'); break
                    except OSError: time.sleep(.05)
                else: self.fail('server did not start')
                for path,body in [('/nope',{}),('/start',dict(stage=1,name='../bad')),('/route',{})]:
                    with self.assertRaises(urllib.error.HTTPError) as cm: client.request(path,body)
                    self.assertEqual(cm.exception.code,400)
                    self.assertIn('error',json.load(cm.exception))
                client.request('/start',dict(stage=1,name='http_trial'))
                result=client.request('/stop',{})
                self.assertTrue(result['last_stop']['acknowledged'])
                result=client.request('/end',{})
                self.assertEqual(result['result']['outcome'],'aborted')
                self.assertTrue(result['stop']['acknowledged'])
                client.request('/shutdown',{})
                proc.join(timeout=5)
                self.assertFalse(proc.is_alive()); self.assertEqual(proc.exitcode,0)
            finally:
                if proc.is_alive(): proc.terminate(); proc.join(timeout=5)
