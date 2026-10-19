"""Owned structural samples; optional source-locked user resource coverage."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from resource_field_script import parse, parse_script_tail, inspect


def command(opcode, *parameters):
    return struct.pack('<15i', opcode, *(list(parameters) + [0]*(14-len(parameters))))


def tail():
    return (struct.pack('<4i', 1, 99, 1, 314159) + bytes(56)
            + struct.pack('<i', 1) + command(-271828, -1, 2147483647, -2147483648))


def field():
    header = bytearray(1060)
    struct.pack_into('<i', header, 0, 9)
    struct.pack_into('<i', header, 8, 17)
    return bytes(header) + bytes(6*4) + tail()


class FieldScriptTests(unittest.TestCase):
    def test_unknown_signed_opcodes_and_parameters_preserved(self):
        value = parse_script_tail(tail(), 0)
        self.assertTrue(value['exact_eof'])
        self.assertEqual(value['command_count'], 2)
        self.assertEqual(value['events'][0]['flag'], 99)
        self.assertEqual(value['events'][0]['conditions'][0]['opcode'], 314159)
        action = value['events'][0]['actions'][0]
        self.assertEqual(action['offset'], 76)
        self.assertEqual(action['opcode'], -271828)
        self.assertEqual(action['parameters'][:3], [-1, 2147483647, -2147483648])
        self.assertFalse(value['opcode_semantics_verified'])

    def test_existing_static_prefix_is_used_without_changes(self):
        data = field()
        value = parse(data)
        self.assertEqual(value['offset'], 1084)
        self.assertEqual(value['map_resource_id'], 9)
        self.assertEqual(value['playbook_id'], 17)
        self.assertEqual(value['source_sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(data, field())

    def test_all_truncated_tail_prefixes_rejected(self):
        data = tail()
        for end in range(len(data)):
            with self.subTest(end=end), self.assertRaises(ValueError):
                parse_script_tail(data[:end], 0)

    def test_zero_events_and_exact_eof(self):
        self.assertEqual(parse_script_tail(bytes(4), 0)['events'], [])
        self.assertEqual(parse_script_tail(struct.pack('<4i', 1, 2147483647, 0, 0), 0)
                         ['events'][0]['flag'], 2147483647)
        with self.assertRaisesRegex(ValueError, 'trailing'):
            parse_script_tail(bytes(5), 0)

    def test_source_hash_change_during_inspection_rejected(self):
        source = Mock()
        source.read_bytes.side_effect = [field(), field() + b'changed']
        with self.assertRaisesRegex(ValueError, 'source changed'):
            inspect(source)

    def test_negative_counts_flags_and_global_command_budget(self):
        for offset in (0, 4, 8, 72):
            data = bytearray(tail()); struct.pack_into('<i', data, offset, -1)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                parse_script_tail(data, 0)
        with self.assertRaisesRegex(ValueError, 'event count'):
            parse_script_tail(tail(), 0, max_events=0)
        with self.assertRaisesRegex(ValueError, 'command count'):
            parse_script_tail(tail(), 0, max_commands=1)
        with self.assertRaisesRegex(ValueError, 'command count'):
            parse_script_tail(struct.pack('<4i', 1, 0, 0, 2147483647), 0)

    def test_invalid_offsets_and_limits(self):
        for offset in (-1, len(tail())+1, True, 0.0):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                parse_script_tail(tail(), offset)
        for limit in (-1, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                parse_script_tail(tail(), 0, max_events=limit)

    def test_cli_compact_report_and_path_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'input/owned.fld'
            source.parent.mkdir(); source.write_bytes(field())
            report = root/'report.json'
            cmd = [sys.executable, str(ROOT/'tools/resource_field_script.py'),
                   '--source', str(source), '--report', str(report)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('FIELD_SCRIPT_INSPECT PASS', result.stdout)
            value = json.loads(report.read_text(encoding='utf8'))
            self.assertTrue(value['source_unchanged'])
            self.assertFalse(value['parameters_exported'])
            self.assertNotIn('parameters', value['events'][0]['actions'][0])
            before = report.read_bytes()
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)
            self.assertEqual(report.read_bytes(), before)
            cmd[-1] = str(source.parent/'forbidden.json')
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)
            self.assertFalse((source.parent/'forbidden.json').exists())
            self.assertEqual(source.read_bytes(), field())

    @unittest.skipUnless((ROOT/'runtime/data/Field/0757.fld').is_file(),
                         'Requires user-supplied Field0757')
    def test_optional_source_locked_stairwell_structure(self):
        source = ROOT/'runtime/data/Field/0757.fld'
        data = source.read_bytes()
        self.assertIn(hashlib.sha256(data).hexdigest(), (
            '7b92ac0c7fe82aa2d63761c6442ff40f43c0b947644e4f03ea3b48e868b91a87',
            '13d92e10cddf9bb490bbcfd76c81cf6b7c90b12afebc34a7dd1ba3fd6dff21cf'))
        value = parse(data)
        self.assertEqual(value['offset'], 0x9b4)
        self.assertEqual(len(value['events']), 4)
        event = value['events'][2]
        self.assertEqual([row['opcode'] for row in event['actions']], [7, 202, 1, 700, 1, 8])
        self.assertEqual(event['actions'][1]['parameters'][:3], [10000, 5, 1])
        self.assertTrue(inspect(source)['source_unchanged'])


if __name__ == '__main__':
    unittest.main()
