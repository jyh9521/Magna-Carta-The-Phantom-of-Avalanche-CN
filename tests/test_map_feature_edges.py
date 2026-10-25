"""Offline line-map topology and coordinate-domain regression tests."""
import struct
import sys
import tempfile
import unittest
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_map_atlas as tool


SQUARE = [[(0, 0, 0), (10, 0, 0), (10, 10, 0)],
          [(0, 0, 0), (10, 10, 0), (0, 10, 0)]]


class MapFeatureEdgeTests(unittest.TestCase):
    def test_locale_labels_are_generated_with_source_hash_and_no_local_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            labels = root / 'labels.json'
            values = {'map_title': '地形', 'map_legend': 'NPC / Player', 'map_hint': 'F9: mini > full > off'}
            original = json.dumps(values, ensure_ascii=False).encode('utf8')
            labels.write_bytes(original)
            manifest = tool.build(source, root / 'out', labels=labels)
            for key, name in [('map_title', 'label.txt'), ('map_legend', 'legend.txt'), ('map_hint', 'hint.txt')]:
                data = (root / 'out' / name).read_bytes()
                self.assertEqual(data, values[key].encode('utf-16le'))
                self.assertEqual(manifest['labels']['files'][name], hashlib.sha256(data).hexdigest())
            self.assertEqual(manifest['labels']['source_sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(manifest['labels']['encoding'], 'utf-16le')
            self.assertNotIn(str(root), json.dumps(manifest))
            self.assertEqual(labels.read_bytes(), original)

    def test_title_only_labels_and_omitted_labels_preserve_legacy_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            labels = root / 'labels.json'
            labels.write_text(json.dumps({'map_title': 'Map'}))
            tool.build(source, root / 'named', labels=labels)
            self.assertEqual((root / 'named/label.txt').read_bytes(), b'M\0a\0p\0')
            self.assertFalse((root / 'named/legend.txt').exists())
            self.assertFalse((root / 'named/hint.txt').exists())
            manifest = tool.build(source, root / 'legacy')
            self.assertNotIn('labels', manifest)
            self.assertEqual({path.name for path in (root / 'legacy').iterdir()}, {'manifest.json'})

    def test_invalid_label_fields_rejected_before_output_creation(self):
        invalid = [{}, [], {'map_title': 'Map', 'unknown': 'x'}, {'map_title': None},
                   {'map_title': ''}, {'map_title': '   '}, {'map_title': 'Map', 'map_hint': False}]
        invalid += [{'map_title': 'a' + char + 'b'} for char in ('\0', '\n', '\r', '\u2028', '\u2029')]
        invalid += [{'map_title': 'a' * 256}, {'map_title': '\U0001f600' * 128}, {'map_title': '\ud800'}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            labels = root / 'labels.json'
            for index, value in enumerate(invalid):
                with self.subTest(value=value):
                    labels.write_text(json.dumps(value), encoding='utf8')
                    output = root / str(index)
                    with self.assertRaises(ValueError):
                        tool.build(source, output, labels=labels)
                    self.assertFalse(output.exists())
            labels.write_text('{"map_title":"Map","map_title":"Duplicate"}', encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                tool.build(source, root / 'duplicate', labels=labels)
            self.assertFalse((root / 'duplicate').exists())

    def test_label_limit_counts_utf16_code_units_not_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            labels = Path(directory) / 'labels.json'
            value = '\U0001f600' * 127 + 'x'
            labels.write_text(json.dumps({'map_title': value}), encoding='utf8')
            files, record = tool.map_labels(labels)
            self.assertEqual(len(files['label.txt']), 510)
            self.assertEqual(files['label.txt'].decode('utf-16le'), value)

    def test_coplanar_interior_diagonal_removed(self):
        edges = tool.feature_edges(SQUARE)
        self.assertEqual(len(edges), 4)
        self.assertNotIn(((0, 0, 0), (10, 10, 0)), edges)

    def test_opposite_winding_and_input_order_are_stable(self):
        self.assertEqual(tool.feature_edges(SQUARE),
                         tool.feature_edges([list(reversed(p)) for p in reversed(SQUARE)]))

    def test_duplicate_and_same_side_faces_keep_boundary(self):
        self.assertEqual(len(tool.feature_edges([SQUARE[0], SQUARE[0]])), 3)
        shared = ((0, 0, 0), (10, 0, 0))
        self.assertIn(shared, tool.feature_edges([SQUARE[0],
                      [(0, 0, 0), (10, 0, 0), (5, 5, 0)]]))

    def test_fold_and_nonmanifold_edges_are_retained(self):
        shared = ((0, 0, 0), (10, 0, 0))
        folded = [SQUARE[0], [(0, 0, 0), (10, 0, 0), (0, 0, 5)]]
        self.assertIn(shared, tool.feature_edges(folded))
        self.assertIn(shared, tool.feature_edges(folded + [SQUARE[0]]))

    def test_seam_tolerance_and_degenerate_faces(self):
        shifted = [(0.000001, 0, 0), (10, 10.000001, 0), (0, 10, 0)]
        self.assertEqual(tool.feature_edges(SQUARE), tool.feature_edges([SQUARE[0], shifted]))
        self.assertEqual(tool.feature_edges([[(0, 0, 0)] * 3]), [])

    def test_roof_does_not_erase_lower_details_and_metadata_stays_fixed(self):
        meshes = [{'points': [(0, 0, 70), (10, 0, 70), (10, 10, 70), (0, 10, 70),
                              (3, 3, 0), (7, 3, 0), (3, 7, 0)],
                   'triangles': [(0, 1, 2), (0, 2, 3), (4, 5, 6)]}]
        solid, view = tool.raster(meshes, [0, 0, 10, 10], 128)
        lines, line_view = tool.raster(meshes, [0, 0, 10, 10], 128, style='feature-edges')
        self.assertEqual(view, line_view)
        # The lower edge Y=3 crosses X=5; a roof face used to overwrite it.
        pixel = (int(view[0] + 5 * view[2]), int(128 - view[1] - 3 * view[2]))
        self.assertEqual(solid.getpixel(pixel), (65, 86, 84))
        self.assertEqual(lines.getpixel(pixel), (177, 211, 194))
        self.assertEqual(lines.getpixel((30, 30)), (19, 32, 39))

    def test_default_solid_is_identical_and_clip_mode_composes(self):
        meshes = [{'points': [(0, 0, 0), (10, 0, 0), (0, 10, 100)],
                   'triangles': [(0, 1, 2)]}]
        image, view = tool.raster(meshes, [0, 0, 10, 10], 128)
        explicit, same_view = tool.raster(meshes, [0, 0, 10, 10], 128, style='solid')
        clipped, clipped_view = tool.raster(meshes, [0, 0, 10, 10], 128, 50, 'feature-edges')
        self.assertEqual(image.tobytes(), explicit.tobytes())
        self.assertEqual(view, same_view)
        self.assertEqual(view, clipped_view)
        self.assertNotEqual(image.tobytes(), clipped.tobytes())

    def test_unknown_style_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            with self.assertRaisesRegex(ValueError, 'render style'):
                tool.build(source, root / 'output', style='guessed-floor')
            self.assertFalse((root / 'output').exists())

    def test_build_manifest_and_metadata_match_solid_source(self):
        from test_resource_wrd import sample
        identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        original = sample()[:-40] + struct.pack('<4I', 0, 0, 0, 1) + \
            struct.pack('<II16f', 0, 0, *identity) + struct.pack('<II', 0, 0) + bytes(16)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / '0009.wrd').write_bytes(original)
            baseline = tool.build(source, root / 'solid', 128)
            candidate = tool.build(source, root / 'lines', 128, style='feature-edges')
            self.assertNotIn('render_style', baseline)
            self.assertEqual(candidate['render_style'], 'feature-edges')
            self.assertEqual(baseline['accepted'][0]['source_sha256'],
                             candidate['accepted'][0]['source_sha256'])
            self.assertEqual((root / 'solid/0009.map').read_bytes(),
                             (root / 'lines/0009.map').read_bytes())
            self.assertEqual((source / '0009.wrd').read_bytes(), original)
            self.assertFalse(candidate['navigation_verified'])


if __name__ == '__main__':
    unittest.main()
