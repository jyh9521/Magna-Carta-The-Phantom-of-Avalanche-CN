from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build/native/Release/world_gamepad_fixture.exe'
@unittest.skipUnless(EXE.is_file(),'Build the owned world_gamepad_fixture first')
class StickReversalTests(unittest.TestCase):
    def test_fast_reversal_reaches_production_menu_key_route(self):
        r=subprocess.run([str(EXE)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('GAMEPAD_STICK_REVERSAL_REPLAY PASS vertical=immediate horizontal=immediate neutral_sample=not_required cross_axis_noise=latched signed_endpoint=valid game_started=false',r.stdout)
