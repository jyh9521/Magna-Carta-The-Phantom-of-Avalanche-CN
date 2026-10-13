import json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import update_image_candidate as m

class ImageUpgradeTests(unittest.TestCase):
    def fixture(self,root):
        workspace=root/'copy';workspace.mkdir();(workspace/'.locale-install.json').write_text('{"state":"candidate"}')
        (workspace/'image.bgr').write_bytes(b'old pixels');(workspace/'save.sav').write_bytes(b'owned save')
        old=root/'old';old.write_bytes(b'old pixels');new=root/'new';new.write_bytes(b'new pixels')
        return workspace,old,new
    def test_apply_and_rollback_keep_saves_and_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);w,old,new=self.fixture(root)
            with patch.object(m,'collect',side_effect=[{'image.bgr':old},{'image.bgr':new}]):m.apply(w,[],[],root/'backup')
            self.assertEqual((w/'image.bgr').read_bytes(),b'new pixels')
            m.rollback(w,root/'backup');self.assertEqual((w/'image.bgr').read_bytes(),b'old pixels')
            self.assertEqual((w/'save.sav').read_bytes(),b'owned save');self.assertEqual(old.read_bytes(),b'old pixels')
    def test_drift_before_apply_creates_no_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);w,old,new=self.fixture(root);(w/'image.bgr').write_bytes(b'drift')
            with patch.object(m,'collect',side_effect=[{'image.bgr':old},{'image.bgr':new}]):
                with self.assertRaises(ValueError):m.apply(w,[],[],root/'backup')
            self.assertFalse((root/'backup').exists());self.assertEqual((w/'image.bgr').read_bytes(),b'drift')
    def test_rollback_drift_refuses_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);w,old,new=self.fixture(root)
            with patch.object(m,'collect',side_effect=[{'image.bgr':old},{'image.bgr':new}]):m.apply(w,[],[],root/'backup')
            (w/'image.bgr').write_bytes(b'user edit')
            with self.assertRaises(ValueError):m.rollback(w,root/'backup')
            self.assertEqual((w/'image.bgr').read_bytes(),b'user edit')

    def test_readonly_copy_is_updated_then_attributes_restored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);w,old,new=self.fixture(root);target=w/'image.bgr';target.chmod(0o444)
            original_mode=target.stat().st_mode
            with patch.object(m,'collect',side_effect=[{'image.bgr':old},{'image.bgr':new}]):m.apply(w,[],[],root/'backup')
            self.assertEqual(target.read_bytes(),b'new pixels')
            m.rollback(w,root/'backup');self.assertEqual(target.read_bytes(),b'old pixels')
            self.assertEqual(target.stat().st_mode,original_mode)

    def test_write_failure_restores_every_attempted_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);w,old,new=self.fixture(root);(w/'second.bgr').write_bytes(b'old pixels')
            original_write=Path.write_bytes;failed=[False]
            def write(path,raw):
                if path==w/'second.bgr' and not failed[0]:
                    failed[0]=True;raise OSError('owned fixture write failure')
                return original_write(path,raw)
            with patch.object(m,'collect',side_effect=[{'image.bgr':old,'second.bgr':old},{'image.bgr':new,'second.bgr':new}]):
                with patch.object(Path,'write_bytes',write):
                    with self.assertRaises(OSError):m.apply(w,[],[],root/'backup')
            self.assertEqual((w/'image.bgr').read_bytes(),b'old pixels')
            self.assertEqual((w/'second.bgr').read_bytes(),b'old pixels')
