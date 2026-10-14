from pathlib import Path
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[1]
class PacingDeadlineTests(unittest.TestCase):
    def test_actual_present_hook_clock_replay(self):
        executable = ROOT / 'build/native/Release/advanced_display_fixture.exe'
        if not executable.exists():
            self.skipTest('Build the owned Win32 advanced_display_fixture first')
        result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PACING_CLOCK_REPLAY PASS frequencies=2 frames_per_trace=3601 oversleep_ms=1 epoch_drift_ticks=0 fractional_ticks=true missed_slots=skipped pause=reanchored device_switch=reanchored game_started=false', result.stdout)
        self.assertIn('updates30=1818 updates60=1818', result.stdout)
        self.assertIn('commercial_code_executed=false game_started=false', result.stdout)
if __name__ == '__main__':
    unittest.main()
