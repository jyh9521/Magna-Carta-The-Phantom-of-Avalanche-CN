from pathlib import Path
import subprocess
import unittest

EXE = Path(__file__).resolve().parents[1]/'build/native/Release/world_gamepad_fixture.exe'


@unittest.skipUnless(EXE.is_file(), 'Build owned world_gamepad_fixture first')
class CursorRenderBoundaryTests(unittest.TestCase):
    def test_hide_never_skips_position_preparation(self):
        result = subprocess.run([str(EXE)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('GAMEPAD_CURSOR_RENDER_BOUNDARY_REPLAY PASS preparation=preserved hidden_submission=suppressed mouse_restore=original menu_submission=original game_started=false', result.stdout)
