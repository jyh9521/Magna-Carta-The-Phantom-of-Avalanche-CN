from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import cleanup_release as tool
class ReleaseCleanupTests(unittest.TestCase):
 def fixture(self,d):
  r=Path(d);(r/'dist').mkdir();(r/'runtime').mkdir();(r/'runtime/runtime.json').write_text('{"files":{}}')
  (r/'runtime/MC00.sav').write_bytes(b'save');(r/'build/evidence').mkdir(parents=True);(r/'build/evidence/baseline.bin').write_bytes(b'baseline')
  subprocess.run(['git','init',str(r)],check=True,capture_output=True)
  for n in tool.KEEP:
   with zipfile.ZipFile(r/'dist'/n,'w') as z:z.writestr('Overlay-Manifest.json',json.dumps({'status':'released'}))
  (r/'dist/obsolete.zip').write_bytes(b'old')
  return r
 def test_plan_and_apply_preserve_baselines_saves_and_kept_archives(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d)
   with patch.object(tool,'ROOT',r):
    tool.clean();self.assertTrue((r/'dist/obsolete.zip').exists());tool.clean(True)
   self.assertFalse((r/'dist/obsolete.zip').exists());self.assertEqual((r/'runtime/MC00.sav').read_bytes(),b'save');self.assertEqual((r/'build/evidence/baseline.bin').read_bytes(),b'baseline')
   self.assertEqual(set(p.name for p in (r/'dist').iterdir()),set(tool.KEEP))
 def test_tracked_target_is_never_removed(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d);subprocess.run(['git','-C',str(r),'add','dist/obsolete.zip'],check=True,capture_output=True)
   with patch.object(tool,'ROOT',r),self.assertRaises(ValueError):tool.clean(True)
   self.assertTrue((r/'dist/obsolete.zip').exists())
 def test_missing_release_stops_before_deletion(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d);(r/'dist'/tool.KEEP[0]).unlink()
   with patch.object(tool,'ROOT',r),self.assertRaises(FileNotFoundError):tool.clean(True)
   self.assertTrue((r/'dist/obsolete.zip').exists())
if __name__=='__main__':unittest.main()
