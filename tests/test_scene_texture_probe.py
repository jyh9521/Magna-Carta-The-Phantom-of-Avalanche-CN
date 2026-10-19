"""Owned orchestration fixtures; actual offscreen results are separate evidence."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import check_scene_texture_lifecycle as t
class SceneTextureProbeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.driver=self.root/'driver.dll';self.driver.write_bytes(b'owned driver')
        self.probe=self.root/'probe.exe';self.probe.write_bytes(b'owned probe')
        self.ddraw=self.root/'ddraw.dll';self.ddraw.write_bytes(b'owned system API')
    def run_mode(self,mode,report=None):return t.observe(self.driver,self.probe,self.ddraw,mode,report)
    def native(self,mode,exit=0):
        return SimpleNamespace(returncode=exit,stderr='',stdout='NATIVE_TEXTURE_REFS after_bind=2\nNATIVE_TEXTURE_RESULT mode='+mode+' cycles=200 residual_bound_after_delete='+('0' if mode=='candidate' else '200')+'\nNATIVE_TEXTURE_OBSERVATION_PASS access_violation=false retained_reference_is_not_uaf=true game_crash_reproduced=false rollback=exact\n')
    def test_unknown_driver_rejected_before_execution(self):
        with patch.object(t.subprocess,'run') as run:
            with self.assertRaises(ValueError):self.run_mode('baseline')
            run.assert_not_called()
    def test_all_modes_keep_observation_separate_from_game_crash_proof(self):
        for mode in t.MODES:
            with self.subTest(mode=mode),patch.object(t,'DRIVER_SHA',hashlib.sha256(self.driver.read_bytes()).hexdigest()),patch.object(t.subprocess,'run',return_value=self.native(mode)) as run:
                report=self.root/(mode+'.json');r=self.run_mode(mode,report)
                self.assertTrue(r['observation_verified']);self.assertFalse(r['game_crash_reproduced']);self.assertFalse(r['game_started'])
                self.assertEqual(json.loads(report.read_text())['mode'],mode)
                args=run.call_args.args[0];self.assertEqual('--'+mode in args,mode!='candidate')
    def test_access_violation_not_reported_as_success(self):
        with patch.object(t,'DRIVER_SHA',hashlib.sha256(self.driver.read_bytes()).hexdigest()),patch.object(t.subprocess,'run',return_value=self.native('baseline',0xc0000005)):
            with self.assertRaises(RuntimeError):self.run_mode('baseline')
    def test_wrong_mode_output_rejected(self):
        with patch.object(t,'DRIVER_SHA',hashlib.sha256(self.driver.read_bytes()).hexdigest()),patch.object(t.subprocess,'run',return_value=self.native('candidate')):
            with self.assertRaises(RuntimeError):self.run_mode('baseline')
    def test_report_never_overwritten(self):
        report=self.root/'report.json';report.write_bytes(b'preserve')
        with patch.object(t,'DRIVER_SHA',hashlib.sha256(self.driver.read_bytes()).hexdigest()),patch.object(t.subprocess,'run') as run:
            with self.assertRaises(ValueError):self.run_mode('baseline',report)
            run.assert_not_called()
        self.assertEqual(report.read_bytes(),b'preserve')
    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):self.run_mode('invented')
if __name__=='__main__':unittest.main()
