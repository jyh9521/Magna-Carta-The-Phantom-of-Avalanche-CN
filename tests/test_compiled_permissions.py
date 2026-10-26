"""Real Windows ACL gates; UAC dispatch is intercepted, never auto-approved."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import test_compiled_desktop as desktop


@unittest.skipUnless(os.name == 'nt', 'Windows ACL integration')
class CompiledPermissionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix='compiled permission template ')
        cls.base = Path(cls.workspace.name)
        cls.template, _, _, _ = desktop.make_owned_fixture(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='compiled permission case ')
        self.addCleanup(self.temp.cleanup)
        self.case = Path(self.temp.name)
        self.root = self.case/'Program Files fixture'
        shutil.copytree(self.template, self.root)
        self.env = dict(os.environ, LOCALAPPDATA=str(self.case/'original user data'))
        self.script = self.case/'probe.ps1'

    def ps(self, body):
        self.script.write_text("$ErrorActionPreference='Stop'\n[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)\n"
                               "$root=$args[0]\n[Reflection.Assembly]::LoadFrom((Join-Path $root 'modules/DesktopRuntime.dll')) | Out-Null\n"+body,
                               encoding='utf-8-sig')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(self.script), str(self.root)],
                                env=self.env, capture_output=True, encoding='utf8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        return result.stdout.strip()

    def test_writable_installation_does_not_request_elevation_or_leave_probe(self):
        before = set(self.root.iterdir())
        self.assertEqual(self.ps("[DesktopRuntime.Elevation]::Required($root,$null,$true)"), 'False')
        self.assertEqual(set(self.root.iterdir()), before)

    def test_embedded_manifest_disables_implicit_virtualstore_redirection(self):
        for name in ('Configure.exe','Game.exe'):
            self.assertEqual(desktop.audit.exe_execution_level(self.root/name),'asInvoker')

    def test_root_denied_creation_or_ini_denied_write_each_require_elevation(self):
        for target, right in [('directory', 'CreateFiles'), ('file', 'WriteData')]:
            with self.subTest(target=target):
                accessor = 'Directory' if target == 'directory' else 'File'
                path = '$root' if target == 'directory' else "(Join-Path $root 'DDrawCompat-MagnaCarta.ini')"
                text = self.ps(f"""
$path={path};$old=[IO.{accessor}]::GetAccessControl($path)
$acl=[IO.{accessor}]::GetAccessControl($path)
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'{right}','Deny'))
[IO.{accessor}]::SetAccessControl($path,$acl)
try {{ [DesktopRuntime.Elevation]::Required($root,$null,$true) }}
finally {{ $old.SetSecurityDescriptorSddlForm($old.GetSecurityDescriptorSddlForm('Access'),'Access');[IO.{accessor}]::SetAccessControl($path,$old) }}
""")
                self.assertEqual(text, 'True')
        self.assertFalse(list(self.root.glob('access-*.tmp')))
        self.assertEqual((self.root/'DDrawCompat-MagnaCarta.ini').read_bytes(), b'base display')

    def test_runas_targets_same_entry_and_preserves_original_user_and_arguments(self):
        result = json.loads(self.ps("""
$p=[DesktopRuntime.Elevation]::StartInfo($root,$true,[string[]]@('--settings-file','C:\\settings folder\\a.json','--verify-only'))
@{file=$p.FileName;args=$p.Arguments;verb=$p.Verb;shell=$p.UseShellExecute;cwd=$p.WorkingDirectory;style=$p.WindowStyle.ToString()}|ConvertTo-Json -Compress
"""))
        self.assertEqual(result['file'], str(self.root/'Configure.exe'))
        self.assertEqual(result['verb'], 'runas')
        self.assertTrue(result['shell'])
        self.assertEqual(result['style'], 'Normal')
        self.assertIn('"--settings-file" "C:\\settings folder\\a.json" "--verify-only"', result['args'])
        self.assertIn('"--elevated" "--user-local-data" "'+self.env['LOCALAPPDATA']+'"', result['args'])

    def test_relative_paths_are_normalized_before_uac_changes_working_directory(self):
        result=json.loads(self.ps("""
$p=[DesktopRuntime.Elevation]::StartInfo($root,$false,[string[]]@('--settings-file','relative settings.json','--verify-only'))
@{args=$p.Arguments;expected=[IO.Path]::GetFullPath('relative settings.json');style=$p.WindowStyle.ToString()}|ConvertTo-Json -Compress
"""))
        self.assertIn('"'+result['expected']+'"',result['args'])
        self.assertEqual(result['style'],'Hidden')

    def test_atomic_write_preserves_readonly_attribute_and_allows_existing_file_fallback(self):
        self.assertEqual(self.ps("""
$path=Join-Path $root 'enhancements.json';$value=[DesktopRuntime.Settings]::Defaults()
[DesktopRuntime.Settings]::Write($path,$value)
[IO.File]::SetAttributes($path,'ReadOnly')
try {
 $value['resolution']='2k';[DesktopRuntime.Settings]::Write($path,$value)
 if([IO.File]::GetAttributes($path) -ne 'ReadOnly'){throw 'Attribute changed'}
 if([DesktopRuntime.Settings]::Read($path)['resolution'] -ne '2k'){throw 'Settings missing'}
}finally{[IO.File]::SetAttributes($path,'Normal')}
$oldDir=[IO.Directory]::GetAccessControl($root);$acl=[IO.Directory]::GetAccessControl($root)
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'CreateFiles','Deny'))
[IO.Directory]::SetAccessControl($root,$acl)
try {
 $value['resolution']='4k';[DesktopRuntime.Settings]::Write($path,$value)
 if([DesktopRuntime.Settings]::Read($path)['resolution'] -ne '4k'){throw 'Fallback write missing'}
 'READONLY_WRITE PASS bytes=updated attributes=preserved existing_fallback=exact'
}finally{$oldDir.SetSecurityDescriptorSddlForm($oldDir.GetSecurityDescriptorSddlForm('Access'),'Access');[IO.Directory]::SetAccessControl($root,$oldDir)}
"""),'READONLY_WRITE PASS bytes=updated attributes=preserved existing_fallback=exact')

    def dispatch(self, configure, accept=False):
        # Only this fixture ACL is restored to emulate permission being granted.
        # The production dispatcher still uses ShellExecute runas and an OS token.
        return self.ps("""
