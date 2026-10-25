"""Exercise per-install user settings and logs without changing real preferences."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
MODULE=Path(os.environ.get('USER_STORAGE_MODULE',ROOT/'src/configuration/EnhancementSettings.psm1'))
def user_root(install,local):
 identity=str(Path(install).resolve()).rstrip('\\/').upper().encode('utf8')
 return Path(local)/'MagnaCarta/Installations'/hashlib.sha256(identity).hexdigest()[:16]
class UserStorageTests(unittest.TestCase):
 def run_ps(self,code,local):
  env=os.environ.copy();env['LOCALAPPDATA']=str(local)
  return subprocess.run(['powershell.exe','-NoProfile','-Command',"$ErrorActionPreference='Stop';Import-Module '"+str(MODULE)+"' -Force;"+code],capture_output=True,text=True,encoding='utf8',errors='replace',env=env,timeout=30)
 def fixture(self,d,name='install'):
  r=Path(d)/name;(r/'config').mkdir(parents=True);(r/'runtime.json').write_text('{}');(r/'Start.ps1').write_text('# fixture')
  s=dict(schema=2,resolution='2k',window_mode='windowed',frame_rate=30,native_gamepad=False,free_view=False,window_resolution='1600x900')
  (r/'config/enhancements.json').write_text(json.dumps(s));return r
 def test_default_route_uses_user_settings_and_user_log(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d);local=Path(d)/'user data';before=(r/'config/enhancements.json').read_bytes()
   p=self.run_ps("Get-EnhancementLaunchSpec '"+str(r/'config')+"' '' $true|ConvertTo-Json -Compress",local)
   self.assertEqual(p.returncode,0,p.stderr);v=json.loads(p.stdout);u=user_root(r,local)
   self.assertEqual(Path(v['Arguments'][3]),u/'enhancements.json')
   self.assertEqual(Path(v['LogPath']),u/'cache/profile.log');self.assertEqual((r/'config/enhancements.json').read_bytes(),before)
 def test_first_import_save_and_fresh_process_reload(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d);local=Path(d)/'user data';u=user_root(r,local);before=(r/'config/enhancements.json').read_bytes()
   p=self.run_ps("$p=Initialize-EnhancementUserSettings '"+str(r)+"';$s=Read-EnhancementSettings $p;$s.frame_rate=60;Write-EnhancementSettings $p $s|ConvertTo-Json -Compress",local)
   self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['frame_rate'],60)
   # A later distribution default must not overwrite saved user choices.
   (r/'config/enhancements.json').write_bytes(before.replace(b'"2k"',b'"4k"'))
   p=self.run_ps("$p=Initialize-EnhancementUserSettings '"+str(r)+"';Read-EnhancementSettings $p|ConvertTo-Json -Compress",local)
   self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['resolution'],'2k');self.assertEqual(json.loads(p.stdout)['frame_rate'],60)
   self.assertTrue((u/'enhancements.json').exists())
 def test_installations_do_not_share_preferences(self):
  with tempfile.TemporaryDirectory() as d:
   a=self.fixture(d,'a');b=self.fixture(d,'b');local=Path(d)/'user'
   p=self.run_ps("Initialize-EnhancementUserSettings '"+str(a)+"';Initialize-EnhancementUserSettings '"+str(b)+"'",local)
   self.assertEqual(p.returncode,0,p.stderr);self.assertNotEqual(user_root(a,local),user_root(b,local));self.assertTrue((user_root(a,local)/'enhancements.json').exists());self.assertTrue((user_root(b,local)/'enhancements.json').exists())
 def test_invalid_user_settings_fail_without_legacy_fallback(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d);local=Path(d)/'user';u=user_root(r,local);u.mkdir(parents=True);(u/'enhancements.json').write_bytes(b'invalid')
   p=self.run_ps("Initialize-EnhancementUserSettings '"+str(r)+"'",local)
   self.assertNotEqual(p.returncode,0);self.assertEqual((u/'enhancements.json').read_bytes(),b'invalid')
 def test_read_only_legacy_directory_does_not_block_save(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.fixture(d);local=Path(d)/'user';before=(r/'config/enhancements.json').read_bytes()
   code="$dir='"+str(r/'config')+"';$old=[IO.Directory]::GetAccessControl($dir);$acl=[IO.Directory]::GetAccessControl($dir);$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User;$deny=[Security.AccessControl.FileSystemAccessRule]::new($sid,[Security.AccessControl.FileSystemRights]::CreateFiles,[Security.AccessControl.AccessControlType]::Deny);$acl.AddAccessRule($deny);[IO.Directory]::SetAccessControl($dir,$acl);try{$p=Initialize-EnhancementUserSettings '"+str(r)+"';$s=Read-EnhancementSettings $p;$s.frame_rate=60;$null=Write-EnhancementSettings $p $s;'USER_STORAGE_READONLY PASS'}finally{[IO.Directory]::SetAccessControl($dir,$old)}"
   p=self.run_ps(code,local);self.assertEqual(p.returncode,0,p.stderr);self.assertIn('USER_STORAGE_READONLY PASS',p.stdout);self.assertEqual((r/'config/enhancements.json').read_bytes(),before)
class UserStorageDeploymentTests(unittest.TestCase):
 def fixture(self,d):
  sys.path.insert(0,str(ROOT/'tools'))
  import deploy_user_storage
  r=Path(d)/'install';(r/'config').mkdir(parents=True);(r/'modules').mkdir()
  (r/'Start.ps1').write_text("if(-not $SettingsFile){$SettingsFile=Join-Path $runtimeRoot 'config/enhancements.json'}\n $cache=Join-Path $runtimeRoot 'cache'\n")
  (r/'config/Configure.ps1').write_bytes(b'old ui');(r/'config/EnhancementSettings.psm1').write_bytes(b'old settings module')
  (r/'config/enhancements.json').write_bytes(b'legacy preferences')
  (r/'Configure.exe').write_bytes(b'old entry');(r/'Game.exe').write_bytes(b'old entry');(r/'modules/workspace_launcher.exe').write_bytes(b'old native')
  files={p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*') if p.is_file() and p.name!='enhancements.json'}
  (r/'runtime.json').write_text(json.dumps(dict(schema=1,files=files)))
  entries=Path(d)/'entries';entries.mkdir()
  for n in ('Configure.exe','Game.exe'):(entries/n).write_bytes(b'MZowned entry')
  native=Path(d)/'native.exe';native.write_bytes(b'MZUSER_DATA_CACHE_V1')
  return deploy_user_storage,r,entries,native
 def test_deploy_and_independent_rollback_preserve_all_original_bytes(self):
  with tempfile.TemporaryDirectory() as d:
   tool,r,entries,native=self.fixture(d);record=Path(d)/'record'
   before={p.relative_to(r).as_posix():p.read_bytes() for p in r.rglob('*') if p.is_file()}
   tool.apply(r,entries,native,record);self.assertIn(b'Initialize-EnhancementUserSettings',(r/'Start.ps1').read_bytes());tool.rollback(r,record)
   self.assertEqual(before,{p.relative_to(r).as_posix():p.read_bytes() for p in r.rglob('*') if p.is_file()})
 def test_rollback_drift_stops_before_writing(self):
  with tempfile.TemporaryDirectory() as d:
   tool,r,entries,native=self.fixture(d);record=Path(d)/'record';tool.apply(r,entries,native,record)
   (r/'Game.exe').write_bytes(b'foreign modification')
   before={p.relative_to(r).as_posix():p.read_bytes() for p in r.rglob('*') if p.is_file()}
   with self.assertRaises(ValueError):tool.rollback(r,record)
   self.assertEqual(before,{p.relative_to(r).as_posix():p.read_bytes() for p in r.rglob('*') if p.is_file()})
if __name__=='__main__':unittest.main()
