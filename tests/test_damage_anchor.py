"""Compiled popup getter coverage, independent of driver/UI matrix state."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT/'build/native/Release/damage-render-fixture/damage_projection_bridge.exe'
IDENTITY = [float(i % 5 == 0) for i in range(16)]


@unittest.skipUnless(BRIDGE.is_file(), 'Build documented damage_projection_bridge')
class PopupAnchorTests(unittest.TestCase):
    def run_anchor(self, index=0, point=(2, 1, -4), parent=None, camera=None,
                   fov=90, options=(), cached=(0, 0), known_driver=True):
        matrices = [IDENTITY] + ([] if parent is None else [parent])
        fields = ['anchor', 800, 600, index, int(known_driver), fov, 1, 1000,
                  *(camera or IDENTITY), len(matrices),
                  *[v for m in matrices for v in m], *IDENTITY, *point, *cached]
        result = subprocess.run([str(BRIDGE), str(BRIDGE.parent/'AsrD3DDrv.dll'), *options],
                                input=' '.join(map(str, fields))+'\n', text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual(row['abi_error_bits'], 0)
        self.assertFalse(row['game_started'])
        return row

    def test_all_nine_popup_calls_share_fresh_anchor_and_abi(self):
        for index in range(9):
            with self.subTest(index=index):
                self.assertEqual(self.run_anchor(index)['screen'], [550, 225])

    def test_scene_camera_and_parent_replace_stale_cache(self):
        parent = IDENTITY.copy(); parent[12] = -1
        camera = IDENTITY.copy(); camera[13] = -1
        self.assertEqual(self.run_anchor(parent=parent, camera=camera, cached=(123, 45))['screen'], [475, 300])

    def test_invalid_points_are_hidden_not_top_left(self):
        for point in [(0, 0, 4), (0, 0, -.5), (0, 0, -1001), (100, 0, -4), (float('nan'), 0, -4)]:
            with self.subTest(point=point):
                self.assertEqual(self.run_anchor(point=point)['screen'], [-1, -1])
        self.assertEqual(self.run_anchor(fov=0)['screen'], [-1, -1])

    def test_unknown_driver_preserves_native_cached_anchor(self):
        self.assertEqual(self.run_anchor(known_driver=False, cached=(123, 45))['screen'], [123, 45])

    def test_native_and_exact_rollback_restore_cached_behavior(self):
        for option in ('--native', '--rollback'):
            with self.subTest(option=option):
                row = self.run_anchor(options=(option,), cached=(123, 45))
                self.assertEqual(row['screen'], [123, 45])
                self.assertFalse(row['hook_enabled'])
                self.assertEqual(row['rollback_exact'], option == '--rollback')


if __name__ == '__main__':
    unittest.main()
