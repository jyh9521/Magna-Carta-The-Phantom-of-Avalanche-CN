import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('graphics_compat', Path(__file__).resolve().parents[1] / 'tools/graphics_compat.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GraphicsCompatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'
        self.game.mkdir()
        self.original = self.game / 'fixture.bin'
        self.original.write_bytes(b'original')
        self.expected = {'fixture.bin': module.sha(b'original')}

    def apply_fixture(self):
        with patch.object(module, 'DLL_SHA256', module.sha(b'fixture-layer')):
            return module.apply(self.game, self.root, b'fixture-layer', self.expected)

    def test_roundtrip(self):
        self.apply_fixture()
        self.assertEqual(self.original.read_bytes(), b'original')
        with patch.object(module, 'DLL_SHA256', module.sha(b'fixture-layer')):
            self.assertEqual(module.remove(self.game, self.root), 3)
        self.assertEqual(list(self.game.iterdir()), [self.original])

    def test_existing_layer_rejected(self):
        (self.game / 'D3D9.dll').write_bytes(b'other')
        with self.assertRaises(ValueError):
            self.apply_fixture()
        self.assertFalse((self.game / module.STATE_NAME).exists())

    def test_drv_layer_rejected(self):
        (self.game / 'Drv').mkdir()
        (self.game / 'Drv/ddraw.dll').write_bytes(b'other')
        with self.assertRaises(ValueError):
            self.apply_fixture()

    def test_unknown_version_rejected(self):
        self.original.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.apply_fixture()

    def test_outside_workspace_rejected(self):
        with self.assertRaises(ValueError):
            module.workspace_path(self.root, self.root)

    def test_tampered_output_preserved(self):
        self.apply_fixture()
        (self.game / module.CONFIG_NAME).write_bytes(b'changed')
        with patch.object(module, 'DLL_SHA256', module.sha(b'fixture-layer')):
            with self.assertRaises(ValueError):
                module.remove(self.game, self.root)
        self.assertTrue((self.game / 'ddraw.dll').exists())

    def test_manifest_traversal_rejected(self):
        self.apply_fixture()
        (self.game / module.STATE_NAME).write_text('{"outputs":{"../fixture.bin":"x"}}')
        with self.assertRaises(ValueError):
            module.remove(self.game, self.root)
        self.assertEqual(self.original.read_bytes(), b'original')

    def test_package_mismatch_rejected(self):
        package = self.root / 'unknown.zip'
        package.write_bytes(b'unknown')
        with self.assertRaises(ValueError):
            module.package_dll(package)

    def test_hal_profile_roundtrip(self):
        with patch.object(module, 'DLL_SHA256', module.sha(b'fixture-layer')):
            module.apply(self.game, self.root, b'fixture-layer', self.expected, profile='hal')
            self.assertEqual((self.game / module.CONFIG_NAME).read_bytes(), module.CONFIG + b'SupportedDevices = hal\n')
            self.assertEqual(module.remove(self.game, self.root), 3)
        self.assertEqual(self.original.read_bytes(), b'original')

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            module.apply(self.game, self.root, b'fixture-layer', self.expected, profile='unknown')
        self.assertEqual(list(self.game.iterdir()), [self.original])

    def select_fixture(self, profile):
        with patch.object(module, 'DLL_SHA256', module.sha(b'fixture-layer')):
            return module.select_profile(self.game, self.root, profile, self.expected)

    def test_profile_switch_and_restore(self):
        self.apply_fixture()
        original = (self.game / module.STATE_NAME).read_bytes()
        self.assertTrue(self.select_fixture('hal'))
        self.assertEqual((self.game / module.CONFIG_NAME).read_bytes(), module.PROFILES['hal'])
        self.assertFalse(self.select_fixture('hal'))
        self.assertTrue(self.select_fixture('standard'))
        self.assertEqual((self.game / module.STATE_NAME).read_bytes(), original)
        self.assertEqual(self.original.read_bytes(), b'original')

    def test_profile_switch_preserves_tampered_config(self):
        self.apply_fixture()
        (self.game / module.CONFIG_NAME).write_bytes(b'custom')
        with self.assertRaises(ValueError):
            self.select_fixture('hal')
        self.assertEqual((self.game / module.CONFIG_NAME).read_bytes(), b'custom')

    def test_profile_switch_rejects_competing_layer(self):
        self.apply_fixture()
        (self.game / 'D3DImm.dll').write_bytes(b'other')
        with self.assertRaises(ValueError):
            self.select_fixture('hal')
        self.assertEqual((self.game / module.CONFIG_NAME).read_bytes(), module.CONFIG)

    def test_profile_switch_rejects_foreign_manifest(self):
        self.apply_fixture()
        with patch.object(module, 'DLL_SHA256', module.sha(b'fixture-layer')):
            with self.assertRaises(ValueError):
                module.select_profile(self.game, self.root, 'hal', {'unknown': 'hash'})

    def test_profile_switch_write_failure_restores_both_files(self):
        self.apply_fixture()
        original = (self.game / module.STATE_NAME).read_bytes()
        replace = module.replace_bytes
        calls = 0
        def fail_second(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('fixture write failure')
            return replace(path, data)
        with patch.object(module, 'replace_bytes', fail_second):
            with self.assertRaises(OSError):
                self.select_fixture('hal')
        self.assertEqual((self.game / module.CONFIG_NAME).read_bytes(), module.CONFIG)
        self.assertEqual((self.game / module.STATE_NAME).read_bytes(), original)
        self.assertEqual(len(list(self.game.iterdir())), 4)

    def test_driver_version_matrix_is_explicit(self):
        self.assertEqual(set(module.VERSION_INPUTS), {'patched', 'unpatched'})
        original = module.VERSION_INPUTS['patched']
        candidate = module.VERSION_INPUTS['unpatched']
        self.assertEqual(candidate['MagnaCarta.exe'], original['MagnaCarta.exe'])
        self.assertEqual(candidate['MCAlpha.dll'], original['MCAlpha.dll'])
        self.assertNotEqual(candidate['Drv/AsrD3DDrv.dll'], original['Drv/AsrD3DDrv.dll'])
        self.assertIn('Drv/AsrGlDrv.dll', candidate)

    def test_activation_profile_roundtrip(self):
        self.apply_fixture()
        self.assertTrue(self.select_fixture('activation'))
        self.assertEqual((self.game/module.CONFIG_NAME).read_bytes(),module.CONFIG+b'AltTabFix = noactivateapp(0)\n')
        self.assertTrue(self.select_fixture('standard'))
        self.assertEqual((self.game/module.CONFIG_NAME).read_bytes(),module.CONFIG)


if __name__ == '__main__':
    unittest.main()
