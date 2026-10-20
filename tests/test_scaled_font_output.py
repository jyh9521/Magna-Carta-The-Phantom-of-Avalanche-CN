import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import update_scaled_font_output as tool
from check_scaled_font_runtime import check

ROOT=Path(__file__).resolve().parents[1]


class OutputTests(unittest.TestCase):
    def test_output_policy_matrix(self):
        exe=ROOT/'build/native/Release/scaled_font_output_fixture.exe'
        if not exe.exists():self.skipTest('build output fixture first')
        p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertIn('cases=72 laptop=2880x1800',p.stdout)
    def test_low_logical_target_high_presentation_three_states(self):
        if not (ROOT/'build/native/Release/scaled_font_runtime_fixture.exe').exists():self.skipTest('build native fixture first')
        for mode,n in [('baseline',0),('modified',40),('rollback',0)]:
            r=check(mode,presentation=True);self.assertIn(f'hd_textures={n}',r['result'])
            if mode=='modified':
                self.assertIn('output=2880x1800 logical=800x600 enabled=true',r['stdout'])
                self.assertIn('output=1920x1080 logical=1920x1080 enabled=false',r['stdout'])


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='owned-output-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'runtime';(self.root/'modules').mkdir(parents=True)
        self.native=self.base/'native';self.native.mkdir();self.record=self.base/'record'
        old=b'owned previous C module';launcher=b'owned old launcher'
        for p,b in [('modules/scaled-font.dll',old),('modules/workspace_launcher.exe',launcher),('Play.cmd',b'owned unchanged entry'),('MC00.sav',b'owned save')]:
            (self.root/p).write_bytes(b)
        m=dict(schema=1,scaled_font=dict(schema=1,enabled=True,module='scaled-font',scale=4),files={p:tool.digest((self.root/p).read_bytes()) for p in ('modules/scaled-font.dll','modules/workspace_launcher.exe')})
        # The generic manifest validator requires the existing Start digest.
        (self.root/'Start.ps1').write_bytes(b'owned entry');m['files']['Start.ps1']=tool.digest(b'owned entry')
        (self.root/'runtime.json').write_text(json.dumps(m),encoding='utf8')
        (self.native/'workspace_profile.dll').write_bytes(b'MZ'+'launcher_output_snapshot'.encode('utf-16le'))
        (self.native/'workspace_launcher.exe').write_bytes(b'MZSCALED_FONT_OUTPUT')
        a=patch.object(tool,'BASE_MODULE',tool.digest(old));a.start();self.addCleanup(a.stop)
        a=patch.object(tool,'idle');a.start();self.addCleanup(a.stop)
        self.before=self.snapshot()
    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def update(self):return tool.update(self.root,self.native,self.record)
    def test_update_and_rollback_exact(self):
        self.update();m=json.loads((self.root/'runtime.json').read_bytes());self.assertEqual(m['scaled_font_output']['source'],'launcher_display_snapshot')
        self.assertEqual((self.root/'MC00.sav').read_bytes(),self.before['MC00.sav']);tool.rollback(self.record);self.assertEqual(self.snapshot(),self.before)
    def test_unknown_baseline_preserved(self):
        with patch.object(tool,'BASE_MODULE','0'*64),self.assertRaises(ValueError):self.update()
        self.assertEqual(self.snapshot(),self.before)
    def test_partial_write_compensation(self):
        real=tool.write_file
        def fail(p,b):
            if p==self.root/'modules/workspace_launcher.exe':raise OSError('owned write failure')
            real(p,b)
        with patch.object(tool,'write_file',side_effect=fail),self.assertRaises(OSError):self.update()
        self.assertEqual(self.snapshot(),self.before)
    def test_wrong_candidate_pair_rejected(self):
        (self.native/'workspace_launcher.exe').write_bytes(b'old launcher')
        with self.assertRaises(ValueError):self.update()
        self.assertEqual(self.snapshot(),self.before)
    def test_foreign_rollback_target_preserved(self):
        self.update();(self.root/'modules/scaled-font.dll').write_bytes(b'foreign');now=self.snapshot()
        with self.assertRaises(ValueError):tool.rollback(self.record)
        self.assertEqual(self.snapshot(),now)
    def test_backup_drift_preserved(self):
        self.update();(self.record/'original/modules/scaled-font.dll').write_bytes(b'foreign');now=self.snapshot()
        with self.assertRaises(ValueError):tool.rollback(self.record)
        self.assertEqual(self.snapshot(),now)
    def test_reentry_rejected(self):
        self.update();now=self.snapshot()
        with self.assertRaises(ValueError):tool.update(self.root,self.native,self.base/'second')
        self.assertEqual(self.snapshot(),now)
