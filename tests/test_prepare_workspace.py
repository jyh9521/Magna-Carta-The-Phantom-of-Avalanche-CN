import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prepare_workspace', Path(__file__).resolve().parents[1] / 'tools/prepare_workspace.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'sample.dat').write_bytes(b'original\x00\xff')

    def test_copy_and_source_preserved(self):
        rows = module.prepare(self.source, self.root / 'copy', self.root / 'manifest.json')
        self.assertEqual(len(rows), 1)
        self.assertEqual(module.inventory(self.source), module.inventory(self.root / 'copy'))
        (self.root / 'copy/sample.dat').write_bytes(b'changed')
        self.assertEqual((self.source / 'sample.dat').read_bytes(), b'original\x00\xff')

    def test_existing_target_rejected(self):
        target = self.root / 'copy'
        target.mkdir()
        with self.assertRaises(ValueError):
            module.prepare(self.source, target, self.root / 'manifest.json')

    def test_nested_target_rejected(self):
        with self.assertRaises(ValueError):
            module.prepare(self.source, self.source / 'copy', self.root / 'manifest.json')

    def test_manifest_in_source_rejected(self):
        with self.assertRaises(ValueError):
            module.prepare(self.source, self.root / 'copy', self.source / 'manifest.json')


if __name__ == '__main__':
    unittest.main()
