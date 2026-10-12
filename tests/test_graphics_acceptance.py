import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('check_graphics_probe', Path(__file__).resolve().parents[1] / 'tools/check_graphics_probe.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GraphicsAcceptanceTests(unittest.TestCase):
    def test_exit_failure_overrides_render_marker(self):
        self.assertFalse(module.accepted(-1073740791, module.MARKER))
        self.assertFalse(module.accepted(3221226525, module.MARKER))

    def test_exit_success_needs_render_marker(self):
        self.assertFalse(module.accepted(0, ''))
        self.assertTrue(module.accepted(0, module.MARKER))

    def test_hal_profile_needs_device_filter(self):
        self.assertFalse(module.accepted(0, module.MARKER, True))
        self.assertTrue(module.accepted(0, 'DEVICE_ENUM hal=1 tnl=0\n' + module.MARKER, True))
