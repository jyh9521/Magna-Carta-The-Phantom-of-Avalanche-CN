from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from resource_field import parse, audit


def sample():
    header = bytearray(1060)
    struct.pack_into('<i', header, 0, 9)
    struct.pack_into('<i', header, 8, 17)
    struct.pack_into('<I', header, 244, 1)
    actor = bytearray(52); struct.pack_into('<ii3f', actor, 0, 7, 21, 1, 2, 3)
    obj = bytearray(56); struct.pack_into('<iiI3f', obj, 0, 8, 22, 3, 4, 5, 6)
    region = bytearray(112); struct.pack_into('<3fi', region, 0, 0, 0, 0, 44)
    for i in range(8):
        struct.pack_into('<3f', region, 16+i*12, (i&1)*2-1, ((i>>1)&1)*2-1, ((i>>2)&1)*2-1)
    data = bytes(header)+struct.pack('<I', 1)+bytes(76)+struct.pack('<I', 1)+actor+struct.pack('<I', 1)+obj
    data += struct.pack('<I', 1)+bytes(124)+struct.pack('<I', 1)+region
    data += struct.pack('<I', 1)+struct.pack('<5I', 1, 2, 3, 4, 1)+bytes(152)
    data += struct.pack('<3I', 5, 1, 1)+bytes(228)
    return data+b'OWNED SCRIPT TAIL'


class FieldPrefixTests(unittest.TestCase):
    def test_native_serialized_strides_and_opaque_tail(self):
        data = sample(); result = parse(data)
        self.assertEqual(result['map_resource_id'], 9)
        self.assertEqual(result['playbook_id'], 17)
        self.assertEqual(result['actors'][0], {'resource_id': 21, 'position': (1., 2., 3.)})
        self.assertEqual(result['objects'][0]['position'], (4., 5., 6.))
        self.assertEqual(result['objects'][0]['kind'], 3)
        self.assertEqual(result['region_volumes'][0]['id'], 44)
        self.assertEqual(result['remaining_opaque_bytes'], len(b'OWNED SCRIPT TAIL'))
        self.assertFalse(result['full_file_parsed']); self.assertFalse(result['navigation_verified'])

    def test_truncation_rejected_at_each_known_boundary(self):
        data = sample()
        for size in [0, 1059, 1060, 1200, len(data)-len(b'OWNED SCRIPT TAIL')-1]:
            self.assertRaisesRegex(ValueError, 'Truncated Field', parse, data[:size])

    def test_unbounded_counts_rejected(self):
        data = bytearray(sample()); struct.pack_into('<I', data, 1060, 0xffffffff)
        self.assertRaisesRegex(ValueError, 'count exceeds', parse, data)

    def test_nonfinite_coordinates_rejected(self):
        data = bytearray(sample()); struct.pack_into('<f', data, 1060+4+76+4+52+4+12, float('nan'))
        self.assertRaisesRegex(ValueError, 'coordinate', parse, data)

    def test_missing_map_sentinel_is_not_normalized_to_a_real_map(self):
        data = bytearray(sample()); struct.pack_into('<i', data, 0, -1)
        self.assertEqual(parse(data)['map_resource_id'], -1)

    def test_unknown_loader_image_rejected_before_resource_scan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'field').mkdir(); (root/'maps').mkdir(); engine = root/'owned.dll'; engine.write_bytes(b'owned unknown image')
            self.assertRaisesRegex(ValueError, 'Unsupported Field loader', audit, root/'field', root/'maps', engine)

    def test_report_guard_preserves_existing_and_source_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/'field'; source.mkdir(); maps = root/'maps'; maps.mkdir()
            engine = root/'owned.dll'; engine.write_bytes(b'owned unknown image')
            existing = root/'report.json'; existing.write_bytes(b'keep')
            for report in [existing, source/'report.json', maps/'report.json']:
                result = subprocess.run([sys.executable, str(ROOT/'tools/resource_field.py'), '--source', str(source),
                                         '--maps', str(maps), '--engine', str(engine), '--report', str(report)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(existing.read_bytes(), b'keep'); self.assertFalse((source/'report.json').exists())

    @unittest.skipUnless((ROOT/'runtime/data/MCAlpha.dll').is_file(), 'Requires supported user-supplied loader image')
    def test_source_locked_audit_of_owned_field_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/'field'; source.mkdir(); maps = root/'maps'; maps.mkdir()
            field = source/'0001.fld'; field.write_bytes(sample()); (maps/'0009.wrd').write_bytes(b'owned map presence fixture')
            result = audit(source, maps, ROOT/'runtime/data/MCAlpha.dll')
            self.assertEqual(len(result['accepted_prefixes']), 1); self.assertEqual(result['rejected'], [])
            self.assertTrue(result['accepted_prefixes'][0]['map_file_exists'])
            self.assertTrue(result['source_unchanged']); self.assertFalse(result['game_started'])
            self.assertEqual(field.read_bytes(), sample())
