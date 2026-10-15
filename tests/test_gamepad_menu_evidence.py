from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build/native/Release/gamepad_ui_fixture.exe'
@unittest.skipUnless(EXE.is_file(),'Build owned gamepad_ui_fixture first')
class MenuEvidenceTests(unittest.TestCase):
    def test_target_coordinates_and_bounded_read_only_click_evidence(self):
        r=subprocess.run([str(EXE)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('GAMEPAD_MENU_EVIDENCE_REPLAY PASS target_identity=true native_coordinates=true click_phase=before_mouse state=unchanged limit=256 limit_notice=once game_started=false',r.stdout)
