from pathlib import Path
import sys,tempfile,json,hashlib,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import retarget_shared_entries as tool

class EntryTests(unittest.TestCase):
 def fixture(self,root):
  (root/'data').mkdir();(root/'Start.ps1').write_bytes(b'owned shared entry')
  (root/'runtime.json').write_text(json.dumps(dict(schema=1,data_root='data',files={'Start.ps1':hashlib.sha256(b'owned shared entry').hexdigest()},recipes={r:{} for s,a,r in tool.ENTRIES.values()})))
  for n,(s,a,r) in tool.ENTRIES.items():(root/'data'/n).write_bytes(tool.original(s,a))
  (root/'data/Configure.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0.advanced-runtime\\Configure.ps1"\r\nif errorlevel 1 pause\r\n')
 def test_dry_run_apply_idempotent_no_game_copy(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.fixture(root);before=(root/'data/Play-Xbox.cmd').read_bytes()
   self.assertEqual(len(tool.retarget(root)),12);self.assertEqual((root/'data/Play-Xbox.cmd').read_bytes(),before)
   result=tool.retarget(root,True);self.assertTrue(all(x['changed'] for x in result))
   self.assertIn(b'-Recipe motion-gamepad %*',(root/'data/Play-Xbox.cmd').read_bytes())
   self.assertIn(b'-Recipe motion %*',(root/'data/Play-60fps-complete.cmd').read_bytes())
   m=json.loads((root/'runtime.json').read_text())
   self.assertEqual(m['files']['data/Play-Xbox.cmd'],hashlib.sha256((root/'data/Play-Xbox.cmd').read_bytes()).hexdigest())
   self.assertFalse(any(x['changed'] for x in tool.retarget(root,True)))
   self.assertEqual(len(list((root/'data').iterdir())),12)
 def test_unknown_script_blocks_all_writes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.fixture(root);before=(root/'data/Play-configured.cmd').read_bytes()
   (root/'data/Play-Xbox.cmd').write_bytes(b'user custom entry')
   self.assertRaises(ValueError,tool.retarget,root,True)
   self.assertEqual((root/'data/Play-configured.cmd').read_bytes(),before)
 def test_drift_blocks_all_writes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.fixture(root);(root/'Start.ps1').write_bytes(b'drift')
   self.assertRaises(ValueError,tool.retarget,root,True)
