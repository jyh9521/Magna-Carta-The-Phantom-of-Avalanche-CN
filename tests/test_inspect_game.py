import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

import pycdlib

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


survey = load('inspect_game')
comparison = load('compare_inputs')


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_iso(self):
        iso = pycdlib.PyCdlib()
        iso.new(vol_ident='SAMPLE')
        iso.add_fp(io.BytesIO(b'test'), 4, iso_path='/DATA.DAT;1')
        path = self.root / 'sample.iso'
        iso.write(str(path))
        iso.close()
        return path

    def test_iso_inventory(self):
        report = survey.inspect_iso(self.make_iso())
        self.assertEqual(report['volume_id'], 'SAMPLE')
        self.assertEqual(report['file_count'], 1)
        self.assertTrue(report['files'][0]['within_image'])

    def test_invalid_iso_reported(self):
        path = self.root / 'bad.iso'
        path.write_bytes(b'bad')
        self.assertIn('error', survey.inspect_iso(path))

    def test_empty_fpb_counted(self):
        (self.root / 'Fpb').mkdir()
        (self.root / 'Fpb/0.fpb').write_bytes(b'\0' * 4)
        self.assertEqual(survey.fpb_stats(self.root)['empty'], 1)

    def test_comparison_does_not_write_inputs(self):
        image = self.make_iso()
        workspace = self.root / 'workspace'
        workspace.mkdir()
        (workspace / 'data.dat').write_bytes(b'test')
        patch = self.root / 'patch.zip'
        with zipfile.ZipFile(patch, 'w') as archive:
            archive.writestr('data.dat', b'test')
            archive.writestr('extra.dat', b'other')
        result = comparison.compare(workspace, image, patch)
        self.assertEqual(result['disc']['counts'], {'identical': 1})
        self.assertEqual(result['patch']['counts'], {'identical': 1, 'not-installed': 1})
        self.assertEqual((workspace / 'data.dat').read_bytes(), b'test')
        self.assertFalse((workspace / 'extra.dat').exists())


if __name__ == '__main__':
    unittest.main()
