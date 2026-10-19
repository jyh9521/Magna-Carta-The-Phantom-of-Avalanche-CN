import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_opening_layout import audit
from build_opening_layout import build
from resource_image import TGA_FOOTER


class OpeningLayoutTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'FrameData').mkdir()
        (root / 'BGR').mkdir()
        fdi = bytearray(787)
        fdi[:8] = bytes.fromhex('ba00000001000000')
        fdi[157] = 1
        struct.pack_into('<iiiii', fdi, 159, 1, 0, 0, 3, 1)
        (root / 'FrameData/0042.fdi').write_bytes(fdi)
        header = bytearray(18)
        header[2] = 2
        struct.pack_into('<HH', header, 12, 256, 256)
        header[16:18] = b'\x20\x08'
        raw = b'W' * 24 + header + bytes([255, 255, 255, 255]) * (256 * 256) + TGA_FOOTER
        (root / 'BGR/0001.BGR').write_bytes(raw)
        row = audit(root, 42)
        row['sha256'] = {key.replace('\\', '/'): value for key, value in row['sha256'].items()}
        row['ink_xyxy'] = list(row['ink_xyxy'])
        row['source_tile_bounds'] = [0, 0, 256, 256]
        metadata = root / 'metadata.json'
        metadata.write_text(json.dumps({'schema': 2, 'locale': 'fixture', 'layouts': [row]}), encoding='utf8')
        return metadata, row

    def test_generated_header_uses_measured_center_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            metadata, _ = self.fixture(root)
            output = root / 'generated/layout.h'
            self.assertEqual(build(root, metadata, output), 1)
            original = output.read_bytes()
            self.assertIn(b'{42, 128.0f, 128.0f, 0, 0, 256, 256}', original)
            build(root, metadata, output)
            self.assertEqual(output.read_bytes(), original)

    def test_bounds_must_be_whole_tiles_and_preserve_bright_ink(self):
        for bounds, error in [([0, 0, 255, 256], 'invalid source tile bounds'),
                              ([256, 0, 512, 256], 'exclude opening ink')]:
            with self.subTest(bounds=bounds), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                metadata, row = self.fixture(root)
                row['source_tile_bounds'] = bounds
                metadata.write_text(json.dumps({'schema': 2, 'layouts': [row]}), encoding='utf8')
                with self.assertRaisesRegex(ValueError, error):
                    build(root, metadata, root / 'layout.h')
                self.assertFalse((root / 'layout.h').exists())

    def test_dark_offscreen_tile_is_excluded_without_color_rewriting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            metadata, row = self.fixture(root)
            fdi = bytearray((root / 'FrameData/0042.fdi').read_bytes())
            fdi[199] = 1
            struct.pack_into('<iiiii', fdi, 201, 1, 0, 256, 3, 2)
            (root / 'FrameData/0042.fdi').write_bytes(fdi)
            raw = (root / 'BGR/0001.BGR').read_bytes()
            dark = raw[:42] + bytes([20, 10, 5, 255]) * (256 * 256) + raw[-26:]
            (root / 'BGR/0002.BGR').write_bytes(dark)
            row = audit(root, 42)
            row['sha256'] = {k.replace('\\', '/'): v for k, v in row['sha256'].items()}
            row['ink_xyxy'] = list(row['ink_xyxy'])
            row['source_tile_bounds'] = [0, 0, 256, 256]
            metadata.write_text(json.dumps({'schema': 2, 'layouts': [row]}), encoding='utf8')
            self.assertEqual(build(root, metadata, root / 'layout.h'), 1)
            self.assertEqual((root / 'BGR/0002.BGR').read_bytes(), dark)

    def test_unknown_source_hash_rejected_without_writing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            metadata, _ = self.fixture(root)
            path = root / 'BGR/0001.BGR'
            path.write_bytes(path.read_bytes() + b'drift')
            output = root / 'generated/layout.h'
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                build(root, metadata, output)
            self.assertFalse(output.exists())
            self.assertFalse(output.parent.exists())

    def test_wrong_center_rejected_preserving_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            metadata, row = self.fixture(root)
            row['ink_center'][0] += 1
            metadata.write_text(json.dumps({'schema': 2, 'layouts': [row]}), encoding='utf8')
            output = root / 'layout.h'
            output.write_bytes(b'existing header')
            with self.assertRaisesRegex(ValueError, 'measured ink'):
                build(root, metadata, output)
            self.assertEqual(output.read_bytes(), b'existing header')

    def test_missing_tile_hash_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            metadata, row = self.fixture(root)
            row['sha256'].pop('BGR/0001.BGR')
            metadata.write_text(json.dumps({'schema': 2, 'layouts': [row]}), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'measured ink'):
                build(root, metadata, root / 'layout.h')


if __name__ == '__main__':
    unittest.main()
