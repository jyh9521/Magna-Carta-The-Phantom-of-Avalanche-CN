import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import render_candidate as module


class RenderCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.copy = self.root / 'copy'
        self.inputs = {'fixture.bin': module.graphics.sha(b'game')}
        self.hashes = {**self.inputs, 'ddraw.dll': module.graphics.sha(b'dll'),
                       module.CONFIG_NAME: module.graphics.sha(module.BASELINE)}
        for name, value in [('SOURCE_INPUTS', self.inputs), ('GRAPHICS_INPUTS', self.inputs), ('SOURCE_HASHES', self.hashes)]:
            p = patch.object(module, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(module.graphics, 'DLL_SHA256', self.hashes['ddraw.dll'])
        p.start()
        self.addCleanup(p.stop)
        for folder in (self.source, self.copy):
            folder.mkdir()
            (folder / 'Drv').mkdir()
            (folder / 'fixture.bin').write_bytes(b'game')
            (folder / 'ddraw.dll').write_bytes(b'dll')
            (folder / module.CONFIG_NAME).write_bytes(module.BASELINE)
            state = {'schema': 1, 'layer': 'DDrawCompat', 'version': module.graphics.VERSION,
                     'profile': 'render1080', 'inputs': self.inputs,
                     'outputs': {'ddraw.dll': self.hashes['ddraw.dll'],
                                 module.CONFIG_NAME: self.hashes[module.CONFIG_NAME]}}
            (folder / module.graphics.STATE_NAME).write_text(json.dumps(state))

    def test_generate_source_preserved_and_five_hashes(self):
        out = self.root / 'bundle'
        manifest = module.generate(self.source, out)
        for name, data in module.PROFILES.items():
            self.assertEqual((out / (name + '.ini')).read_bytes(), data)
            self.assertEqual(manifest['profiles'][name]['sha256'], module.graphics.sha(data))
        self.assertFalse(manifest['profiles']['wide4k']['installable'])
        self.assertFalse(manifest['profiles']['combined']['installable'])
        self.assertEqual((self.source / module.CONFIG_NAME).read_bytes(), module.BASELINE)

    def test_variable_isolation(self):
        self.assertEqual(module.PROFILES['render4k'], module.BASELINE.replace(b'1920x1080', b'3840x2160'))
        self.assertEqual(module.PROFILES['wide4k'], module.PROFILES['render4k'].replace(
            b'DisplayAspectRatio = app', b'DisplayAspectRatio = 16:9'))
        self.assertEqual(module.PROFILES['fps60'], module.BASELINE + b'FpsLimiter = flipend(60)\n')
        self.assertEqual(module.PROFILES['combined'], module.PROFILES['wide4k'] + b'FpsLimiter = flipend(60)\n')

    def test_each_installable_profile_roundtrip(self):
        for profile in ('baseline', 'render4k', 'fps60'):
            module.apply(self.source, self.copy, self.root, profile)
            self.assertEqual((self.copy / module.CONFIG_NAME).read_bytes(), module.PROFILES[profile])
            module.rollback(self.copy, self.root)
            self.assertEqual((self.copy / module.CONFIG_NAME).read_bytes(), module.BASELINE)
            self.assertFalse((self.copy / module.STATE_NAME).exists())

    def test_source_and_nested_targets_rejected(self):
        with self.assertRaises(ValueError):
            module.apply(self.source, self.source, self.root, 'render4k')
        nested = self.source / 'nested'
        nested.mkdir()
        with self.assertRaises(ValueError):
            module.apply(self.source, nested, self.root, 'render4k')

    def test_wide_draft_install_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Projection integration'):
            module.apply(self.source, self.copy, self.root, 'wide4k')
        self.assertFalse((self.copy / module.STATE_NAME).exists())

    def test_unknown_source_and_manifest_rejected(self):
        (self.source / 'fixture.bin').write_bytes(b'unknown')
        with self.assertRaises(ValueError): module.checked_source(self.source)
        (self.source / 'fixture.bin').write_bytes(b'game')
        (self.source / module.graphics.STATE_NAME).write_text('{}')
        with self.assertRaises(ValueError): module.checked_source(self.source)

    def test_competing_overlay_rejected(self):
        (self.source / 'DDrawCompatOverlay-MagnaCarta.ini').write_bytes(b'VSync=off')
        with self.assertRaises(ValueError): module.checked_source(self.source)

    def test_existing_bundle_and_nested_bundle_rejected(self):
        with self.assertRaises(ValueError): module.generate(self.source, self.copy)
        with self.assertRaises(ValueError): module.generate(self.source, self.source / 'bundle')

    def test_existing_candidate_rejected(self):
        module.apply(self.source, self.copy, self.root, 'render4k')
        with self.assertRaises(ValueError): module.apply(self.source, self.copy, self.root, 'fps60')

    def test_changed_config_preserved_on_rollback(self):
        module.apply(self.source, self.copy, self.root, 'render4k')
        (self.copy / module.CONFIG_NAME).write_bytes(b'user edit')
        with self.assertRaises(ValueError): module.rollback(self.copy, self.root)
        self.assertEqual((self.copy / module.CONFIG_NAME).read_bytes(), b'user edit')
        self.assertTrue((self.copy / module.STATE_NAME).exists())

    def test_changed_binary_preserved_on_rollback(self):
        module.apply(self.source, self.copy, self.root, 'render4k')
        (self.copy / 'ddraw.dll').write_bytes(b'user dll')
        with self.assertRaises(ValueError): module.rollback(self.copy, self.root)
        self.assertEqual((self.copy / 'ddraw.dll').read_bytes(), b'user dll')

    def test_tampered_candidate_manifest_rejected(self):
        module.apply(self.source, self.copy, self.root, 'render4k')
        (self.copy / module.STATE_NAME).write_text('{"schema":1,"profile":"wide4k"}')
        with self.assertRaises(ValueError): module.rollback(self.copy, self.root)

    def test_changed_graphics_manifest_preserved(self):
        module.apply(self.source, self.copy, self.root, 'render4k')
        (self.copy / module.graphics.STATE_NAME).write_text('{}')
        with self.assertRaises(ValueError): module.rollback(self.copy, self.root)
        self.assertEqual((self.copy / module.graphics.STATE_NAME).read_text(), '{}')


if __name__ == '__main__':
    unittest.main()
