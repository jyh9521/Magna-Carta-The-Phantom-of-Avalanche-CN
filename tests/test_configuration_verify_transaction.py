from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT/'src/configuration/EnhancementSettings.psm1'


class ConfigurationVerifyTransactionTests(unittest.TestCase):
    def run_transaction(self, folder, restore, action):
        code = ("$ErrorActionPreference='Stop';Import-Module '"+str(MODULE)+"' -Force;"
                "$p='"+str(folder/'display.ini')+"';"
                "Invoke-EnhancementDisplayTransaction $p ([byte[]](4,5,6)) $"+str(restore).lower()+" {"+action+"}")
        return subprocess.run(['powershell.exe', '-NoProfile', '-Command', code], capture_output=True, text=True, timeout=20)

    def test_existing_writable_ini_in_non_creatable_directory(self):
        # The installed game grants file write but no parent FILE_ADD_FILE.
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='restricted-display-') as d:
            root=Path(d); ini=root/'display.ini'; ini.write_bytes(b'original')
            code=("$ErrorActionPreference='Stop';"
                  "$dir='"+str(root)+"';$file=Join-Path $dir 'display.ini';"
                  "$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User;"
                  "$old=[IO.Directory]::GetAccessControl($dir);"
                  "$acl=[IO.Directory]::GetAccessControl($dir);"
                  "$deny=[Security.AccessControl.FileSystemAccessRule]::new($sid,[Security.AccessControl.FileSystemRights]::CreateFiles,[Security.AccessControl.AccessControlType]::Deny);"
                  "$acl.AddAccessRule($deny);[IO.Directory]::SetAccessControl($dir,$acl);"
                  "try{Import-Module '"+str(Path(os.environ.get('TRANSACTION_MODULE_SOURCE',MODULE)))+"' -Force;"
                  "Invoke-EnhancementDisplayTransaction $file ([byte[]](4,5,6)) $true {if(([IO.File]::ReadAllBytes($file)-join ',') -ne '4,5,6'){throw 'Candidate missing'}};"
                  "Invoke-EnhancementDisplayTransaction $file ([byte[]](7,8)) $false {};"
                  "if(([IO.File]::ReadAllBytes($file)-join ',') -ne '7,8'){throw 'Normal launch value missing'};"
                  "'RESTRICTED_DISPLAY PASS verify_restore=exact normal_write=exact'"
                  "}finally{[IO.Directory]::SetAccessControl($dir,$old)}")
            result=subprocess.run(['powershell.exe','-NoProfile','-Command',code],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('RESTRICTED_DISPLAY PASS',result.stdout)
            self.assertEqual(ini.read_bytes(),bytes([7,8]))

    def test_verify_restores_exact_original_bytes_on_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='verify-transaction-') as d:
            root = Path(d); ini = root/'display.ini'; ini.write_bytes(b'\x00original\r\n\xff')
            result = self.run_transaction(root, True, "if(([IO.File]::ReadAllBytes($p) -join ',') -ne '4,5,6'){throw 'Candidate not active'};'ACTION_PASS'")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('ACTION_PASS', result.stdout)
            self.assertEqual(ini.read_bytes(), b'\x00original\r\n\xff')
            self.assertEqual([f.name for f in root.iterdir()], ['display.ini'])

    def test_verify_restores_on_action_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='verify-transaction-') as d:
            root = Path(d); ini = root/'display.ini'; ini.write_bytes(b'original')
            result = self.run_transaction(root, True, "throw 'Owned verifier failed'")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Owned verifier failed', result.stderr)
            self.assertEqual(ini.read_bytes(), b'original')
            self.assertEqual([f.name for f in root.iterdir()], ['display.ini'])

    def test_normal_launch_keeps_selected_configuration(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='verify-transaction-') as d:
            root = Path(d); ini = root/'display.ini'; ini.write_bytes(b'original')
            result = self.run_transaction(root, False, "'ACTION_PASS'")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(ini.read_bytes(), bytes([4, 5, 6]))

    def test_foreign_change_is_preserved_not_overwritten_by_restore(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='verify-transaction-') as d:
            root = Path(d); ini = root/'display.ini'; ini.write_bytes(b'original')
            result = self.run_transaction(root, True, "[IO.File]::WriteAllBytes($p,[byte[]](9,8,7))")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Display configuration changed during verification', result.stderr)
            self.assertEqual(ini.read_bytes(), bytes([9, 8, 7]))


class SharedVerifyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='owned-verify-exe-')
        cls.directory = Path(cls.temporary.name).resolve()
        assert cls.directory.is_relative_to((ROOT/'build').resolve())
        cls.exe = cls.directory/'owned-verifier.exe'
        source = ('public class OwnedVerifier { public static int Main(string[] args) {'
                  'if(System.Array.IndexOf(args,"--verify-only")<0)return 88;'
                  'string capture=System.Environment.GetEnvironmentVariable("OWNED_CAPTURE_FILE");'
                  'if(capture!=null)System.IO.File.WriteAllText(capture,System.String.Join("|",args)+"|MC_FREE_VIEW="+System.Environment.GetEnvironmentVariable("MC_FREE_VIEW")+"|MC_WINDOWED="+System.Environment.GetEnvironmentVariable("MC_WINDOWED")+"|MC_WINDOW_RESOLUTION="+System.Environment.GetEnvironmentVariable("MC_WINDOW_RESOLUTION")+"|MC_MOTION60_COMPLETE="+System.Environment.GetEnvironmentVariable("MC_MOTION60_COMPLETE")+"|MC_FIELD_RETURN_HEIGHT="+System.Environment.GetEnvironmentVariable("MC_FIELD_RETURN_HEIGHT")+"|MC_GUI_PARENT_GUARD="+System.Environment.GetEnvironmentVariable("MC_GUI_PARENT_GUARD")+"|MC_SCENE_LOADING="+System.Environment.GetEnvironmentVariable("MC_SCENE_LOADING")+"|MC_NATIVE_SCENE_LOADING="+System.Environment.GetEnvironmentVariable("MC_NATIVE_SCENE_LOADING")+"|MC_SCALED_FONT="+System.Environment.GetEnvironmentVariable("MC_SCALED_FONT")+"|MC_SCALED_FONT_ASSETS="+System.Environment.GetEnvironmentVariable("MC_SCALED_FONT_ASSETS"));'
                  'string code=System.Environment.GetEnvironmentVariable("OWNED_VERIFY_EXIT");'
                  'return code=="7"?7:0; }}')
        command = "Add-Type -TypeDefinition '"+source+"' -OutputAssembly '"+str(cls.exe)+"' -OutputType ConsoleApplication"
        result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def fixture(self, root):
        storage_env=patch.dict(os.environ, {'LOCALAPPDATA':str(root/'user data')});storage_env.start();self.addCleanup(storage_env.stop)
        (root/'data').mkdir(); (root/'config/profiles').mkdir(parents=True); (root/'modules').mkdir()
        start = Path(os.environ.get('TRANSACTION_START_SOURCE', ROOT/'src/configuration/StartShared.ps1'))
        module = Path(os.environ.get('TRANSACTION_MODULE_SOURCE', MODULE))
        shutil.copyfile(start, root/'Start.ps1')
        shutil.copyfile(module, root/'config/EnhancementSettings.psm1')
        shutil.copyfile(self.exe, root/'modules/workspace_launcher.exe')
        (root/'data/DDrawCompat-MagnaCarta.ini').write_bytes(b'owned baseline\r\n')
        profiles = {}
        for name in ['baseline', 'render4k', 'wide4k', 'fps60', 'combined']:
            value = b'owned baseline\r\n' if name == 'baseline' else ('owned '+name+'\r\n').encode()
            (root/'config/profiles'/f'{name}.ini').write_bytes(value)
            profiles[name] = hashlib.sha256(value).hexdigest()
        (root/'config/enhancements.json').write_text(json.dumps(dict(schema=1,display_profile='wide4k',motion60=False,native_gamepad=False)))
        (root/'config/profile-base.bin').write_bytes(bytes(52))
        (root/'config/PrepareProfile.ps1').write_text('function Convert-CompatibilityProfile([byte[]]$Value){return ,$Value}')
        (root/'runtime.json').write_text(json.dumps({'schema': 1, 'data': {}, 'files': {}, 'profiles': profiles,
                'recipes': {'configured': {'module': 'configured'}}, 'configured_modules': {'display': 'display'}}))

    def run_shared(self, fail):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='verify-shared-') as d:
            root = Path(d); self.fixture(root)
            env = os.environ.copy(); env['OWNED_VERIFY_EXIT'] = '7' if fail else '0'
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                     str(root/'Start.ps1'), '-VerifyOnly'], capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(result.returncode == 0, not fail, result.stdout+result.stderr)
            if fail:
                self.assertIn('Shared launcher exit=7', result.stderr)
            self.assertEqual((root/'data/DDrawCompat-MagnaCarta.ini').read_bytes(), b'owned baseline\r\n',
                             'VerifyOnly left the selected candidate INI in game data')

    def test_real_shared_script_restores_ini_on_success(self):
        self.run_shared(False)

    def test_real_shared_script_restores_ini_on_verifier_failure(self):
        self.run_shared(True)

    def test_material_settings_reach_real_shared_entry_arguments_and_environment(self):
        import sys
        sys.path.insert(0, str(ROOT/'tools'))
        from build_configuration_profiles import profiles
        cases=[('1080p','fullscreen',30,False,False),('2k','windowed',60,True,True),
               ('4k','borderless',30,True,False),('auto','fullscreen',60,False,True),
               ('auto','windowed',30,False,True),('2k','borderless',60,False,False)]
        for resolution, mode, fps, pad, camera in cases:
            with self.subTest(resolution=resolution, mode=mode, fps=fps), tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='material-entry-') as d:
                root=Path(d);self.fixture(root)
                manifest=json.loads((root/'runtime.json').read_text())
                for name,data,_ in profiles():
                    (root/'config/profiles'/(name+'.ini')).write_bytes(data)
                    manifest['profiles'][name]=hashlib.sha256(data).hexdigest()
                (root/'runtime.json').write_text(json.dumps(manifest))
                window_size='1600x900' if resolution=='2k' else '1280x720'
                (root/'config/enhancements.json').write_text(json.dumps(dict(schema=2,resolution=resolution,window_mode=mode,window_resolution=window_size,frame_rate=fps,native_gamepad=pad,free_view=camera)))
                capture=root/'actual.txt';env=os.environ.copy();env['OWNED_CAPTURE_FILE']=str(capture)
                env['MC_FREE_VIEW']='parent';env['MC_WINDOWED']='parent';env['MC_MOTION60_COMPLETE']='parent'
                result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'Start.ps1'),'-VerifyOnly'],capture_output=True,text=True,env=env,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                actual=capture.read_text()
                self.assertIn('module=configuration',result.stdout)
                self.assertIn('configuration.dll',actual)
                self.assertIn('--display-profile|md3-'+resolution+'-'+mode+'-'+str(fps),actual)
                self.assertNotIn('--native-gamepad',actual)
                self.assertNotIn('--input-passthrough',actual)
                self.assertIn('MC_FREE_VIEW=0',actual)
                self.assertIn('MC_WINDOWED='+str(int(mode=='windowed')),actual)
                self.assertIn('MC_WINDOW_RESOLUTION='+(window_size if mode=='windowed' else '')+'|',actual)
                self.assertIn('MC_MOTION60_COMPLETE='+str(int(fps==60)),actual)
                self.assertEqual((root/'data/DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned baseline\r\n')
