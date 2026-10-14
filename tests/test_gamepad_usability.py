from pathlib import Path
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build/native/Release/world_gamepad_fixture.exe"
@unittest.skipUnless(EXE.is_file(), "Build the owned native fixture first")
class GamepadUsabilityTests(unittest.TestCase):
    def test_production_input_draw_and_menu_routes(self):
        result = subprocess.run([str(EXE)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for marker in [
            "GAMEPAD_CURSOR_VISIBILITY_REPLAY PASS detected=hidden motion_click_wheel=restore idle_pad=no_steal fresh_pad=hide unrelated_sprite=preserved disconnect=restore",
            "GAMEPAD_MENU_PRECISION_REPLAY PASS engage=19000 release=11000 diagonal=one_axis direction=latched dpad=priority world_analog=unchanged",
            "GAMEPAD_SPACE_REPLAY PASS X=Space high_bit=merged held=native direct_interaction=not_duplicated mouse_walk=false",
        ]:
            self.assertIn(marker, result.stdout)
        self.assertIn("game_started=false", result.stdout)
