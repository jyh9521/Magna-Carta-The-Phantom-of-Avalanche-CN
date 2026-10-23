"""Owned x86 ABI bridge tests, separate from native glyph/GPU rendering proofs."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DamageProjectionBridgeTests(unittest.TestCase):
    def bridge(self):
        folders = [ROOT / 'build/native/Release/damage-render-fixture',
                   ROOT / 'build/native/damage-projection-bridge/Release',
                   ROOT / 'build/native/Release/damage-projection-bridge',
                   ROOT / 'build/damage-render-chain/input-native/Release']
        for folder in folders:
            exe = folder / 'damage_projection_bridge.exe'
            dll = folder / 'AsrD3DDrv.dll'
            if exe.is_file() and dll.is_file():
                return exe, dll
        self.skipTest('Build the owned Win32 damage_projection_bridge and driver fixture first')

    def case(self, point=(.5, .5, .5), slots=(0x1897c, 0x80a4, 0x9b8c)):
        identity = [int(i % 5 == 0) for i in range(16)]
        return ' '.join(map(str, ['owned', 800, 600, *slots, *identity, *identity,
                                  *point, 123, 456, 789, 12, 127])) + '\n'

    def run_case(self, line, *options):
        exe, dll = self.bridge()
        result = subprocess.run([str(exe), str(dll), *options], input=line,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual(row['abi_error_bits'], 0)
        self.assertFalse(row['commercial_dll_loaded'])
        self.assertFalse(row['game_started'])
        return row

    def test_real_installer_lookup_and_x86_stack_nonvolatile_contract(self):
        row = self.run_case(self.case())
        self.assertTrue(row['installer_ready'])
        self.assertTrue(row['driver_lookup'])
        self.assertTrue(row['hook_enabled'])
        self.assertEqual(row['raster_float'], [600, 450, .5, 1])
        self.assertEqual(row['valid'], 1)
        self.assertEqual(row['delegated'], [0, 0, 0])

    def test_unpatched_run_is_an_explicit_control_not_a_source_baseline(self):
        row = self.run_case(self.case(), '--native')
        self.assertFalse(row['hook_enabled'])
        self.assertFalse(row['installer_ready'])
        self.assertEqual(row['raster_float'], [123, 456, 789, 12])
        self.assertEqual(row['valid'], 127)
        self.assertEqual(row['delegated'], [1, 1, 1])

    def test_explicit_rollback_restores_original_site_behavior(self):
        row = self.run_case(self.case(), '--rollback')
        self.assertTrue(row['installer_ready'])
        self.assertTrue(row['rollback_exact'])
        self.assertFalse(row['hook_enabled'])
        self.assertEqual(row['raster_float'], [123, 456, 789, 12])
        self.assertEqual(row['valid'], 127)
        self.assertEqual(row['delegated'], [1, 1, 1])

    def test_unknown_driver_virtuals_are_delegated(self):
        row = self.run_case(self.case(slots=(0x1897d, 0x80a5, 0x9b8d)))
        self.assertEqual(row['raster_float'], [123, 456, 789, 12])
        self.assertEqual(row['valid'], 127)
        self.assertEqual(row['delegated'], [1, 1, 1])

    def test_nonfinite_and_offscreen_points_produce_invalid_raster(self):
        for point in [(2, .5, .5), ('nan', 0, 0), (0, 0, -.5)]:
            with self.subTest(point=point):
                row = self.run_case(self.case(point=point))
                self.assertEqual(row['valid'], 0)
                self.assertEqual(row['delegated'], [0, 0, 0])

    def test_real_driver_is_rejected_before_loader_call(self):
        exe, _ = self.bridge()
        commercial = ROOT / 'runtime/data/Drv/AsrD3DDrv.dll'
        if not commercial.exists():
            self.skipTest('Local original driver is not supplied')
        result = subprocess.run([str(exe), str(commercial)], input=self.case(),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('only no-entry no-import owned fixture accepted', result.stderr)


if __name__ == '__main__':
    unittest.main()
