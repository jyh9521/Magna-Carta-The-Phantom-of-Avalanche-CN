import hashlib,json,os,shutil,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_clean_overlay as tool
import test_configuration_verify_transaction as transaction
sha=lambda b:hashlib.sha256(b).hexdigest()
class FlatLaunchTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  transaction.SharedVerifyIntegrationTests.setUpClass();cls.exe=transaction.SharedVerifyIntegrationTests.exe
 @classmethod
 def tearDownClass(cls):transaction.SharedVerifyIntegrationTests.tearDownClass()
 def test_flat_root_reaches_owned_verifier_without_data_directory(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='flat-owned-') as d:
   root=Path(d);transaction.SharedVerifyIntegrationTests.fixture(self,root)
   shutil.move(root/'data/DDrawCompat-MagnaCarta.ini',root/'DDrawCompat-MagnaCarta.ini');(root/'data').rmdir()
   m=json.loads((root/'runtime.json').read_text());m['data_root']='.';(root/'runtime.json').write_text(json.dumps(m))
   env=os.environ.copy();env['OWNED_CAPTURE_FILE']=str(root/'capture.txt')
   r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'Start.ps1'),'-VerifyOnly'],capture_output=True,text=True,env=env,timeout=30)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('SHARED_RUNTIME PASS',r.stdout)
   self.assertIn('--workspace|'+str(root)+'|',(root/'capture.txt').read_text());self.assertIn('--in-place-overlay',(root/'capture.txt').read_text())
   self.assertFalse((root/'data').exists());self.assertEqual((root/'DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned baseline\r\n')
class NativeOverlayLaunchTests(unittest.TestCase):
 @unittest.skipUnless((ROOT/'build/native/Release/overlay_launch_fixture.exe').exists(),'Build native preflight fixture')
 def test_real_launcher_rejects_legacy_and_accepts_explicit_overlay_root(self):
  if not (ROOT/'runtime/data/MagnaCarta.exe').exists():self.skipTest('Source-locked samples not available')
  with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='native-flat-') as d:
   root=Path(d);(root/'modules').mkdir();(root/'cache').mkdir()
   for n in ['MagnaCarta.exe','MCAlpha.dll']:shutil.copyfile(ROOT/'runtime/data'/n,root/n)
   (root/'modules/profile.dll').write_bytes(b'owned preflight marker');(root/'cache/profile.bin').write_bytes(bytes(52))
   r=subprocess.run([str(ROOT/'build/native/Release/overlay_launch_fixture.exe'),str(root)],capture_output=True,text=True,timeout=20)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('registry_writes=0 children=0',r.stdout)
