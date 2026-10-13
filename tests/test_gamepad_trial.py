from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import prepare_gamepad_trial as trial
class GamepadTrialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='gamepad-entry-fixture-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'candidate';r=self.root/'.advanced-runtime';r.mkdir(parents=True);self.r=r
        for n in ('motion-trial.json','StartTitle.ps1','StartAdvanced.ps1','manifest.json','workspace_profile.dll','workspace_launcher.exe','title-background.json'):(r/n).write_bytes(b'owned noncommercial fixture')
        stub="param([string]$Mode,[switch]$PrepareOnly)\nif(-not $PrepareOnly){throw 'must not launch'}\n$s=Join-Path $PSScriptRoot ('session-'+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory $s|Out-Null;Write-Output ('ADVANCED_PREPARED PASS mode='+$Mode+' game_started=false session='+$s)\n"
        (r/'StartMotion.ps1').write_text(stub,encoding='utf-8-sig');self.lock=trial.write_entrypoints(self.root)
    def run_script(self,args=''):
        return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.r/'StartGamepad.ps1'),'-PrepareOnly',*args.split()],capture_output=True,text=True)
    def test_prepare_native(self):
        p=self.run_script();self.assertEqual(p.returncode,0,p.stderr);self.assertIn('native_enabled=True game_started=false',p.stdout)
    def test_prepare_off(self):
        p=self.run_script('-NoGamepad');self.assertEqual(p.returncode,0,p.stderr);self.assertIn('native_enabled=False game_started=false',p.stdout)
    def test_tool_drift_rejects(self):
        (self.r/'workspace_profile.dll').write_bytes(b'drift');p=self.run_script();self.assertNotEqual(p.returncode,0);self.assertNotIn('ADVANCED_PREPARED',p.stdout)
    def test_entrypoints_and_pending_acceptance(self):
        for name in ('Play-Xbox.cmd','Play-keyboard-mouse.cmd','Play-Xbox-30fps.cmd'):self.assertIn(b'StartGamepad.ps1',(self.root/name).read_bytes())
        self.assertFalse(self.lock['in_game_verified']);self.assertFalse(self.lock['physical_controller_verified'])
    def test_cli_sets_native_flag_explicitly(self):
        s=(ROOT/'src/runtime/workspace_launcher.cpp').read_text();self.assertIn('arg == L"--native-gamepad"',s);self.assertIn('L"MC_GAMEPAD_NATIVE",nativeGamepad?L"1":L"0"',s)
if __name__=='__main__':unittest.main()
