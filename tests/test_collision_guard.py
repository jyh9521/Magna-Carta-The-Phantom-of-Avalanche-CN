import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))


class CollisionGuardTests(unittest.TestCase):
    def fixture(self):
        p=ROOT/'build/native/Release/collision_guard_fixture.exe'
        if not p.exists():self.skipTest('Owned Win32 fixture must be built locally')
        return p

    def test_compiled_baseline_and_modified_owned_image(self):
        p=self.fixture()
        b=subprocess.run([str(p),'--baseline'],capture_output=True,text=True,timeout=30)
        self.assertEqual(b.returncode,1)
        self.assertIn('invalid_endpoint=accepted policy=absent',b.stdout)
        a=subprocess.run([str(p)],capture_output=True,text=True,timeout=30)
        self.assertEqual(a.returncode,0,a.stdout+a.stderr)
        self.assertIn('bounds=native8 rollback=byte_exact',a.stdout)

    def test_scripted_player_motion_retains_native_xyz(self):
        q=subprocess.run([str(self.fixture()),'--scripted-motion'],capture_output=True,text=True,timeout=30)
        self.assertEqual(q.returncode,0,q.stdout+q.stderr)
        self.assertIn('xyz=exact mode=2 locks=0 npc_collision=retained',q.stdout)
        self.assertIn('rollback=byte_exact game_started=false',q.stdout)

    def test_real_bsp_compiled_kernel(self):
        p=ROOT/'runtime/data/MCAlpha.dll';k=ROOT/'build/native/Release/collision_kernel_replay.dll'
        if not p.exists() or not k.exists():self.skipTest('Local game geometry and owned compiled kernel required')
        with tempfile.TemporaryDirectory() as temp:
            report=Path(temp)/'report.json'
            q=subprocess.run([sys.executable,'-B',str(ROOT/'tools/replay_collision_guard.py'),
                '--source',str(ROOT/'runtime/data'),'--kernel',str(k),'--report',str(report)],
                cwd=ROOT,capture_output=True,text=True,timeout=90)
            self.assertEqual(q.returncode,0,q.stdout+q.stderr)
            r=json.loads(report.read_text('utf8'))
            self.assertEqual(len(r['cases']),4)
            self.assertTrue(r['compiled_kernel_native_oracle_pass'])
            self.assertFalse(r['player_ingress_reproduced'])
            self.assertTrue(all(c['recovered']['status']==2 and c['reentry']['status']==1 for c in r['cases']))

    def test_no_map_specific_runtime_coordinates(self):
        source=(ROOT/'src/runtime/collision_guard.cpp').read_text('utf8')
        self.assertNotIn('==614',source)
        self.assertIn('word(scene,0x156c)!=2',source)
        self.assertIn('memcpy(scratch,c->tree+0x14,28)',source)


if __name__=='__main__':unittest.main()
