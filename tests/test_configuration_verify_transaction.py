from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT/'src/configuration/EnhancementSettings.psm1'


class ConfigurationVerifyTransactionTests(unittest.TestCase):
    def run_transaction(self, folder, restore, action):
        code = ("$ErrorActionPreference='Stop';Import-Module '"+str(MODULE)+"' -Force;"
                "$p='"+str(folder/'display.ini')+"';"
                "Invoke-EnhancementDisplayTransaction $p ([byte[]](4,5,6)) $"+str(restore).lower()+" {"+action+"}")
        return subprocess.run(['powershell.exe', '-NoProfile', '-Command', code], capture_output=True, text=True, timeout=20)

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
