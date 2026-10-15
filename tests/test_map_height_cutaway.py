from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_map_atlas as tool


class MapHeightCutawayTests(unittest.TestCase):
    def test_roof_is_excluded_above_cut_plane(self):
        self.assertEqual(tool.clip_at_height([(0, 0, 70), (10, 0, 70), (0, 10, 70)], 30), [])

    def test_floor_is_preserved(self):
        floor = [(0, 0, 0), (10, 0, 0), (0, 10, 0)]
        self.assertEqual(tool.clip_at_height(floor, 30), floor)

    def test_crossing_triangle_is_clipped_not_discarded(self):
        polygon = tool.clip_at_height([(0, 0, 0), (10, 0, 0), (0, 10, 100)], 50)
        self.assertEqual(len(polygon), 4)
        self.assertTrue(all(point[2] <= 50 for point in polygon))
        self.assertIn((0., 5., 50.), polygon)
        self.assertIn((5., 5., 50.), polygon)

    def test_plane_boundary_does_not_duplicate_vertices(self):
        polygon = tool.clip_at_height([(0, 0, 50), (10, 0, 0), (0, 10, 100)], 50)
        self.assertEqual(len(polygon), 3)
        self.assertEqual(len(set(polygon)), len(polygon))

    def test_invalid_height_rejected(self):
        for height in [float('nan'), float('inf'), -float('inf')]:
            self.assertRaisesRegex(ValueError, 'height', tool.clip_at_height, [(0, 0, 0)]*3, height)

    def test_cutaway_preserves_viewport_and_default_rendering(self):
        meshes = [{'points': [(0, 0, 0), (10, 0, 0), (0, 10, 0), (2, 2, 70), (4, 2, 70), (2, 4, 70)],
                   'triangles': [(0, 1, 2), (3, 4, 5)]}]
        bounds = [0, 0, 10, 10]
        baseline, viewport = tool.raster(meshes, bounds, 128)
        cutaway, cut_viewport = tool.raster(meshes, bounds, 128, 30)
        uncut, uncut_viewport = tool.raster(meshes, bounds, 128, 1000)
        self.assertEqual(viewport, cut_viewport); self.assertEqual(viewport, uncut_viewport)
        self.assertEqual(baseline.tobytes(), uncut.tobytes())
        self.assertNotEqual(baseline.tobytes(), cutaway.tobytes())

    def test_invalid_build_height_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/'source'; source.mkdir()
            self.assertRaisesRegex(ValueError, 'height', tool.build, source, root/'out', 128, None, float('nan'))
            self.assertFalse((root/'out').exists())

    def test_cut_plane_below_entire_scene_rejects_blank_candidate(self):
        meshes = [{'points': [(0, 0, 70), (10, 0, 70), (0, 10, 70)], 'triangles': [(0, 1, 2)]}]
        self.assertRaisesRegex(ValueError, 'removed all geometry', tool.raster, meshes, [0, 0, 10, 10], 128, 30)
