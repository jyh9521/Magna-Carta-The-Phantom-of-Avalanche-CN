from pathlib import Path
import importlib.util,json,subprocess,sys,unittest,os,tempfile
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_title_replay',ROOT/'tools/replay_native_title.py')
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
class NativeTitleReplayTests(unittest.TestCase):
    def test_unknown_image_rejected_before_emulation(self):
        with self.assertRaisesRegex(ValueError,'Unsupported MCAlpha image'):
            replay.NativeTitle(b'unknown image')
    def test_report_cannot_overwrite_sample_or_hardlink_alias(self):
        (ROOT/'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='native-replay-guard-') as directory:
            folder=Path(directory).resolve()
            self.assertTrue(folder.is_relative_to((ROOT/'build').resolve()))
            sample=folder/'sample.bin';sample.write_bytes(b'owned invalid sample')
            alias=folder/'alias.json';os.link(sample,alias)
            for output in [sample,alias]:
                r=subprocess.run([sys.executable,str(ROOT/'tools/replay_native_title.py'),'--sample',str(sample),'--report',str(output)],capture_output=True,text=True)
                self.assertEqual(r.returncode,2,r.stderr)
                self.assertIn('Report must differ from the sample path',r.stderr)
                self.assertEqual(sample.read_bytes(),b'owned invalid sample')
    @unittest.skipUnless(importlib.util.find_spec('unicorn') and (ROOT/'runtime/data/MCAlpha.dll').is_file(),'Requires optional Unicorn and user-supplied supported image')
    def test_original_instruction_mouse_and_title_contract(self):
        result=replay.run_replay((ROOT/'runtime/data/MCAlpha.dll').read_bytes())
        self.assertEqual(len(result['cases']),33)
        self.assertGreater(result['native_instructions'],20000)
        self.assertFalse(result['game_dll_loaded'])
        self.assertFalse(result['game_started'])
        cases={c['name']:c for c in result['cases']}
        self.assertEqual(cases['title_16d_press_hold_release_idle']['transition_requests'],[7])
        self.assertEqual(cases['title_16e_press_hold_release_idle']['transition_requests'],[9])
        self.assertEqual(cases['title_16f_press_hold_release_idle']['transition_requests'],[11])
        self.assertEqual(cases['start_release_resource_boundary']['transition_request'],'not_reached')
        self.assertEqual(cases['start_release_resource_boundary']['boundary']['size'],0x13c)
        self.assertTrue(cases['exclusive_exact_top']['admitted'])
        self.assertFalse(cases['exclusive_rejects_sibling']['admitted'])
        self.assertGreater(cases['fractional_offset_ftol']['ftol_shim_calls'],0)
