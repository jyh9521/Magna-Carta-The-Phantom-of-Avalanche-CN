import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('runtime_settings', Path(__file__).resolve().parents[1] / 'tools/runtime_settings.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SettingTests(unittest.TestCase):
    def test_only_renderer_changes(self):
        original = bytes([1, 1] + list(range(50)))
        modified = module.convert(original, 'direct3d')
        self.assertEqual(module.renderer(modified), 'direct3d')
        self.assertEqual(modified[:1] + modified[2:], original[:1] + original[2:])
        self.assertEqual(module.convert(modified, 'opengl'), original)

    def test_unknown_layout_rejected(self):
        with self.assertRaises(ValueError):
            module.renderer(b'\0' * 51)

    def test_unknown_renderer_rejected(self):
        with self.assertRaises(ValueError):
            module.renderer(b'\0\x03' + b'\0' * 50)


if __name__ == '__main__':
    unittest.main()
