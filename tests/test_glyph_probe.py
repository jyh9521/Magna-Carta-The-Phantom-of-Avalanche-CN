import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_glyph_probe as m
from resource_font import parse


def inputs():
    result = {}
    for family in ('Eng', 'Kor', 'Chi'):
        count = {'Eng': 351, 'Kor': 6239, 'Chi': 13151}[family]
        for i in (0, 1):
            header = bytearray(100)
            header[:4] = b'TEST'
            struct.pack_into('<H', header, 88, 8)
            header[90] = 1
            struct.pack_into('<II', header, 92, count, count * 8)
            result[f'{family}{i}.dat'] = bytes(header) + bytes([2 if family == 'Chi' else 1]) * count * 8
    return result


class GlyphProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / 'Font').mkdir(parents=True)
        self.data = inputs()
        for name, data in self.data.items():
            (self.source / 'Font' / name).write_bytes(data)
        (self.source / 'MCAlpha.dll').write_bytes(b'fixture-not-game')
        self.spec = dict(schema=1, fonts={n: m.sha(d) for n, d in self.data.items()},
                         binaries={'MCAlpha.dll': m.sha(b'fixture-not-game')},
                         mappings=[dict(source='이', target='中'), dict(source='다', target='文')])
        self.spec_path = self.root / 'spec.json'
        self.save_spec()
        self.package = self.root / 'package'
        self.workspace = self.root / 'workspace'

    def save_spec(self):
        self.spec_path.write_text(json.dumps(self.spec), encoding='utf-8')

    def build(self):
        return m.build(self.source, self.spec_path, self.package)

    def test_only_selected_glyph_bytes_change(self):
        output, changes = m.transform(self.data, self.spec['mappings'])
        self.assertEqual(len(changes), 4)
        for name, original in self.data.items():
            allowed = {p for c in changes if c['file'] == name
                       for p in range(c['offset'], c['offset'] + c['length'])}
            differing = {p for p, (a, b) in enumerate(zip(original, output[name])) if a != b}
            self.assertEqual(allowed, differing)
            self.assertEqual(len(original), len(output[name]))
            self.assertEqual(parse(original).header, parse(output[name]).header)

    def test_build_preserves_source_and_originals(self):
        state = self.build()
        self.assertEqual(set(state['modified']), {'Kor0.dat', 'Kor1.dat'})
        for name, data in self.data.items():
            self.assertEqual((self.source / 'Font' / name).read_bytes(), data)
        for name in state['modified']:
            self.assertEqual((self.package / 'original' / name).read_bytes(), self.data[name])
        self.assertFalse(state['game_started'])

    def test_apply_verify_restore_exact(self):
        self.build()
        shutil.copytree(self.source, self.workspace)
        m.operate('apply', self.package, self.workspace)
        m.operate('verify', self.package, self.workspace)
        m.operate('restore', self.package, self.workspace)
        for name, data in self.data.items():
            self.assertEqual((self.workspace / 'Font' / name).read_bytes(), data)
        self.assertFalse((self.workspace / '.glyph-probe.json').exists())

    def test_unknown_hash_fails_before_output(self):
        (self.source / 'Font' / 'Kor0.dat').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.build()
        self.assertFalse(self.package.exists())

    def test_unknown_binary_fails_before_output(self):
        (self.source / 'MCAlpha.dll').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.build()
        self.assertFalse(self.package.exists())

    def test_duplicate_slot_rejected(self):
        self.spec['mappings'].append(self.spec['mappings'][0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            m.transform(self.data, self.spec['mappings'])

    def test_unsupported_encoding_rejected(self):
        with self.assertRaises(UnicodeEncodeError):
            m.slot('测')
        with self.assertRaises(ValueError):
            m.slot('\n')
        with self.assertRaises(ValueError):
            m.slot('中文')

    def test_geometry_mismatch_rejected(self):
        data = dict(self.data)
        font = bytearray(data['Chi0.dat'])
        struct.pack_into('<H', font, 88, 7)
        struct.pack_into('<I', font, 96, 13151 * 7)
        data['Chi0.dat'] = bytes(font[:100]) + b'\x02' * (13151 * 7)
        with self.assertRaisesRegex(ValueError, 'geometry'):
            m.transform(data, self.spec['mappings'])

    def test_output_reuse_and_nested_source_rejected(self):
        self.build()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.build()
        with self.assertRaisesRegex(ValueError, 'separate'):
            m.build(self.source, self.spec_path, self.source / 'output')

    def test_restore_refuses_drift_without_overwrite(self):
        self.build()
        shutil.copytree(self.source, self.workspace)
        m.operate('apply', self.package, self.workspace)
        path = self.workspace / 'Font' / 'Kor1.dat'
        path.write_bytes(b'user-change')
        first = (self.workspace / 'Font' / 'Kor0.dat').read_bytes()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            m.operate('restore', self.package, self.workspace)
        self.assertEqual(path.read_bytes(), b'user-change')
        self.assertEqual((self.workspace / 'Font' / 'Kor0.dat').read_bytes(), first)

    def test_corrupt_package_rejected_before_apply(self):
        self.build()
        shutil.copytree(self.source, self.workspace)
        (self.package / 'Font' / 'Kor1.dat').write_bytes(b'broken')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            m.operate('apply', self.package, self.workspace)
        self.assertEqual((self.workspace / 'Font' / 'Kor0.dat').read_bytes(), self.data['Kor0.dat'])

    def test_double_apply_rejected(self):
        self.build()
        shutil.copytree(self.source, self.workspace)
        m.operate('apply', self.package, self.workspace)
        with self.assertRaisesRegex(ValueError, 'already applied'):
            m.operate('apply', self.package, self.workspace)

    def test_partial_apply_io_failure_recovers(self):
        self.build()
        shutil.copytree(self.source, self.workspace)
        real_copy = shutil.copyfile

        def fail_second(source, target):
            if Path(target).name == 'Kor1.dat':
                Path(target).write_bytes(b'partial')
                raise OSError('simulated write error')
            return real_copy(source, target)

        with patch.object(m.shutil, 'copyfile', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'simulated'):
                m.operate('apply', self.package, self.workspace)
        for name, data in self.data.items():
            self.assertEqual((self.workspace / 'Font' / name).read_bytes(), data)
        self.assertFalse((self.workspace / '.glyph-probe.json').exists())

    def test_partial_restore_io_failure_recovers(self):
        self.build()
        shutil.copytree(self.source, self.workspace)
        m.operate('apply', self.package, self.workspace)
        before = {n: (self.workspace / 'Font' / n).read_bytes() for n in self.data}
        real_copy = shutil.copyfile

        def fail_second(source, target):
            if Path(target).name == 'Kor1.dat':
                Path(target).write_bytes(b'partial')
                raise OSError('simulated write error')
            return real_copy(source, target)

        with patch.object(m.shutil, 'copyfile', side_effect=fail_second):
            with self.assertRaises(OSError):
                m.operate('restore', self.package, self.workspace)
        for name, data in before.items():
            self.assertEqual((self.workspace / 'Font' / name).read_bytes(), data)
        m.operate('verify', self.package, self.workspace)


if __name__ == '__main__':
    unittest.main()
