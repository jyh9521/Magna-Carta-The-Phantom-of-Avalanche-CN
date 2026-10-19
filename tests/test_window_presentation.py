from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WindowPresentationTests(unittest.TestCase):
    def test_native_allocation_presentation_and_raster_routes(self):
        fixture = ROOT / 'build/native/Release/configuration_display_fixture.exe'
        if not fixture.is_file():
            self.skipTest('Build configuration_display_fixture for the native presentation checks')
        result = subprocess.run([str(fixture)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('BACKBUFFER_ROUTE observed=640x480 expected=640x480', result.stdout)
        self.assertIn('PRESENT_ROUTE observed=1280x720 expected=1280x720', result.stdout)
        self.assertIn('WINDOW_RASTER_FILL PASS black_padding_pixels=0', result.stdout)


if __name__ == '__main__':
    unittest.main()
