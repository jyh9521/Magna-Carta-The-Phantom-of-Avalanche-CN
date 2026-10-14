import subprocess
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class QueuedWorldReplayTests(unittest.TestCase):
    def test_real_hook_deferred_camera_replay(self):
        executable = ROOT / 'build/native/Release/motion60_fixture.exe'
        if not executable.exists():
            self.skipTest('Build the owned Win32 motion60_fixture before running native replay')
        result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('QUEUED_WORLD_REPLAY PASS samples=32 camera_motion=true camera_rotation=true queue_before_camera=true world_restore=exact game_started=false', result.stdout)
        self.assertIn('commercial_code_executed=false game_started=false', result.stdout)
if __name__ == '__main__':
    unittest.main()
