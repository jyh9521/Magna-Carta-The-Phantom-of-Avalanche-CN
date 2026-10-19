"""Replay mixed skin/static rendering through the installed production hooks."""
import subprocess
import unittest
from pathlib import Path

EXE = Path(__file__).resolve().parents[1] / 'build/native/Release/rigid_motion_fixture.exe'

@unittest.skipUnless(EXE.is_file(), 'Build rigid_motion_fixture first')
class RigidMotionTests(unittest.TestCase):
    def test_mixed_renderers_share_phase_and_restore(self):
        result = subprocess.run([str(EXE)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('body_part_phase=equal', result.stdout)
        self.assertIn('pose_world_restore=exact', result.stdout)
        self.assertIn('seh=restored slots_rollback=exact', result.stdout)
