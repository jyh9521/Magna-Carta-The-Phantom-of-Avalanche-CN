from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build/native/Release/world_gamepad_fixture.exe'
@unittest.skipUnless(EXE.is_file(),'Build the owned world_gamepad_fixture first')
class MenuLocatorTests(unittest.TestCase):
    def test_menu_has_visible_exact_native_locator(self):
        r=subprocess.run([str(EXE)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('GAMEPAD_MENU_LOCATOR_REPLAY PASS menu=visible exploration=hidden mouse_restore=retained native_hit_position=exact game_started=false',r.stdout)
