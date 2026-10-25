"""Owned Field samples and optional checks of source-locked local resources."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_map_points as tool


def command(opcode, *args):
    return struct.pack('<15i', opcode, *(list(args) + [0] * (14-len(args))))


def event(conditions, actions, flag=0):
    return (struct.pack('<2i', flag, len(conditions)) + b''.join(conditions)
            + struct.pack('<i', len(actions)) + b''.join(actions))


def sample(events=None, map_id=9, region_ids=(7,)):
    if events is None:
        events = [event([command(304, 10000, 7)], [command(4, 2)])]
    header = bytearray(1060)
    struct.pack_into('<i', header, 0, map_id)
    data = bytes(header) + bytes(4*4) + struct.pack('<i', len(region_ids))
    for identifier in region_ids:
        region = struct.pack('<3fi', 4, 5, 6, identifier)
        for corner in range(8):
            region += struct.pack('<3f', 4+2*(corner&1)-1, 5+2*((corner>>1)&1)-1, 6+2*((corner>>2)&1)-1)
        data += region
    return data + bytes(4) + struct.pack('<i', len(events)) + b''.join(events)


class MapPointsTests(unittest.TestCase):
    def points(self, events=None, **kwargs):
        return tool.extract_points(tool.parse_field(sample(events, **kwargs)), {2: 31})

    def test_region_center_transition_and_binary_contract(self):
        points, skipped = self.points()
        self.assertFalse(skipped)
        row = points[0]
        self.assertEqual((row['x'], row['y'], row['z']), (4, 5, 6))
        self.assertEqual(row['region_min'], [3, 4, 5])
        self.assertEqual(row['region_max'], [5, 6, 7])
        self.assertEqual(row['target_map'], 31)
        binary = tool.encode_points(1, 9, points)
        self.assertEqual(len(binary), 52)
        self.assertEqual(tool.HEADER.unpack_from(binary), (b'MCP1', 1, 9, 1))
        self.assertEqual(tool.ROW.unpack_from(binary, 16), (0, 7, 2, 31, 0, 0, 4, 5, 6))

    def test_action5_and_alternate_playable_actor(self):
        points, _ = self.points([event([command(304, 10001, 7)], [command(5, 2, 4, 5)])])
        self.assertEqual(points[0]['target_field'], 2)
        self.assertEqual(points[0]['trigger_actor'], 1)
        self.assertEqual(points[0]['action_opcode'], 5)

    def test_only_matching_runtime_actor_is_contract_not_guessed_player(self):
        points, _ = self.points([event([command(304, 10042, 7)], [command(4, 2)])])
        self.assertEqual(points[0]['trigger_actor'], 42)
        for actor in (-1, 9999, 20000):
            points, skipped = self.points([event([command(304, actor, 7)], [command(4, 2)])])
            self.assertFalse(points)
            self.assertIn('supported actor', skipped[0]['reason'])

    def test_extra_conditions_and_limited_event_remain_unevaluated(self):
        points, _ = self.points([event([command(304, 10000, 7), command(101, 8)], [command(4, 2)], 3)])
        self.assertEqual(points[0]['flags'], 3)
        self.assertEqual(self.points([event([command(304, 10000, 7)], [command(4, 2)], 1)])[0][0]['flags'], 2)

    def test_multiple_regions_and_nonspatial_transitions_skipped(self):
        for conditions in ([], [command(100, 7)], [command(304, 10000, 7)]*2):
            points, skipped = self.points([event(conditions, [command(4, 2)])])
            self.assertFalse(points)
            self.assertEqual(len(skipped), 1)

    def test_dialogue_movement_without_transition_is_not_exit(self):
        points, skipped = self.points([event([command(304, 10000, 7)], [command(202, 10000, 3), command(700, 1)])])
        self.assertFalse(points)
        self.assertFalse(skipped)

    def test_multiple_targets_remain_separate_and_ambiguous(self):
        points, _ = self.points([event([command(304, 10000, 7)], [command(4, 2), command(5, 8)])])
        self.assertEqual([p['target_field'] for p in points], [2, 8])
        self.assertEqual([p['target_map'] for p in points], [31, -1])
        self.assertEqual([p['flags'] for p in points], [1, 1])

    def test_bad_target_and_missing_region_skipped(self):
        for conditions, actions in (([command(304, 10000, 8)], [command(4, 2)]),
                                    ([command(304, 10000, 7)], [command(4, -1)])):
            points, skipped = self.points([event(conditions, actions)])
            self.assertFalse(points)
            self.assertTrue(skipped)

    def test_exact_eof_unique_regions_finite_coordinates_and_map_range(self):
        for data in (sample()+b'x', sample()[:-1], sample(region_ids=(7, 7)), sample(map_id=-2), sample(map_id=10000)):
            with self.assertRaises(ValueError):
                tool.parse_field(data)
        broken = bytearray(sample())
        struct.pack_into('<f', broken, 1080, float('nan'))
        with self.assertRaises(ValueError):
            tool.parse_field(broken)

    def test_no_map_and_zero_points_have_explicit_header(self):
        binary = tool.encode_points(1, -1, [])
        self.assertEqual(tool.HEADER.unpack(binary), (b'MCP1', 1, 0xffffffff, 0))
        self.assertEqual(self.points([], map_id=-1), ([], []))

    def test_oversize_is_rejected_not_truncated(self):
        events = [event([command(304, 10000, 7)], [command(4, 2)])]*65
        with self.assertRaisesRegex(ValueError, 'exceeds 64'):
            self.points(events)

    def test_build_manifest_source_hashes_rejections_and_nonoverwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root/'Field'; source.mkdir()
            engine = root/'engine'; engine.write_bytes(b'owned engine fixture')
            (source/'0001.fld').write_bytes(sample())
            (source/'0002.fld').write_bytes(sample([], map_id=31))
            (source/'0003.fld').write_bytes(b'bad field')
            output = root/'points'
            with patch.object(tool, 'ENGINE_SHA256S', {tool.digest(engine.read_bytes())}):
                result = tool.build(source, engine, output)
                self.assertEqual((len(result['accepted']), len(result['rejected'])), (2, 1))
                self.assertEqual(result['marker_count'], 1)
                self.assertEqual(result['accepted'][0]['points'][0]['target_map'], 31)
                self.assertEqual(result['accepted'][0]['poi_sha256'], tool.digest((output/'0001.poi').read_bytes()))
                self.assertEqual((output/'0002.poi').stat().st_size, 16)
                self.assertFalse((output/'0003.poi').exists())
                self.assertEqual(json.loads((output/'manifest.json').read_text()), result)
                self.assertNotIn(str(root), (output/'manifest.json').read_text())
                with self.assertRaisesRegex(ValueError, 'new and outside'):
                    tool.build(source, engine, output)

    def test_wrong_engine_and_changed_source_fail_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root/'Field'; source.mkdir()
            engine = root/'engine'; engine.write_bytes(b'owned engine fixture')
            field = source/'0001.fld'; field.write_bytes(sample())
            output = root/'points'
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                tool.build(source, engine, output)
            self.assertFalse(output.exists())
            original = tool.extract_points

            def mutate(*args):
                field.write_bytes(sample()+b'x')
                return original(*args)

            with patch.object(tool, 'ENGINE_SHA256S', {tool.digest(engine.read_bytes())}), patch.object(tool, 'extract_points', side_effect=mutate):
                with self.assertRaisesRegex(ValueError, 'sources changed'):
                    tool.build(source, engine, output)
            self.assertFalse(output.exists())

    def test_real_stairwell_fields_when_present(self):
        source = ROOT/'runtime/data/Field'
        engine = ROOT/'runtime/data/MCAlpha.dll'
        if not engine.exists() or not (source/'0751.fld').exists():
            self.skipTest('Optional local source resources absent')
        if tool.digest(engine.read_bytes()) not in tool.ENGINE_SHA256S:
            self.skipTest('Optional local engine is unsupported')
        a, _ = tool.extract_points(tool.parse_field((source/'0751.fld').read_bytes()), {})
        b, _ = tool.extract_points(tool.parse_field((source/'0757.fld').read_bytes()), {})
        self.assertEqual([(p['region_id'], p['target_field'], p['trigger_actor']) for p in a], [(0, 750, 1), (1, 754, 1), (3, 757, 1)])
        self.assertEqual([(p['region_id'], p['target_field'], p['trigger_actor']) for p in b], [(0, 751, 0)])


if __name__ == '__main__':
    unittest.main()
