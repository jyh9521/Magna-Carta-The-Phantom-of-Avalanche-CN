"""Owned micro-runtime transactions; never deploy to the player's runtime."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import prepare_field_return_trial as trial

START = """param([string]$SettingsFile='')
$module='configuration'
$ini=Join-Path $game 'DDrawCompat-MagnaCarta.ini'
$environment=@{}
foreach($key in @('MC_WINDOWED','MC_WINDOW_RESOLUTION')){$environment[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
try{
 $env:MC_WINDOW_RESOLUTION=''
}finally{
 foreach($key in $environment.Keys){[Environment]::SetEnvironmentVariable($key,$environment[$key],'Process')}
}
""".replace('\n', '\r\n').encode('utf8')


class FieldReturnTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root/'runtime'; self.runtime.mkdir()
        (self.runtime/'modules').mkdir(); (self.runtime/'data').mkdir()
        (self.runtime/'data/MC00.sav').write_bytes(b'owned save do not change')
        (self.runtime/'modules/configuration.dll').write_bytes(b'owned accepted module')
        (self.runtime/'Start.ps1').write_bytes(START)
        (self.runtime/'Play.cmd').write_bytes(b'owned default entry')
        (self.runtime/'config').mkdir()
        (self.runtime/'config/enhancements.json').write_bytes(b'owned settings')
        files = {name: trial.digest((self.runtime/name).read_bytes()) for name in (
            'Start.ps1', 'modules/configuration.dll', 'Play.cmd', 'config/enhancements.json')}
        self.manifest = {'schema': 1, 'files': files, 'recipes': {'configured': {'module': 'configuration'}},
                         'data': {'MC00.sav': trial.digest((self.runtime/'data/MC00.sav').read_bytes())}}
        (self.runtime/'runtime.json').write_bytes((json.dumps(self.manifest)+'\n').encode('utf8'))
        self.module = self.root/'workspace_profile.dll'; self.module.write_bytes(b'owned candidate module')
        self.record = self.root/'record'
        self.before = self.snapshot()

    def snapshot(self):
        return {p.relative_to(self.runtime).as_posix(): p.read_bytes()
                for p in self.runtime.rglob('*') if p.is_file()}

    def install(self):
        return trial.prepare(self.runtime, self.module, self.record)

    def update_manifest(self):
        (self.runtime/'runtime.json').write_text(json.dumps(self.manifest), encoding='utf8')

    def test_install_keeps_default_and_only_adds_opt_in_candidate(self):
        transaction = self.install()
        self.assertEqual(len(transaction['changes']), 4)
        manifest = json.loads((self.runtime/'runtime.json').read_bytes())
        self.assertEqual(manifest['recipes'], self.manifest['recipes'])
        self.assertEqual(manifest['data'], self.manifest['data'])
        self.assertEqual(manifest['field_return_height_module'], 'field-return-height')
        for name in set(self.before)-{'Start.ps1', 'runtime.json'}:
            self.assertEqual((self.runtime/name).read_bytes(), self.before[name])
        start = (self.runtime/'Start.ps1').read_bytes()
        self.assertIn(b'[switch]$FieldReturnHeight', start)
        self.assertIn(b"$env:MC_FIELD_RETURN_HEIGHT=if($FieldReturnHeight){'1'}else{'0'}", start)
        self.assertIn(b"'MC_WINDOW_RESOLUTION','MC_FIELD_RETURN_HEIGHT'", start)
        self.assertIn(b'if($FieldReturnHeight){if(-not $manifest.field_return_height_module)', start)
        self.assertIn(b'foreach($key in $environment.Keys)', start)
        self.assertIn(b'-FieldReturnHeight', (self.runtime/'Play-stairwell-fix.cmd').read_bytes())
        self.assertEqual((self.runtime/'modules/field-return-height.dll').read_bytes(), self.module.read_bytes())
        trial.validate_manifest(self.runtime, manifest)

    def test_rollback_restores_every_original_byte_and_removes_only_own_additions(self):
        self.install()
        trial.rollback(self.record)
        self.assertEqual(self.snapshot(), self.before)
        self.assertTrue((self.record/'changes.json').is_file())
        with self.assertRaises(ValueError):
            trial.rollback(self.record)

    def test_existing_record_or_destinations_rejected(self):
        self.record.mkdir()
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(self.snapshot(), self.before)
        self.record.rmdir()
        destination = self.runtime/'modules/field-return-height.dll'
        destination.write_bytes(b'foreign')
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(destination.read_bytes(), b'foreign')

    def test_installed_runtime_cannot_be_reentered(self):
        self.install(); before = self.snapshot()
        with self.assertRaises(ValueError):
            trial.prepare(self.runtime, self.module, self.root/'other-record')
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root/'other-record').exists())

    def test_initial_digest_drift_rejected_before_record_creation(self):
        (self.runtime/'Start.ps1').write_bytes(START+b'# drift')
        with self.assertRaisesRegex(ValueError, 'input changed'): self.install()
        self.assertFalse(self.record.exists())

    def test_unknown_or_duplicate_launcher_anchor_rejected(self):
        for bad in (START.replace(b"[string]$SettingsFile='')", b'param()'),
                    START+b"\n$ini=Join-Path $game 'DDrawCompat-MagnaCarta.ini'\n",
                    START.replace(b'foreach($key in $environment.Keys)', b'foreach($key in @())')):
            with self.subTest(start=bad):
                (self.runtime/'Start.ps1').write_bytes(bad)
                self.manifest['files']['Start.ps1'] = trial.digest(bad)
                self.update_manifest()
                with self.assertRaisesRegex(ValueError, 'anchor'): self.install()
                self.assertFalse(self.record.exists())

    def test_unknown_schema_and_untracked_start_rejected(self):
        self.manifest['schema'] = 2; self.update_manifest()
        with self.assertRaises(ValueError): self.install()
        self.manifest['schema'] = 1; del self.manifest['files']['Start.ps1']; self.update_manifest()
        with self.assertRaises(ValueError): self.install()
        self.assertFalse(self.record.exists())

    def test_unsafe_manifest_paths_and_source_inside_runtime_rejected(self):
        for name in ('../escape', '/absolute', 'modules\\other', 'C:/absolute', 'modules/./other'):
            self.manifest['files'][name] = '0'*64; self.update_manifest()
            with self.subTest(path=name), self.assertRaises(ValueError): self.install()
            del self.manifest['files'][name]
        self.update_manifest()
        with self.assertRaisesRegex(ValueError, 'outside runtime'):
            trial.prepare(self.runtime, self.runtime/'modules/configuration.dll', self.record)
        with self.assertRaisesRegex(ValueError, 'outside runtime'):
            trial.prepare(self.runtime, self.module, self.runtime/'record')

    def test_drift_and_tampered_backup_block_entire_rollback(self):
        self.install()
        candidate = self.runtime/'modules/field-return-height.dll'
        candidate.write_bytes(b'foreign drift'); before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'drift'): trial.rollback(self.record)
        self.assertEqual(self.snapshot(), before)
        candidate.write_bytes(self.module.read_bytes())
        (self.record/'before/Start.ps1').write_bytes(b'tampered')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'backup changed'): trial.rollback(self.record)
        self.assertEqual(self.snapshot(), before)

    def test_install_write_failure_restores_complete_baseline(self):
        original = trial.write_file; failed = False
        def failing(path, data):
            nonlocal failed
            if path == self.runtime/'runtime.json' and not failed:
                failed = True
                raise OSError('injected installation failure')
            return original(path, data)
        with patch.object(trial, 'write_file', side_effect=failing):
            with self.assertRaisesRegex(OSError, 'injected'): self.install()
        self.assertEqual(self.snapshot(), self.before)

    def test_rollback_write_failure_retains_complete_candidate(self):
        self.install(); before = self.snapshot()
        original = trial.write_file; failed = False
        def failing(path, data):
            nonlocal failed
            if path == self.runtime/'runtime.json' and not failed:
                failed = True
                raise OSError('injected rollback failure')
            return original(path, data)
        with patch.object(trial, 'write_file', side_effect=failing):
            with self.assertRaisesRegex(OSError, 'injected'): trial.rollback(self.record)
        self.assertEqual(self.snapshot(), before)
        trial.rollback(self.record)
        self.assertEqual(self.snapshot(), self.before)

    def test_symlink_or_junction_source_rejected(self):
        link = self.root/'linked-module.dll'
        try:
            os.symlink(self.module, link)
        except (OSError, NotImplementedError):
            self.skipTest('Host does not allow creating a symlink fixture')
        with self.assertRaisesRegex(ValueError, 'Reparse'):
            trial.prepare(self.runtime, link, self.record)
        self.assertFalse(self.record.exists())

    def test_windows_reparse_attribute_on_source_or_parent_rejected(self):
        real_lstat = Path.lstat
        for guarded in (self.module, self.runtime/'modules'):
            def lstat(path, *args, **kwargs):
                info = real_lstat(path, *args, **kwargs)
                if path == guarded:
                    return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                return info
            with self.subTest(path=guarded), patch.object(Path, 'lstat', autospec=True, side_effect=lstat):
                with self.assertRaisesRegex(ValueError, 'Reparse'): self.install()
            self.assertFalse(self.record.exists())
        self.assertEqual(self.snapshot(), self.before)

    def test_cli_install_and_rollback(self):
        script = ROOT/'tools/prepare_field_return_trial.py'
        command = [sys.executable, str(script), '--runtime', str(self.runtime),
                   '--module', str(self.module), '--record', str(self.record)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('default=baseline', result.stdout)
        result = subprocess.run([sys.executable, str(script), '--rollback', str(self.record)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('original_bytes=restored', result.stdout)
        self.assertEqual(self.snapshot(), self.before)


if __name__ == '__main__':
    unittest.main()
