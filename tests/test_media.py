import math
import unittest
from ecowalk_drive_aiplay.media.timeline import validate_times,sample_times,interpolate_state,SimulationFollowCamera

class Timeline(unittest.TestCase):
    def test_50_to_30_has_distinct_time_samples(self):
        times=validate_times([{'t':i/50} for i in range(51)])
        frames=list(sample_times(times,30))
        self.assertEqual(len(frames),31)
        self.assertAlmostEqual(frames[1][4],2/3)
        self.assertEqual(len({(f[2],f[3],round(f[4],8)) for f in frames}),31)
        self.assertAlmostEqual(frames[-1][1],1)
    def test_timestamp_rejections(self):
        for times in ([0,0],[.02,0],[0,float('nan')],[0,.1]):
            with self.subTest(times=times),self.assertRaises(ValueError): validate_times([{'t':t} for t in times])
    def test_quaternion_short_arc_and_endpoints(self):
        import mujoco as mj
        import numpy as np
        model=mj.MjModel.from_xml_string('<mujoco><worldbody><body><freejoint/><geom type="sphere" size=".1" mass="1"/></body></worldbody></mujoco>')
        n=mj.mj_stateSize(model,mj.mjtState.mjSTATE_FULLPHYSICS)
        a=np.zeros(n); b=np.zeros(n); a[4]=1; b[4]=-1; b[1]=2
        mid=interpolate_state(mj,model,a,b,.5)
        self.assertAlmostEqual(mid[1],1); self.assertAlmostEqual(abs(mid[4]),1)
        self.assertAlmostEqual(np.linalg.norm(mid[4:8]),1)
        self.assertTrue(np.allclose(interpolate_state(mj,model,a,b,0),a))
        end=interpolate_state(mj,model,a,b,1)
        self.assertAlmostEqual(end[1],2); self.assertAlmostEqual(abs(end[4]),1)
    def test_timestamps_use_integer_pts_not_rounded_display(self):
        from ecowalk_drive_aiplay.media.validate import parse_timestamps
        pts=parse_timestamps('config in time_base: 1/15360, frame_rate: 30/1\nn: 3001 pts: 1536512 pts_time:100.033\nn: 3002 pts:1537024 pts_time:100.067')
        self.assertAlmostEqual(pts[1]-pts[0],1/30)
    def test_camera_uses_explicit_sim_clock(self):
        class Filter:
            def reset(self):pass
            def follow(self,x,y,yaw,now):return x,y,now
        camera=SimulationFollowCamera(Filter);camera.time=1.25
        self.assertEqual(camera.follow(1,2,0),(1,2,1.25));camera.reset()
        camera.time=2;self.assertEqual(camera.follow(1,2,0),(1,2,2))

if __name__=='__main__':unittest.main()