if([DesktopRuntime.Elevation]::IsAdministrator()){'ADMIN_TOKEN_SKIP';exit 0}
$ini=Join-Path $root 'DDrawCompat-MagnaCarta.ini'
$old=[IO.File]::GetAccessControl($ini);$acl=[IO.File]::GetAccessControl($ini)
$oldDir=[IO.Directory]::GetAccessControl($root);$dirAcl=[IO.Directory]::GetAccessControl($root)
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'WriteData','Deny'))
$dirAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'CreateFiles','Deny'))
[IO.File]::SetAccessControl($ini,$acl);[IO.Directory]::SetAccessControl($root,$dirAcl)
$script:count=0
try {
 $callback=[Func[Diagnostics.ProcessStartInfo,int]]{param($info)
  $script:count++;if($info.Verb -ne 'runas' -or -not $info.UseShellExecute){throw 'Missing elevation'}
  if(Test-Path (Join-Path $root 'enhancements.json')){throw 'Settings written before UAC'}
  if([IO.File]::ReadAllText($ini) -ne 'base display'){throw 'INI written before UAC'}
  CALLBACK
 }
 $result=[DesktopRuntime.Entry]::RunWithElevation($root,CONFIGURE,[string[]]@('--verify-only'),$callback)
 "DISPATCH exit=$result requests=$script:count"
}finally{$old.SetSecurityDescriptorSddlForm($old.GetSecurityDescriptorSddlForm('Access'),'Access');$oldDir.SetSecurityDescriptorSddlForm($oldDir.GetSecurityDescriptorSddlForm('Access'),'Access');[IO.File]::SetAccessControl($ini,$old);[IO.Directory]::SetAccessControl($root,$oldDir)}
""".replace('CONFIGURE', '$true' if configure else '$false').replace(
            # Interactive Configure needs elevation, but its offline self-test must not.
            "[string[]]@('--verify-only'),$callback", "[string[]]@(),$callback" if configure else "[string[]]@('--verify-only'),$callback").replace('CALLBACK',
            "$old.SetSecurityDescriptorSddlForm($old.GetSecurityDescriptorSddlForm('Access'),'Access');$oldDir.SetSecurityDescriptorSddlForm($oldDir.GetSecurityDescriptorSddlForm('Access'),'Access');[IO.File]::SetAccessControl($ini,$old);[IO.Directory]::SetAccessControl($root,$oldDir);return [DesktopRuntime.Launcher]::Run($root,[NullString]::Value,'configured',$true,$false)" if accept else 'return 1223'))

    def test_cancelled_uac_does_not_write_settings_or_start_native_launcher(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for configure in (True, False):
            result = self.dispatch(configure)
            if result == 'ADMIN_TOKEN_SKIP': self.skipTest('UAC routing needs a non-elevated token')
            self.assertIn('DISPATCH exit=1223 requests=1', result)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertFalse(list((self.case/'original user data').rglob('launcher.stdout.txt')))
        logs=list((self.case/'original user data').rglob('*.log'))
        self.assertEqual(len(logs),2)
        for log in logs:self.assertIn('已取消管理员授权',log.read_text(encoding='utf-8-sig'))

    def test_granted_permission_continues_same_native_preflight_and_root_save(self):
        result = self.dispatch(False, accept=True)
        if result == 'ADMIN_TOKEN_SKIP': self.skipTest('UAC routing needs a non-elevated token')
        self.assertIn('DISPATCH exit=0 requests=1', result)
        self.assertEqual(json.loads((self.root/'enhancements.json').read_bytes()), desktop.DEFAULT)
        self.assertEqual((self.root/'DDrawCompat-MagnaCarta.ini').read_bytes(), b'base display')
        self.assertEqual(len(list((self.case/'original user data').rglob('launcher.stdout.txt'))),1)

    def test_read_only_checks_never_request_uac_and_retry_marker_cannot_loop(self):
        result=self.ps("""
$callback=[Func[Diagnostics.ProcessStartInfo,int]]{param($info) throw 'Unexpected UAC'}
$a=[DesktopRuntime.Entry]::RunWithElevation($root,$false,[string[]]@('--check-installed'),$callback)
$b=[DesktopRuntime.Entry]::RunWithElevation($root,$true,[string[]]@('--self-test'),$callback)
$c=[DesktopRuntime.Entry]::RunWithElevation($root,$false,[string[]]@('--user-local-data',$env:LOCALAPPDATA),$callback)
$d=[DesktopRuntime.Entry]::RunWithElevation($root,$false,[string[]]@('--elevated'),$callback)
$e=2;if(-not [DesktopRuntime.Elevation]::IsAdministrator()){$e=[DesktopRuntime.Entry]::RunWithElevation($root,$false,[string[]]@('--elevated','--user-local-data',$env:LOCALAPPDATA),$callback)}
"READ_ONLY check=$a self=$b malformed=$c retry=$d unelevated_marker=$e"
""")
        self.assertEqual(result, 'READ_ONLY check=0 self=0 malformed=2 retry=2 unelevated_marker=2')
        self.assertFalse((self.root/'enhancements.json').exists())


if __name__ == '__main__': unittest.main()
