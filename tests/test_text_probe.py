import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_text_probe as m
import resource_sgi as sgi
from test_glyph_probe import inputs


def fixture():
    rows = []
    for identifier, name in [(5, '소울 블레이드'), (6, 'ASCII')]:
        record = bytearray([0x55] * 164)
        struct.pack_into('<I', record, 0, identifier)
        field = name.encode('cp949') + b'\0'
        record[4:4 + len(field)] = field
        rows.append(bytes(record))
    return struct.pack('<II', 2, 0x12345678) + b''.join(rows)


class SgiTests(unittest.TestCase):
    def test_roundtrip_preserves_header_and_unknown_bytes(self):
        self.assertEqual(sgi.parse(fixture()).to_bytes(), fixture())

    def test_only_original_name_span_changes(self):
        original = fixture()
        result = sgi.parse(original).replace_name(0, 5, '소울 블레이드'.encode('cp949'), '中文'.encode('cp949')).to_bytes()
        self.assertEqual(len(original), len(result))
        self.assertEqual(result[:12], original[:12])
        self.assertEqual(result[26:], original[26:])
        self.assertEqual(sgi.parse(result).name(0), '中文'.encode('cp949'))

    def test_unknown_identifier_or_name_rejected(self):
        table = sgi.parse(fixture())
        for identifier, name in [(9, table.name(0)), (5, b'wrong')]:
            with self.assertRaises(ValueError):
                table.replace_name(0, identifier, name, b'A')

    def test_overflow_empty_controls_rejected(self):
        table = sgi.parse(fixture())
        for target in [b'A' * 14, b'', b'A\0B', b'A\nB']:
            with self.assertRaises(ValueError):
                table.replace_name(0, 5, table.name(0), target)

    def test_truncation_count_mismatch(self):
        for data in [b'', fixture()[:-1], fixture() + b'\0', struct.pack('<II', 0, 16)]:
            with self.assertRaises(ValueError):
                sgi.parse(data)

    def test_invalid_ordinal_and_missing_terminator(self):
        table = sgi.parse(fixture())
        for ordinal in [True, -1, 2]:
            with self.assertRaises(ValueError):
                table.name(ordinal)
        data = bytearray(fixture()); data[12:112] = b'A' * 100
        with self.assertRaises(ValueError):
            sgi.parse(data).name(0)


class TextProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'; (self.source / 'Font').mkdir(parents=True)
        (self.source / 'Sgi').mkdir(); (self.source / 'Sgi/0000.sgi').write_bytes(fixture())
        self.fonts = inputs()
        for name, data in self.fonts.items(): (self.source / 'Font' / name).write_bytes(data)
        (self.source / 'MCAlpha.dll').write_bytes(b'fixture')
        (self.source / 'MagnaCarta.exe').write_bytes(b'fixture-exe')
        self.spec = dict(schema=1, format='sgi', resource='Sgi/0000.sgi', original_sha256=m.sha(fixture()),
                         original_size=len(fixture()), ordinal=0, identifier=5,
                         expected_hex='소울 블레이드'.encode('cp949').hex(), target='中文',
                         binaries={'MCAlpha.dll': m.sha(b'fixture'), 'MagnaCarta.exe': m.sha(b'fixture-exe')},
                         fonts={n: m.sha(d) for n,d in self.fonts.items()})
        self.spec_path = self.root / 'spec.json'; self.package = self.root / 'package'
        self.workspace = self.root / 'workspace'

    def build(self):
        self.spec_path.write_text(json.dumps(self.spec), encoding='utf8')
        return m.build(self.source, self.spec_path, self.package)

    def test_build_source_unchanged_and_native_target(self):
        state = self.build()
        self.assertEqual((self.source / 'Sgi/0000.sgi').read_bytes(), fixture())
        result = sgi.parse((self.package / 'modified.sgi').read_bytes())
        self.assertEqual(result.name(0), bytes.fromhex('f1e9d9fe'))
        self.assertFalse(state['in_game_display_verified'])

    def test_apply_verify_restore(self):
        self.build(); shutil.copytree(self.source, self.workspace)
        for command in ['apply', 'verify', 'restore']: m.operate(command, self.package, self.workspace)
        self.assertEqual((self.workspace / 'Sgi/0000.sgi').read_bytes(), fixture())
        self.assertFalse((self.workspace / '.text-probe.json').exists())

    def test_resource_hash_mismatch_rejects_before_output(self):
        (self.source / 'Sgi/0000.sgi').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): self.build()
        self.assertFalse(self.package.exists())

    def test_font_overlay_is_rejected(self):
        (self.source / 'Font/Kor0.dat').write_bytes(b'overlay')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): self.build()
        self.assertFalse(self.package.exists())

    def test_encoding_and_native_glyph_coverage(self):
        self.spec['target'] = '测试'
        with self.assertRaises(UnicodeEncodeError): self.build()
        self.assertFalse(self.package.exists())
        self.spec['target'] = '\n'
        with self.assertRaisesRegex(ValueError, 'glyph coverage'): self.build()

    def test_unsafe_path_and_existing_output(self):
        for value in ['../secret', '/secret', 'C:/secret', 'Sgi\\0000.sgi']:
            with self.assertRaises(ValueError): m.relative(value)
        self.build()
        with self.assertRaisesRegex(ValueError, 'already exists'): self.build()

    def test_workspace_drift_preserved(self):
        self.build(); shutil.copytree(self.source, self.workspace)
        m.operate('apply', self.package, self.workspace)
        path = self.workspace / 'Sgi/0000.sgi'; path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'drift'): m.operate('restore', self.package, self.workspace)
        self.assertEqual(path.read_bytes(), b'changed')

    def test_package_tamper_outside_name_rejected(self):
        self.build(); shutil.copytree(self.source, self.workspace)
        path = self.package / 'modified.sgi'; data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)
        state = m.read_json(self.package / 'probe.json'); state['modified_sha256'] = m.sha(data)
        (self.package / 'probe.json').write_text(json.dumps(state), encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'unexpected'): m.operate('apply', self.package, self.workspace)
        self.assertEqual((self.workspace / 'Sgi/0000.sgi').read_bytes(), fixture())

    def test_partial_copy_failure_recovers(self):
        self.build(); shutil.copytree(self.source, self.workspace)
        def fail_copy(source, target):
            Path(target).write_bytes(b'partial'); raise OSError('simulated')
        with patch.object(m.shutil, 'copyfile', side_effect=fail_copy):
            with self.assertRaises(OSError): m.operate('apply', self.package, self.workspace)
        self.assertEqual((self.workspace / 'Sgi/0000.sgi').read_bytes(), fixture())
        self.assertFalse((self.workspace / '.text-probe.json').exists())

    def test_two_builds_byte_exact(self):
        self.build(); second = self.root / 'second'
        m.build(self.source, self.spec_path, second)
        for name in ['original.sgi', 'modified.sgi', 'probe.json']:
            self.assertEqual((self.package / name).read_bytes(), (second / name).read_bytes())


if __name__ == '__main__': unittest.main()
