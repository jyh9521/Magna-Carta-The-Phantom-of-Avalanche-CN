from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build/native/Release/gamepad_ui_fixture.exe'
@unittest.skipUnless(EXE.is_file(),'Build owned gamepad_ui_fixture first')
class NativeAdmissionTests(unittest.TestCase):
    def test_virtual_focus_matches_original_mouse_admission(self):
        r=subprocess.run([str(EXE)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('GAMEPAD_NATIVE_ADMISSION_REPLAY PASS nonmodal_mode2=skipped exact_modal_owner=admitted ordinary_descendant=rejected source_mouse_contract=matched game_started=false',r.stdout)
