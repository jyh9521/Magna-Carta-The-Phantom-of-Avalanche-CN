import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_advanced_trial as trial


class AdvancedTrialTests(unittest.TestCase):
    def setUp(self):
        build = Path(__file__).resolve().parents[1] / 'build'
        build.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=build, prefix='advanced-fixture-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.native = self.root / 'native'
        self.output = self.root / 'candidate'
        self.source.mkdir()
        self.native.mkdir()
        (self.source / '.locale-runtime').mkdir()
        stub = """param([switch]$PrepareOnly,[string]$SettingsFile)
if (-not $PrepareOnly) { throw 'Fixture must never launch.' }
$s=Join-Path $PSScriptRoot ('session-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $s | Out-Null
[IO.File]::WriteAllBytes((Join-Path $s 'profile.bin'),[byte[]](1,2,3))
Write-Output ('LOCALE_START_PREPARED game_started=false session='+$s)
"""
        for name, data in {
            '.locale-runtime/Start.ps1': stub.encode(),
            '.locale-runtime/PrepareProfile.ps1': b'# fixture',
            '.locale-install.json': b'{"state":"candidate"}',
            trial.render.graphics.STATE_NAME: b'fixture marker',
            trial.render.CONFIG_NAME: trial.render.BASELINE,
            'MagnaCarta.exe': b'not executable - owned test data',
            'save.dat': b'preserve me',
        }.items():
            (self.source / name).write_bytes(data)
        for name in ('workspace_launcher.exe','workspace_profile.dll'):
            (self.native / name).write_bytes(b'not executable - owned runtime data')
        hashes = {n: trial.prepare_workspace.digest(self.source/n)
                  for n in ('MagnaCarta.exe',trial.render.CONFIG_NAME)}
        for p in (patch.object(trial.render,'SOURCE_HASHES',hashes),
                  patch.object(trial.render,'checked_source',side_effect=lambda p: Path(p).resolve())):
            p.start()
            self.addCleanup(p.stop)

    def run_entry(self,*args):
        return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass',
            '-File',str(self.output/'.advanced-runtime/StartAdvanced.ps1'),*args],
            capture_output=True,text=True,timeout=30)

    def test_five_modes_prepare_and_rollback_owned_fixture(self):
        trial.prepare(self.source,self.native,self.output)
        for mode,data in trial.render.PROFILES.items():
            result=self.run_entry('-Mode',mode,'-PrepareOnly')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('game_started=false',result.stdout)
            self.assertEqual((self.output/trial.render.CONFIG_NAME).read_bytes(),data)
            self.assertTrue((self.output/('Play-'+mode+'.cmd')).is_file())
        result=self.run_entry('-Rollback')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.output/trial.render.CONFIG_NAME).read_bytes(),trial.render.BASELINE)
        self.assertEqual((self.output/'save.dat').read_bytes(),b'preserve me')
        self.assertEqual((self.source/trial.render.CONFIG_NAME).read_bytes(),trial.render.BASELINE)
        script=(self.output/'.advanced-runtime/StartAdvanced.ps1').read_text(encoding='utf-8-sig')
        self.assertNotIn('--modern-input',script)

    def test_unknown_ini_is_rejected(self):
        trial.prepare(self.source,self.native,self.output)
        (self.output/trial.render.CONFIG_NAME).write_bytes(b'unknown')
        result=self.run_entry('-PrepareOnly')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Unknown active INI',result.stderr)

    def test_case_normalized_and_failed_launcher_restores_baseline(self):
        trial.prepare(self.source,self.native,self.output)
        result=self.run_entry('-Mode','WIDE4K','-PrepareOnly')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('mode=wide4k',result.stdout)
        result=self.run_entry('-Mode','wide4k')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((self.output/trial.render.CONFIG_NAME).read_bytes(),trial.render.BASELINE)
        records=list((self.output/'.advanced-runtime').glob('session-*/result.json'))
        states=[json.loads(p.read_text(encoding='utf-8-sig')) for p in records]
        self.assertTrue(any(s.get('failed') and s.get('restored_baseline') for s in states))

    def test_changed_runtime_is_rejected(self):
        trial.prepare(self.source,self.native,self.output)
        (self.output/'.advanced-runtime/workspace_profile.dll').write_bytes(b'changed')
        result=self.run_entry('-Rollback')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Changed input',result.stderr)

    def test_existing_or_outside_output_is_rejected(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            trial.prepare(self.source,self.native,self.output)
        with self.assertRaises(ValueError):
            trial.prepare(self.source,self.native,Path(tempfile.gettempdir())/'outside-trial')

    def test_source_change_is_rejected(self):
        trial.prepare(self.source,self.native,self.output)
        (self.source/'MagnaCarta.exe').write_bytes(b'changed')
        result=self.run_entry('-PrepareOnly')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Changed input',result.stderr)


if __name__=='__main__':
    unittest.main()
