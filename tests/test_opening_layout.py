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
        metadata = root / 'metadata.json'
        metadata.write_text(json.dumps({'schema': 1, 'locale': 'fixture', 'layouts': [row]}), encoding='utf8')
        return metadata, row

    def test_generated_header_uses_measured_center_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            metadata, _ = self.fixture(root)
            output = root / 'generated/layout.h'
            self.assertEqual(build(root, metadata, output), 1)
            original = output.read_bytes()
            self.assertIn(b'{42, 128.0f, 128.0f}', original)
            build(root, metadata, output)
            self.assertEqual(output.read_bytes(), original)

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
            metadata.write_text(json.dumps({'schema': 1, 'layouts': [row]}), encoding='utf8')
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
            metadata.write_text(json.dumps({'schema': 1, 'layouts': [row]}), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'measured ink'):
                build(root, metadata, root / 'layout.h')


if __name__ == '__main__':
    unittest.main()
