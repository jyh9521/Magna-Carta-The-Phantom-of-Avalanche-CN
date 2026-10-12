from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_text_codec as m


class FontFixture:
    count = 13151


class CodecTests(unittest.TestCase):
    def test_roundtrip_with_ascii_and_controls(self):
        mapping = m.plan('中文测试汉龙', [FontFixture(), FontFixture()])
        text = '中文测试$n A %s {0}\n汉龙'
        self.assertEqual(m.decode(m.encode(text, mapping), mapping), text)

    def test_planning_deterministic(self):
        a = m.plan('龙汉测试中文', [FontFixture()])
        b = m.plan('中文测试汉龙中文', [FontFixture()])
        self.assertEqual(a, b)

    def test_private_slots_are_never_cp949(self):
        for pair, index in m.private_slots([FontFixture()]):
            with self.assertRaises(UnicodeDecodeError): pair.decode('cp949')
            self.assertTrue(0 <= index < 13151)
            self.assertNotIn(pair[1], m.RESERVED_TRAIL)

    def test_no_null_or_format_directive_bytes(self):
        for pair, index in m.private_slots([FontFixture()]):
            self.assertTrue(all(byte >= 0x40 for byte in pair))
            self.assertNotIn(b'$', [pair[:1], pair[1:]])
            self.assertNotIn(b'%', [pair[:1], pair[1:]])

    def test_capacity_and_unknown_character_rejected(self):
        class TinyFont: count = 1
        with self.assertRaises(ValueError): m.plan('中文', [TinyFont()])
        with self.assertRaises(ValueError): m.encode('测试', {})

    def test_truncation_and_embedded_terminator_rejected(self):
        mapping = m.plan('中', [FontFixture()])
        pair = bytes.fromhex(mapping['中']['encoded_hex'])
        with self.assertRaises(ValueError): m.decode(pair[:1], mapping)
        with self.assertRaises(ValueError): m.encode('中\0', mapping)
        with self.assertRaises(ValueError): m.decode(pair+b'\0', mapping)

    def test_duplicate_and_valid_cp949_mapping_rejected(self):
        mapping = m.plan('中文', [FontFixture()]); mapping['文'] = mapping['中']
        with self.assertRaises(ValueError): m.validate(mapping)
        mapping = {'中': dict(encoded_hex='f1e9', index=10057)}
        with self.assertRaises(ValueError): m.validate(mapping)

    def test_surrogates_and_index_mismatch_rejected(self):
        with self.assertRaises(ValueError): m.plan('\ud800', [FontFixture()])
        mapping = m.plan('中', [FontFixture()]); mapping['中']['index'] = 42
        with self.assertRaises(ValueError): m.validate(mapping)


if __name__ == '__main__': unittest.main()
