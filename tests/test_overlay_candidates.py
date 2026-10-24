from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tempfile,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_clean_overlay as tool
import test_overlay_bundle as overlay
import test_configuration_verify_transaction as transaction


class CandidatePackageTests(unittest.TestCase):
 def test_candidate_package_is_self_contained_and_defaults_are_explicit(self):
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp);runtime,previous,_=overlay.OverlayPackageTests.fixture(self,d)
   native=b''.join(s.encode('utf-16le') for s in ('COLLISION_GUARD_READY','AUDIO_PROVIDER_POLICY_READY','CONTACT_AUDIO_READY'))
   (runtime/'modules/configuration.dll').write_bytes(native)
   m=json.loads((runtime/'runtime.json').read_bytes())
   m['files']['modules/configuration.dll']=tool.raw_sha(native)
   m['collision_guard']=dict(schema=1,candidate=True,default_enabled=False,entry='Play-collision-fix.cmd')
   (runtime/'runtime.json').write_text(json.dumps(m))
   before=(runtime/'runtime.json').read_bytes()
   out=d/'all.zip'
   with patch.object(tool,'validate_engine_fixes',return_value={}):tool.build(previous,tool.sha(previous),runtime,out,test_candidates=True)
   with zipfile.ZipFile(out) as z:
    release=json.loads(z.read('runtime.json'));outer=json.loads(z.read('Overlay-Manifest.json'))
    self.assertTrue(release['test_candidates']['collision_guard'])
    self.assertTrue(release['test_candidates']['audio_provider_policy'])
    self.assertEqual(release['collision_guard']['entry'],'Play.cmd')
    self.assertIn('-WithoutTestCandidates',z.read('Play-stable.cmd').decode())
    for n,h in outer['files'].items():self.assertEqual(tool.raw_sha(z.read(n)),h,n)
   self.assertEqual((runtime/'runtime.json').read_bytes(),before)

 def test_missing_candidate_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'lacks'):tool.enable_test_candidates({}, {})


class CandidateStartupTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='candidate-verifier-')
  cls.exe=Path(cls.temp.name)/'capture.exe'
  source=('public class Capture {public static int Main(string[] a){'
   'if(System.Array.IndexOf(a,"--verify-only")<0)return 88;'
   'string s="";foreach(string k in new string[]{"MC_COLLISION_GUARD","MC_AUDIO_PROVIDER_POLICY","MC_CONTACT_AUDIO_TRACE"})s+=k+"="+System.Environment.GetEnvironmentVariable(k)+";";'
   'System.IO.File.WriteAllText(System.Environment.GetEnvironmentVariable("OWNED_CAPTURE_FILE"),s);'
   'return System.Environment.GetEnvironmentVariable("OWNED_VERIFY_EXIT")=="7"?7:0;}}')
  command="Add-Type -TypeDefinition '"+source+"' -OutputAssembly '"+str(cls.exe)+"' -OutputType ConsoleApplication"
  p=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,timeout=30)
  if p.returncode:raise RuntimeError(p.stderr)

 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()

 def fixture(self,root):
  transaction.SharedVerifyIntegrationTests.fixture(self,root)
  shutil.move(root/'data/DDrawCompat-MagnaCarta.ini',root/'DDrawCompat-MagnaCarta.ini');(root/'data').rmdir()
  m=json.loads((root/'runtime.json').read_bytes());m['data_root']='.'
  m['recipes']['baseline']={'module':'display'}
  m['collision_guard']=dict(schema=1,candidate=True)
  markers=b''.join(s.encode('utf-16le') for s in ('COLLISION_GUARD_READY','AUDIO_PROVIDER_POLICY_READY','CONTACT_AUDIO_READY'))
  payload={'Start.ps1':(root/'Start.ps1').read_bytes(),'modules/configuration.dll':markers}
  tool.enable_test_candidates(m,payload)
  for n,b in payload.items():
   p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
  (root/'runtime.json').write_text(json.dumps(m))

 def run_case(self,disabled=False,recipe='configured',fail=False):
  with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='all-fixes-start-') as temp:
   root=Path(temp);self.fixture(root);capture=root/'capture.txt'
   env=os.environ.copy();env['OWNED_CAPTURE_FILE']=str(capture);env['OWNED_VERIFY_EXIT']='7' if fail else '0'
   keys=('MC_COLLISION_GUARD','MC_AUDIO_PROVIDER_POLICY','MC_CONTACT_AUDIO_TRACE')
   for key in keys:env[key]='parent'
   command="$ErrorActionPreference='Stop';try{& '"+str(root/'Start.ps1')+"' -VerifyOnly -Recipe "+recipe+(' -WithoutTestCandidates' if disabled else '')+"}catch{Write-Output 'OWNED_EXPECTED_FAILURE'};"
   command+="foreach($k in @('"+"','".join(keys)+"')){if([Environment]::GetEnvironmentVariable($k,'Process') -ne 'parent'){throw 'Candidate environment leaked'}}"
   p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',command],env=env,capture_output=True,text=True,timeout=30)
   self.assertEqual(p.returncode,0,p.stdout+p.stderr)
   expected='0' if disabled or recipe=='baseline' else '1'
   self.assertEqual(capture.read_text(),''.join(k+'='+expected+';' for k in keys))
   self.assertEqual((root/'DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned baseline\r\n')
   self.assertEqual('OWNED_EXPECTED_FAILURE' in p.stdout,fail,p.stdout+p.stderr)

 def test_normal_play_and_configure_shared_route_enable_candidates(self):self.run_case()
 def test_stable_entry_disables_only_test_candidates(self):self.run_case(disabled=True)
 def test_baseline_never_enables_candidates(self):self.run_case(recipe='baseline')
 def test_failure_restores_environment_and_display_ini(self):self.run_case(fail=True)


if __name__=='__main__':unittest.main()
