from pathlib import Path
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[1]
class CameraSceneSampleTests(unittest.TestCase):
    def test_real_source_callers_do_not_mix_projection_and_scene_history(self):
        exe = ROOT / 'build/native/Release/motion60_fixture.exe'
        if not exe.exists():
            self.skipTest('Build the owned Win32 motion60_fixture first')
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('CAMERA_SCENE_REPLAY PASS temporary_passes=48 remainders=32 late_refresh=true canonical_return_rva=1da26 native_camera=unchanged game_started=false', result.stdout)
        self.assertIn('QUEUED_WORLD_REPLAY PASS', result.stdout)
        self.assertIn('commercial_code_executed=false game_started=false', result.stdout)
if __name__ == '__main__':
    unittest.main()
