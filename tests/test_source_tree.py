"""Source inventory checks use only small independent text fixtures."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from check_source_tree import audit


class SourceTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {'README.md': '[Build](BUILDING.md)\n', 'BUILDING.md': '# Build\n',
                      'CONTRIBUTING.md': '# Contribution\n'}
        self.write()

    def write(self):
        for name, text in self.files.items():
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf8')

    def result(self):
        return audit(self.root, self.files)

    def test_source_only_tree_needs_no_runtime(self):
        result = self.result()
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['local_links'], 1)
        self.assertFalse(result['requires_local_runtime'])
        self.assertFalse((self.root/'runtime').exists())

    def test_populated_directory_placeholder_is_redundant(self):
        self.files.update({'tools/.gitkeep': '', 'tools/example.py': 'pass\n'})
        self.write()
        self.assertIn('redundant directory placeholder: tools/.gitkeep', self.result()['errors'])

    def test_empty_directory_placeholder_remains_valid(self):
        self.files['future/.gitkeep'] = ''
        self.write()
        self.assertEqual(self.result()['errors'], [])

    def test_generated_files_are_rejected(self):
        for name in ('build/result.txt', 'runtime/data.txt', 'tools/__pycache__/m.pyc', 'src/game.dll'):
            with self.subTest(name=name):
                self.files[name] = 'fixture'
                self.write()
                self.assertIn('generated file in source inventory: '+name, self.result()['errors'])
                self.files.pop(name)

    def test_missing_tracked_file_is_reported(self):
        self.files['src/missing.cpp'] = ''
        self.assertIn('missing tracked source: src/missing.cpp', self.result()['errors'])

    def test_untracked_local_link_does_not_hide_missing_input(self):
        self.files['README.md'] = '[Local](private.md)\n'
        self.write()
        (self.root/'private.md').write_text('not published', encoding='utf8')
        self.assertIn('guide link is not tracked: README.md -> private.md', self.result()['errors'])

    def test_links_resolve_relative_to_each_document(self):
        self.files['BUILDING.md'] = '[History](docs/history.md#past)\n'
        self.files['docs/history.md'] = '# Past\n'
        self.write()
        self.assertEqual(self.result()['errors'], [])

    def test_remote_and_fragment_links_are_not_local_inputs(self):
        self.files['README.md'] = '[Remote](https://example.org/path) [Top](#top)\n'
        self.write()
        self.assertEqual(self.result()['errors'], [])

    def test_escaping_link_is_rejected(self):
        self.files['README.md'] = '[Escape](../private.md)\n'
        self.write()
        self.assertIn('guide link escapes source tree: README.md -> ../private.md', self.result()['errors'])

    def test_missing_current_guide_is_rejected(self):
        self.files.pop('CONTRIBUTING.md')
        self.assertIn('missing current guide: CONTRIBUTING.md', self.result()['errors'])

    def test_invalid_inventory_path_is_rejected(self):
        for name in ('../outside', 'C:/private', 'tools\\module.py', ''):
            with self.subTest(name=name):
                self.assertIn('invalid source path: '+name, audit(self.root, [*self.files, name])['errors'])


if __name__ == '__main__':
    unittest.main()
