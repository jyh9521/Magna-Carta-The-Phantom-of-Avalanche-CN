import copy
import json
from pathlib import Path
import tempfile
import stat
import unittest
from unittest.mock import patch

import audit_image_resources as audit
import deploy_image_runtime as deploy
from resource_image import parse
from test_resource_image import tga


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'BGR').mkdir()
        self.raw=tga(width=80,height=40);self.name='BGR/0000.BGR'
        (self.root/self.name).write_bytes(self.raw)
        self.plans=dict(resources=[dict(resource=self.name,source_sha256=audit.sha(self.raw),
                         plans=[dict(mask_xyxy=[10,10,30,30])])])
        self.groups=dict(groups=[]);self.checks={}

    def run_audit(self):
        return audit.audit({self.name:self.raw},self.root,self.plans,self.groups,self.checks)

    def change(self,x,y,pixel):
        i=parse(self.raw);p=bytearray(i.rgba());at=(y*80+x)*4;p[at:at+4]=pixel
        (self.root/self.name).write_bytes(i.replace_rgba(p).to_bytes())

    def test_rgb_only_change_outside_mask_is_detected(self):
        self.change(1,1,bytes([99,2,1,4]))
        self.assertEqual(self.run_audit()['errors'][0]['kind'],'outside_reviewed_masks')

    def test_inside_mask_allowed_and_protected_corner_enforced(self):
        self.change(12,12,bytes([99,2,1,4]));self.assertFalse(self.run_audit()['errors'])
        self.plans['resources'][0]['plans'][0]['protected_rects_xyxy']=[[10,10,15,15]]
        self.assertEqual(self.run_audit()['errors'][0]['kind'],'protected_artwork')

    def test_unreviewed_and_missing_images_detected(self):
        self.plans['resources']=[];self.change(12,12,bytes([99,2,1,4]))
        self.assertEqual(self.run_audit()['errors'][0]['kind'],'unreviewed_change')
        (self.root/self.name).unlink();self.assertEqual(self.run_audit()['errors'][0]['kind'],'inventory')

    def test_source_binding_and_approved_replacement_cannot_drift(self):
        self.plans['resources'][0]['source_sha256']='0'*64
        with self.assertRaises(ValueError):self.run_audit()
        self.checks['approved_replacements']=[dict(resource=self.name,source_sha256=audit.sha(self.raw),
             target_sha256='0'*64,dimensions=[80,40])]
        self.assertEqual(self.run_audit()['errors'][0]['kind'],'approved_replacement_drift')

    def test_original_alpha_invariant_detects_filled_corner(self):
        self.checks['checks']=[dict(resource=self.name,kind='alpha',regions_xyxy=[[10,10,15,15]],meaning='silhouette')]
        self.change(12,12,bytes([3,2,1,255]))
        self.assertEqual(self.run_audit()['errors'][0]['kind'],'invariant')

    def test_overlay_does_not_write_to_workspace(self):
        i=parse(self.raw);p=bytearray(i.rgba());p[(12*80+12)*4]=99
        overrides={self.name:i.replace_rgba(p).to_bytes()}
        r=audit.audit({self.name:self.raw},self.root,self.plans,self.groups,self.checks,overrides)
        self.assertFalse(r['errors']);self.assertEqual((self.root/self.name).read_bytes(),self.raw)


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'runtime'
        for n,b in [('Start.ps1',b'owned entry'),('Play.cmd',b'owned play'),('modules/keep.dll',b'owned module'),
                    ('config/enhancements.json',b'{}'),('data/MC00.sav',b'owned save'),('data/BGR/0000.BGR',b'old image')]:
            p=self.root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        m=dict(schema=1,files={n:deploy.digest((self.root/n).read_bytes()) for n in ['Start.ps1','Play.cmd','modules/keep.dll']},
               data={'BGR/0000.BGR':deploy.digest(b'old image')})
        (self.root/'runtime.json').write_text(json.dumps(m),encoding='utf8')
        self.package=self.base/'package';(self.package/'BGR').mkdir(parents=True)
        (self.package/'BGR/0000.BGR').write_bytes(b'new image')
        (self.package/'build.json').write_text(json.dumps(dict(source_unchanged=True,game_started=False,deployed=False,
             resources=[dict(resource='BGR/0000.BGR',modified_sha256=deploy.digest(b'new image'))])),encoding='utf8')
        self.inventory=self.base/'inventory.json';self.inventory.write_text(json.dumps(dict(game_started=False,
             records=[dict(resource='BGR/0000.BGR',current_sha256=deploy.digest(b'old image'))])),encoding='utf8')
        self.checks=self.base/'checks.json';self.checks.write_text('{}',encoding='utf8')
        self.record=self.base/'record';self.before=self.snapshot()
        mock=patch.object(deploy,'idle');mock.start();self.addCleanup(mock.stop)

    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def apply(self):return deploy.apply(self.root,[self.package],self.inventory,self.checks,self.record)

    def test_image_only_update_and_exact_rollback(self):
        self.apply();after=self.snapshot()
        self.assertEqual({n for n in after if after[n]!=self.before[n]},{'runtime.json','data/BGR/0000.BGR'})
        deploy.rollback(self.record);self.assertEqual(self.snapshot(),self.before)

    def test_readonly_cd_image_retains_attributes_and_rolls_back(self):
        path=self.root/'data/BGR/0000.BGR';path.chmod(stat.S_IREAD)
        mode=path.stat().st_mode
        self.apply();self.assertEqual(path.stat().st_mode,mode)
        deploy.rollback(self.record);self.assertEqual(path.stat().st_mode,mode)
        self.assertEqual(path.read_bytes(),b'old image')

    def test_partial_write_is_compensated(self):
        real=deploy.write_file
        def fail(p,b):
            if p==self.root/'runtime.json':raise OSError('owned write failure')
            real(p,b)
        with patch.object(deploy,'write_file',side_effect=fail),self.assertRaises(OSError):self.apply()
        self.assertEqual(self.snapshot(),self.before)

    def test_baseline_drift_refuses_all_writes(self):
        (self.root/'data/BGR/0000.BGR').write_bytes(b'foreign image');before=self.snapshot()
        with self.assertRaises(ValueError):self.apply()
        self.assertEqual(self.snapshot(),before);self.assertFalse(self.record.exists())

    def test_reentry_refuses_all_writes(self):
        self.apply();before=self.snapshot()
        with self.assertRaises(ValueError):self.apply()
        self.assertEqual(self.snapshot(),before)

    def test_rollback_drift_and_bad_backup_refuse_all_writes(self):
        self.apply();(self.record/'original/data/BGR/0000.BGR').write_bytes(b'foreign backup');before=self.snapshot()
        with self.assertRaises(ValueError):deploy.rollback(self.record)
        self.assertEqual(self.snapshot(),before)

    def test_changed_player_settings_are_retained_during_rollback(self):
        self.apply();(self.root/'config/enhancements.json').write_bytes(b'changed player settings')
        deploy.rollback(self.record)
        self.assertEqual((self.root/'config/enhancements.json').read_bytes(),b'changed player settings')
        self.assertEqual((self.root/'data/MC00.sav').read_bytes(),b'owned save')

    def test_rollback_never_writes_a_newer_image(self):
        self.apply();(self.root/'data/BGR/0000.BGR').write_bytes(b'newer image');before=self.snapshot()
        with self.assertRaises(ValueError):deploy.rollback(self.record)
        self.assertEqual(self.snapshot(),before)
