import copy
import json
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from ecowalk_drive_aiplay.config import DEFAULTS, DATA, load
from ecowalk_drive_aiplay.game_client import NEUTRAL
from ecowalk_drive_aiplay.recording import create_session
from ecowalk_drive_aiplay.server import Controller
from ecowalk_drive_aiplay.trial import expand
from ecowalk_drive_aiplay.validation import route_parameters

class Game:
    def __init__(self,session):
        self.commands=[]; self.fail=False
        meta=json.loads((DATA/'reference/experiment11/game-metadata.json').read_text())['1']
        self.status=dict(sim=dict(x=0.,y=0.,yaw=0.,w_meas=0.,t=1.,mode='stand',fallen=False),
            result=dict(outcome='playing',collisions=0,stage=1),course=meta['course'],
            directory=str(session/'game-runs'/'fake'),real_time_factor=1)
    def request(self,path,body=None,**kw):
        if path=='/command': self.commands.append(copy.deepcopy(body))
        if self.fail: raise TimeoutError('simulated connection failure')
        if path=='/abort': self.status['result']['outcome']='aborted'
        return copy.deepcopy(self.status)

class Safety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.s=create_session(self.tmp.name)
        self.g=Game(self.s); self.c=Controller(self.s,DEFAULTS,self.g)
        self.c.active='trial'; (self.s/'observations/trial').mkdir()
        self.c.tick(); self.c.last_image=time.monotonic()
        self.c.frames['trial:000000']=dict(source_image='file',image_sha256='hash',wall=time.time(),sim={'t':1})
        self.plan=dict(points=[[0,0],[19.55,0]],speed=1.3,lookahead=1.3,corridor=.8,seen='trial:000000',note='test')
    def tearDown(self): self.tmp.cleanup()
    def test_invalid_plans_do_not_mutate_route(self):
        self.c.apply_route(self.plan); original=self.c.route
        bad=[dict(points=[[0,0],[0,0]]),dict(points=[[0,0],[float('nan'),0]]),dict(points=[[0,0]]),
             dict(points=[[0,0],[100000,0]]),dict(speed=float('inf')),dict(lookahead=0),dict(corridor=-1),
             dict(tuning={'corner_divisor':0}),dict(tuning={'unknown':1}),dict(speed=True),dict(lease=181),dict(seen='../other'),dict(expected_route_id=99)]
        for mutation in bad:
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): self.c.apply_route(self.plan|mutation)
            self.assertIs(self.c.route,original)
    def test_end_ack_before_inactive(self):
        self.c.apply_route(self.plan); self.c.tick(); r=self.c.end()
        self.assertEqual(self.g.commands[-1],NEUTRAL); self.assertTrue(r['stop']['acknowledged']); self.assertIsNone(self.c.active)
    def test_replacement_neutral_ack(self):
        self.c.apply_route(self.plan); self.c.tick(); previous=self.c.route.id
        self.c.apply_route(self.plan|{'expected_route_id':previous})
        self.assertEqual(self.g.commands[-1],NEUTRAL); self.assertNotEqual(self.c.route.id,previous)
        self.assertEqual(self.c.cmd,NEUTRAL)
    def test_replacement_disconnect_disables_route(self):
        self.c.apply_route(self.plan); self.g.fail=True
        with self.assertRaises(ConnectionError): self.c.apply_route(self.plan)
        self.assertIsNone(self.c.route)
    def test_reset_clears_trial_state(self):
        self.c.navigation={'reason':'trial_end'}; self.c.prev_collision=99; self.c.prev_sim=200
        self.c.previous_tick=123; self.c.frames={'old':{}}; self.c.reset()
        self.assertEqual(self.c.navigation,{}); self.assertEqual(self.c.prev_collision,0)
        self.assertIsNone(self.c.prev_sim); self.assertIsNone(self.c.previous_tick); self.assertEqual(self.c.frames,{})
    def test_disconnect_attempts_neutral(self):
        self.c.apply_route(self.plan); self.g.fail=True; self.c.tick()
        self.assertIsNone(self.c.route); self.assertEqual(self.g.commands[-1],NEUTRAL); self.assertFalse(self.c.last_stop['acknowledged'])
    def test_persistent_disconnect_ends_with_error(self):
        self.c.apply_route(self.plan); self.g.fail=True
        self.c.transport_error_since=time.monotonic()-3
        self.c.tick()
        self.assertIsNone(self.c.active)
        record=json.loads((self.s/'observations/trial/result.json').read_text())
        self.assertIsNotNone(record['error']); self.assertFalse(record['stop']['acknowledged'])
    def test_persistent_invalid_status_ends(self):
        self.g.status['sim']['x']=float('nan')
        self.c.transport_error_since=time.monotonic()-3
        self.c.tick()
        self.assertIsNone(self.c.active)
    def test_trial_deadline_ends_even_without_route(self):
        self.c.started-=DEFAULTS['trial_timeout']+DEFAULTS['image_timeout']+1
        self.c.tick(); self.assertIsNone(self.c.active)
    def test_guards(self):
        for reason in ('route_deadline','image_watchdog','state_watchdog','fallen','collision_guard','terminal','corridor_violation','clearance_guard'):
            with self.subTest(reason=reason):
                self.c.reset(); self.c.active='trial'; self.c.tick(); self.c.last_image=time.monotonic()
                self.c.frames['trial:000000']=dict(source_image='file',image_sha256='hash',wall=time.time(),sim={'t':1})
                self.g.status['sim'].update(x=0,y=0,fallen=False)
                self.g.status['result'].update(outcome='playing',collisions=0)
                self.c.tick(); self.c.apply_route(self.plan)
                if reason=='route_deadline': self.c.route.deadline=0
                elif reason=='image_watchdog': self.c.last_image-=2
                elif reason=='state_watchdog': self.c.last_sim_change-=3
                elif reason=='fallen': self.g.status['sim']['fallen']=True
                elif reason=='collision_guard': self.g.status['result']['collisions']=1
                elif reason=='terminal': self.g.status['result']['outcome']='finished'
                elif reason=='corridor_violation': self.g.status['sim']['y']=2
                elif reason=='clearance_guard': self.g.status['course']['obstacles']=[[0,0,.1,.1]]
                self.c.tick()
                self.assertIsNone(self.c.route); self.assertEqual(self.c.navigation['reason'],reason)
                self.assertEqual(self.g.commands[-1],NEUTRAL)
                self.g.status['course']['obstacles']=[]
    def test_initial_image_timeout(self):
        self.c.started-=DEFAULTS['image_timeout']+1; self.c.last_image=0
        self.c.tick(); self.assertIsNone(self.c.active); self.assertEqual(self.c.last_stop['reason'],'initial_image_timeout')
    def test_stop_requires_no_image(self):
        self.c.apply_route(self.plan); self.c.action('/stop',{})
        self.assertEqual(self.g.commands[-1],NEUTRAL)
    def test_runner_interrupt_stops_and_ends(self):
        from ecowalk_drive_aiplay.trial import run_trial
        actions=[]
        class InterruptedClient:
            def request(self,path,*args,**kwargs):
                actions.append(path)
                if path=='/start': raise KeyboardInterrupt()
                return {}
        with patch('ecowalk_drive_aiplay.trial.Client',return_value=InterruptedClient()):
            with self.assertRaises(KeyboardInterrupt): run_trial(self.s,DEFAULTS,1,1)
        self.assertEqual(actions,['/start','/stop','/end'])
        self.assertEqual(json.loads((self.s/'s1_final1.failure.json').read_text())['error'],'KeyboardInterrupt')
    def test_unique_session_and_config(self):
        other=create_session(self.tmp.name); self.assertNotEqual(other,self.s)
        self.assertEqual(load(self.s)['controller_url'],DEFAULTS['controller_url'])
    def test_fixed_routes_match_reference(self):
        meta=json.loads((DATA/'reference/experiment11/game-metadata.json').read_text())
        for stage in (1,2,3):
            for i in (1,2,3):
                t=json.loads((DATA/f'configs/experiment11/s{stage}_final{i}.json').read_text())
                p=expand(t['parameters'],meta[str(stage)]['course'])
                old=json.loads((DATA/f'reference/experiment11/expanded-routes/s{stage}_final{i}_executed.json').read_text())
                self.assertEqual(p['points'],old['executed_parameters']['points']); route_parameters(p,meta[str(stage)]['course'])

if __name__=='__main__': unittest.main()
