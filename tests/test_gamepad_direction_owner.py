from pathlib import Path
import subprocess, unittest
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build/native/Release/gamepad_ui_fixture.exe'
@unittest.skipUnless(EXE.is_file(),'Build owned gamepad_ui_fixture first')
class DirectionOwnerTests(unittest.TestCase):
    def test_controller_direction_has_one_owner(self):
        r=subprocess.run([str(EXE)],capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('GAMEPAD_DIRECTION_OWNER_REPLAY PASS sidebar=exclusive green_control=native repeat=exclusive release=exclusive physical_keyboard=preserved state_restore=exact game_started=false',r.stdout)