class OverlayPackageTests(unittest.TestCase):
 def fixture(self,d):
  runtime=d/'runtime';(runtime/'data').mkdir(parents=True);(runtime/'modules').mkdir();(runtime/'config').mkdir()
  original={'sample.bin':b'owned original','unchanged.bin':b'owned unchanged'}
  after=b'owned translated'
  for n,b in {**original,'sample.bin':after,'ddraw.dll':b'owned compatibility','DDrawCompat-MagnaCarta.ini':b'owned ini','Play-Xbox.cmd':b'archived alias'}.items():(runtime/'data'/n).write_bytes(b)
  for n,b in {'modules/configuration.dll':b'owned runtime module','modules/workspace_launcher.exe':'--in-place-overlay'.encode('utf-16le'),'Play.cmd':b'owned play','Configure.cmd':b'owned configure','Play-camera.cmd':b'archived entry','config/enhancements.json':b'{"resolution":"auto","frame_rate":60}'}.items():(runtime/n).write_bytes(b)
  manifest=dict(schema=1,data_root='data',files={n:sha((runtime/n).read_bytes()) for n in ['modules/configuration.dll','modules/workspace_launcher.exe','data/Play-Xbox.cmd','Play-camera.cmd']},data={n:sha((runtime/'data'/n).read_bytes()) for n in ['sample.bin','unchanged.bin','ddraw.dll']},recipes={'camera':{},'configured':{}})
  (runtime/'runtime.json').write_text(json.dumps(manifest))
  base=dict(schema=1,source_files={n:sha(b) for n,b in original.items()},changes=[dict(resource='sample.bin',source_sha256=sha(original['sample.bin']),target_sha256=sha(after),target_size=len(after),patch='deltas/0000.mcd',patch_sha256=sha(b'owned delta'))])
  previous=d/'previous.zip'
  with zipfile.ZipFile(previous,'w') as z:
   for n,b in {'package.json':json.dumps(base).encode(),'deltas/0000.mcd':b'owned delta','payload/data/ddraw.dll':b'owned compatibility','payload/data/DDrawCompat-MagnaCarta.ini':b'owned ini','licenses/fixture.txt':b'owned license'}.items():z.writestr(n,b)
  return runtime,previous,original
 def test_flat_zip_installs_checks_and_rolls_back_from_pristine_backup(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);runtime,previous,original=self.fixture(d);output=d/'overlay.zip';settings=(runtime/'config/enhancements.json').read_bytes()
   with patch.object(tool,'validate_engine_fixes',return_value={}):tool.build(previous,tool.sha(previous),runtime,output)
   with zipfile.ZipFile(output) as z:
    self.assertNotIn('unchanged.bin',z.namelist());self.assertFalse(any(n.startswith(('payload/','deltas/','data/','cache/')) for n in z.namelist()))
    m=json.loads(z.read('runtime.json'));self.assertEqual(m['data_root'],'.');self.assertNotIn('camera',m['recipes']);self.assertNotIn('data/Play-Xbox.cmd',m['files'])
    self.assertEqual(json.loads(z.read('config/enhancements.json'))['frame_rate'],30)
    target=d/'modified';target.mkdir();backup=d/'pristine';backup.mkdir()
    for root in (target,backup):
     for n,b in original.items():(root/n).write_bytes(b)
    # The baseline checker itself is read-only; extraction only follows it.
    script=d/'checker';script.mkdir();(script/'Verify-Overlay.ps1').write_bytes(z.read('Verify-Overlay.ps1'));(script/'Overlay-Manifest.json').write_bytes(z.read('Overlay-Manifest.json'))
    def run(action,root,expected=0):
     args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script/'Verify-Overlay.ps1'),'-Action',action,'-Root',str(root),'-Original',str(backup)]
     r=subprocess.run(args,capture_output=True,text=True,timeout=30);self.assertEqual(r.returncode,expected,r.stdout+r.stderr);return r.stdout
    self.assertIn('OVERLAY_BASELINE PASS',run('Baseline',target));z.extractall(target)
    self.assertIn('OVERLAY_MODIFIED PASS',run('CheckInstalled',target));(target/'save.sav').write_bytes(b'user save')
    (target/'config/enhancements.json').write_bytes(b'user settings')
    rolled=d/'rollback';shutil.copytree(target,rolled)
    self.assertIn('OVERLAY_ROLLBACK PASS',run('Rollback',rolled));self.assertIn('OVERLAY_BASELINE PASS',run('Baseline',rolled))
    self.assertEqual((rolled/'sample.bin').read_bytes(),original['sample.bin']);self.assertEqual((target/'sample.bin').read_bytes(),b'owned translated')
    self.assertFalse((rolled/'ddraw.dll').exists());self.assertEqual((rolled/'save.sav').read_bytes(),b'user save');self.assertEqual((rolled/'config/enhancements.json').read_bytes(),b'user settings')
    self.assertEqual((runtime/'config/enhancements.json').read_bytes(),settings)
    # Wrong-version preflight leaves every file alone.
    (target/'sample.bin').write_bytes(b'foreign');snapshot={p.relative_to(target).as_posix():p.read_bytes() for p in target.rglob('*') if p.is_file()}
    run('Rollback',target,1);self.assertEqual(snapshot,{p.relative_to(target).as_posix():p.read_bytes() for p in target.rglob('*') if p.is_file()})
 def test_small_launch_repair_actual_install_and_rollback(self):
  import build_overlay_launch_repair as repair
  from verify_release_controls_update import verify
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);runtime,previous,_=self.fixture(d);base=d/'flat.zip'
   with patch.object(tool,'validate_engine_fixes',return_value={}):tool.build(previous,tool.sha(previous),runtime,base)
   native=d/'launcher.exe';native.write_bytes(b'owned new launcher'+ '--in-place-overlay'.encode('utf-16le'))
   with patch.object(repair,'PREVIOUS_SHA256',sha(base.read_bytes())):record=repair.build(base,native,d/'record-work',d/'repair.zip')
   report=verify(record,d/'repair.zip',d/'verified',folder=repair.FOLDER)
   self.assertEqual(report['rollback_state'],'original hashes exact')
   root=Path(report['modified']);m=json.loads((root/'runtime.json').read_text());overlay=json.loads((root/'Overlay-Manifest.json').read_text())
   self.assertEqual(m['files']['modules/workspace_launcher.exe'],sha(native.read_bytes()))
   for n in repair.FILES[:-1]:self.assertEqual(overlay['files'][n],sha((root/n).read_bytes()))
 def test_builder_rejects_legacy_launcher_for_flat_layout(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);runtime,previous,_=self.fixture(d)
   (runtime/'modules/workspace_launcher.exe').write_bytes(b'legacy launcher')
   m=json.loads((runtime/'runtime.json').read_text());m['files']['modules/workspace_launcher.exe']=sha(b'legacy launcher');(runtime/'runtime.json').write_text(json.dumps(m))
   with self.assertRaisesRegex(ValueError,'Flat-capable'):tool.build(previous,tool.sha(previous),runtime,d/'bad.zip')
   self.assertFalse((d/'bad.zip').exists())
 def test_resource_drift_rejected_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);runtime,previous,_=self.fixture(d);(runtime/'data/sample.bin').write_bytes(b'foreign')
   with self.assertRaises(ValueError):tool.build(previous,tool.sha(previous),runtime,d/'bad.zip')
   self.assertFalse((d/'bad.zip').exists())
if __name__=='__main__':unittest.main()
