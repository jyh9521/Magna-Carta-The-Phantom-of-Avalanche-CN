import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import prepare_motion_trial as trial

class MotionTrialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='motion-trial-fixture-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        def fake_build(source,native,locale,output):
            r=output/'.advanced-runtime';r.mkdir(parents=True)
            for name in ('manifest.json','workspace_profile.dll','workspace_launcher.exe','title-background.json'):
                (r/name).write_bytes(b'owned noncommercial fixture')
            stub="param([string]$Mode,[switch]$PrepareOnly,[switch]$Rollback)\nif(-not $PrepareOnly -and -not $Rollback){throw 'Fixture must not launch'}\nWrite-Output ('MOTION_PREPARED mode='+$Mode+' complete='+$env:MC_MOTION60_COMPLETE+' game_started=false')\n"
            for name in ('StartTitle.ps1','StartAdvanced.ps1'):(r/name).write_text(stub,encoding='utf-8-sig')
        with patch.object(trial.title,'build',fake_build):self.lock=trial.prepare(self.root,self.root,self.root,self.root/'candidate')
        self.runtime=self.root/'candidate/.advanced-runtime'
    def run_script(self,arguments=''):
        p=self.runtime/'StartMotion.ps1'
        script="$env:MC_MOTION60_COMPLETE='sentinel'; & '"+str(p)+"' "+arguments+"; if($?){Write-Output ('AFTER='+$env:MC_MOTION60_COMPLETE)}else{exit 1}"
        return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',script],capture_output=True,text=True)
    def test_full_mode_and_environment_restore(self):
        r=self.run_script('-Mode combined -PrepareOnly');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('complete=1 game_started=false',r.stdout);self.assertIn('AFTER=sentinel',r.stdout)
    def test_legacy_comparison_clears_full_motion(self):
        r=self.run_script('-Mode combined -LegacyPose -PrepareOnly');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('complete=0 game_started=false',r.stdout)
    def test_30fps_comparison_same_widescreen(self):
        r=self.run_script('-Mode wide4k -PrepareOnly');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('mode=wide4k complete=0',r.stdout)
    def test_rollback_disables_feature(self):
        r=self.run_script('-Rollback');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('complete=0',r.stdout)
    def test_drift_rejects_before_nested_script(self):
        (self.runtime/'workspace_profile.dll').write_bytes(b'drift')
        r=self.run_script('-PrepareOnly');self.assertNotEqual(r.returncode,0);self.assertNotIn('MOTION_PREPARED',r.stdout)
    def test_manifest_does_not_claim_live_acceptance(self):
        saved=json.loads((self.runtime/'motion-trial.json').read_text());self.assertFalse(saved['in_game_verified']);self.assertEqual(saved['logic_interval_ms'],33)
    def test_four_entrypoints(self):
        for name in ('Play-30fps.cmd','Play-60fps-legacy.cmd','Play-60fps-complete.cmd','Rollback-motion.cmd'):
            self.assertIn(b'StartMotion.ps1',(self.root/'candidate'/name).read_bytes())

if __name__=='__main__':unittest.main()
