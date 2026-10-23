import subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class UpdateConsoleTests(unittest.TestCase):
 def test_real_cmd_waits_on_success_and_failure_and_preserves_exit(self):
  for expected in (0,7):
   with self.subTest(exit=expected),tempfile.TemporaryDirectory() as d:
    root=Path(d);(root/'Overlay-Launch-Fix-20261023').mkdir()
    (root/'Fix-Overlay-Launch.cmd').write_bytes((ROOT/'assets/player-test-package/Fix-Overlay-Launch.cmd').read_bytes())
    (root/'Overlay-Launch-Fix-20261023/Update.ps1').write_text("Write-Output 'FIXTURE_RESULT';exit "+str(expected))
    p=subprocess.Popen(['cmd.exe','/d','/c',str(root/'Fix-Overlay-Launch.cmd')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
     deadline=time.monotonic()+15;log=root/'Overlay-Launch-Fix.log'
     while time.monotonic()<deadline:
      if log.exists() and b'FIXTURE_RESULT' in log.read_bytes():break
      self.assertIsNone(p.poll(),'Window closed before key input');time.sleep(.05)
     else:self.fail('Missing result log')
     time.sleep(.15);self.assertIsNone(p.poll(),'Window closed on result')
     out,err=p.communicate(input=b'\r\n',timeout=10)
     self.assertEqual(p.returncode,expected,(out,err))
     self.assertIn(b'Press any key to close this window.',out)
     self.assertIn(('Update exit code: '+str(expected)).encode(),out)
    finally:
     if p.poll() is None:p.kill();p.communicate()
if __name__=='__main__':unittest.main()
