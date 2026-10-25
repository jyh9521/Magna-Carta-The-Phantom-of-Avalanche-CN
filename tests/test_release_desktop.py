import hashlib,json,sys,tempfile,unittest,zipfile,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import build_release_v1 as release
import deploy_desktop_entries as deploy
from build_desktop_entries import build as build_entries

def sha(b):return hashlib.sha256(b).hexdigest()
class ReleaseDesktopTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='desktop entries ');cls.entries=Path(cls.tmp.name)/'entries';build_entries(cls.entries);(cls.entries/'owned-launcher.exe').write_bytes(b'MZUSER_DATA_CACHE_V1')
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_real_exes_route_hidden_scripts_and_propagate_failures(self):
  with tempfile.TemporaryDirectory(prefix='desktop route ') as d:
   d=Path(d);(d/'config').mkdir()
   env=os.environ.copy();env['LOCALAPPDATA']=str(d/'user data')
   key=str(d.resolve()).rstrip('\\/').upper().encode('utf8')
   cache=d/'user data/MagnaCarta/Installations'/hashlib.sha256(key).hexdigest()[:16]/'cache'
   import shutil
   for name in ('Configure','Game'):shutil.copy2(self.entries/(name+'.exe'),d/(name+'.exe'))
   (d/'Start.ps1').write_text("param([string]$Recipe,[switch]$VerifyOnly);if($Recipe -ne 'configured' -or -not $VerifyOnly){exit 8};'DESKTOP_GAME_ROUTE PASS';exit 0")
   (d/'config/Configure.ps1').write_text("param([switch]$SelfTest);if(-not $SelfTest){exit 9};'DESKTOP_CONFIGURE_ROUTE PASS';exit 0")
   for name,marker in [('Configure','DESKTOP_CONFIGURE_ROUTE PASS'),('Game','DESKTOP_GAME_ROUTE PASS')]:
    p=subprocess.run([str(d/(name+'.exe')),'--verify-only'],cwd=ROOT,env=env,timeout=30)
    self.assertEqual(p.returncode,0);self.assertIn(marker,(cache/(name+'.log')).read_text(encoding='utf-8-sig'))
    self.assertLess((d/(name+'.exe')).stat().st_size,32768)
   (d/'Start.ps1').write_text('exit 17')
   self.assertEqual(subprocess.run([str(d/'Game.exe'),'--verify-only'],env=env,timeout=30).returncode,17)
   self.assertEqual(subprocess.run([str(d/'Game.exe'),'--unsupported'],timeout=15).returncode,2)
 def fixture(self,d):
  d=Path(d);(d/'runtime/config').mkdir(parents=True)
  (d/'runtime/config/Configure.xaml').write_bytes(b'original ui')
  (d/'runtime/config/enhancements.json').write_bytes(b'preserved settings')
  (d/'runtime/runtime.json').write_text(json.dumps(dict(files={'config/Configure.xaml':sha(b'original ui')})))
  return d/'runtime'
 def test_deployment_rollback_is_exact_and_preserves_settings(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d);record=Path(d)/'record'
   before={p.relative_to(r).as_posix():p.read_bytes() for p in r.rglob('*') if p.is_file()}
   deploy.apply(r,self.entries,record);self.assertTrue((r/'Game.exe').exists());deploy.rollback(r,record)
   self.assertEqual(before,{p.relative_to(r).as_posix():p.read_bytes() for p in r.rglob('*') if p.is_file()})
 def test_drift_stops_rollback_before_writes(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d);record=Path(d)/'record';deploy.apply(r,self.entries,record)
   (r/'Configure.exe').write_bytes(b'drift')
   before={p.relative_to(r).as_posix():p.read_bytes() for p in r.rglob('*') if p.is_file()}
   with self.assertRaises(ValueError):deploy.rollback(r,record)
   self.assertEqual(before,{p.relative_to(r).as_posix():p.read_bytes() for p in r.rglob('*') if p.is_file()})
 def archive(self,d):
  payload={'sample.bin':b'accepted game bytes','modules/sample.dll':b'accepted module','Play.cmd':b'old entry'}
  payload['runtime.json']=json.dumps(dict(files={'modules/sample.dll':sha(payload['modules/sample.dll']),'Play.cmd':sha(payload['Play.cmd'])})).encode()
  m=dict(kind='clean_game_overlay',layout='flat',changes=[dict(resource='sample.bin',target_sha256=sha(payload['sample.bin']))],files={n:sha(b) for n,b in payload.items()})
  payload['Overlay-Manifest.json']=json.dumps(m).encode();p=Path(d)/'accepted.zip'
  with zipfile.ZipFile(p,'w') as z:
   for n,b in payload.items():z.writestr(n,b)
  return p
 def test_release_preserves_resources_and_removes_cmd_entries(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.archive(d);out=Path(d)/'release.zip';h=sha(p.read_bytes());release.build(p,h,self.entries,out,launcher=self.entries/'owned-launcher.exe')
   with zipfile.ZipFile(out) as z:
    self.assertEqual(z.read('sample.bin'),b'accepted game bytes');self.assertEqual(z.read('modules/sample.dll'),b'accepted module')
    self.assertFalse(any(n.endswith('.cmd') for n in z.namelist()))
    m=json.loads(z.read('Overlay-Manifest.json'));self.assertEqual(m['status'],'released')
    for n,h in m['files'].items():self.assertEqual(sha(z.read(n)),h)
 def test_wrong_accepted_hash_never_creates_output(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.archive(d);out=Path(d)/'release.zip'
   with self.assertRaises(ValueError):release.build(p,'0'*64,self.entries,out)
   self.assertFalse(out.exists())
if __name__=='__main__':unittest.main()
