from pathlib import Path
import subprocess,tempfile,unittest,os
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('SHARED_START_SOURCE',ROOT/'src/configuration/StartShared.ps1'))
class SharedLogTests(unittest.TestCase):
 def run_cache(self,root,verify=False):
  text=SOURCE.read_text(encoding='utf8')
  block=text[text.index(" $cache=Join-Path"):text.index(" [IO.File]::WriteAllBytes((Join-Path $cache 'profile.bin')")]
  script="$ErrorActionPreference='Stop';$runtimeRoot='"+str(root).replace("'","''")+"';$VerifyOnly=$"+str(verify).lower()+";"+block
  return subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,text=True)
 def test_repeated_launch_clears_only_owned_log(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cache=root/'cache';cache.mkdir();other=cache/'user.log';other.write_bytes(b'keep')
   for n in range(3):
    log=cache/'profile.log';log.write_bytes(b'previous launch')
    p=self.run_cache(root);self.assertEqual(p.returncode,0,p.stderr)
    self.assertFalse(log.exists(),'Log path already exists on repeated launch')
    self.assertEqual(other.read_bytes(),b'keep')
 def test_verify_only_preserves_last_session_log(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'cache').mkdir();log=root/'cache/profile.log';log.write_bytes(b'last session')
   p=self.run_cache(root,True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(log.read_bytes(),b'last session')
 def test_directory_at_log_path_fails_without_deleting(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);log=root/'cache/profile.log';log.mkdir(parents=True);keep=log/'keep';keep.write_bytes(b'keep')
   p=self.run_cache(root);self.assertNotEqual(p.returncode,0);self.assertEqual(keep.read_bytes(),b'keep')
if __name__=='__main__':unittest.main()
