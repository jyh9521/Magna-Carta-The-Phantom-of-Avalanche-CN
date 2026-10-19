from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import replay_native_dialogue as replay
class DialogueReplayTests(unittest.TestCase):
    def test_unsupported_image_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'Unsupported full sample'):
            replay.run(b'owned unsupported fixture')
    def test_report_must_not_overwrite_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sample';p.write_bytes(b'owned unsupported fixture');alias=Path(d)/'report';os.link(p,alias)
            for out in [p,alias]:
                r=subprocess.run([sys.executable,'-O',str(ROOT/'tools/replay_native_dialogue.py'),'--sample',str(p),'--report',str(out)],capture_output=True,text=True)
                self.assertEqual(r.returncode,2,r.stderr)
                self.assertIn('Report must differ',r.stderr)
                self.assertEqual(p.read_bytes(),b'owned unsupported fixture')
    @unittest.skipUnless(importlib.util.find_spec('unicorn') and (ROOT/'runtime/data/MCAlpha.dll').is_file(),'Optional native replay dependency/sample')
    def test_native_input_pixel_wrap_and_control_paths(self):
        report=replay.run((ROOT/'runtime/data/MCAlpha.dll').read_bytes())
        self.assertFalse(report['game_started']);self.assertEqual(len(report['cases']),6)
        long=report['cases'][4];controls=report['cases'][5]
        self.assertEqual((long['phase'],long['source_cursor'],long['source_length']),(4,4,12))
        self.assertEqual(long['labels'],['ABCD'])
        self.assertEqual((controls['phase'],controls['source_cursor']),(3,12))
        self.assertEqual(controls['labels'],['AB','CD','EF'])
