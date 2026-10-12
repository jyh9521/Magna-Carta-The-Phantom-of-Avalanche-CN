import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('inspect_minidump', Path(__file__).resolve().parents[1] / 'tools/inspect_minidump.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    data = bytearray(8192)
    struct.pack_into('<4sIII', data, 0, b'MDMP', 0xa793, 4, 32)
    for i, row in enumerate(((7, 56, 0x100), (4, 112, 0x180), (5, 20, 0x300), (6, 168, 0x340))):
        struct.pack_into('<III', data, 32 + 12 * i, *row)
    struct.pack_into('<I', data, 0x180, 1)
    struct.pack_into('<QIIII', data, 0x184, 0x200000, 0x1000, 0, 1, 0x280)
    name = 'fixture.dll'.encode('utf-16le')
    struct.pack_into('<I', data, 0x280, len(name))
    data[0x284:0x284 + len(name)] = name
    struct.pack_into('<IQII', data, 0x300, 1, 0x10000, 0x800, 0x800)
    struct.pack_into('<I4xI', data, 0x340, 7, 0xc000041d)
    struct.pack_into('<Q', data, 0x340 + 24, 0x200090)
    struct.pack_into('<II', data, 0x340 + 160, 716, 0x500)
    for offset, value in ((180, 0x10400), (184, 0x200090), (196, 0x10100)):
        struct.pack_into('<I', data, 0x500 + offset, value)
    struct.pack_into('<7I', data, 0x900, 0xc0000005, 0, 0, 0x200050, 2, 0, 0x78)
    struct.pack_into('<I', data, 0x950, 0x10007)
    for offset, value in ((180, 0x10300), (184, 0x200050), (196, 0x10200)):
        struct.pack_into('<I', data, 0x950 + offset, value)
    struct.pack_into('<II', data, 0xb00, 0, 0x200070)
    struct.pack_into('<II', data, 0xc00, 0, 0x200090)
    return data


class MinidumpTests(unittest.TestCase):
    def test_recovers_earlier_context(self):
        result = module.Dump(fixture()).inspect()
        prior = result['earlier_contexts'][0]
        self.assertEqual(prior['fault_location']['rva'], '0x50')
        self.assertEqual(prior['access_address'], '0x78')
        self.assertEqual(prior['frame_chain'][0]['return_site']['rva'], '0x70')

    def test_truncated_rejected(self):
        with self.assertRaises(ValueError): module.Dump(fixture()[:400])

    def test_wrong_arch_rejected(self):
        data = fixture()
        struct.pack_into('<H', data, 0x100, 9)
        with self.assertRaises(ValueError): module.Dump(data)

    def test_unmatched_context_ignored(self):
        data = fixture()
        struct.pack_into('<I', data, 0x950 + 184, 0x200051)
        self.assertEqual(module.Dump(data).inspect()['earlier_contexts'], [])

    def test_huge_directory_rejected(self):
        data = fixture()
        struct.pack_into('<I', data, 8, 0xffffffff)
        with self.assertRaises(ValueError): module.Dump(data)

    def test_full_memory_snapshot_without_exception_stream(self):
        data = fixture()
        struct.pack_into('<III', data, 32 + 12 * 2, 9, 32, 0x300)
        struct.pack_into('<QQQQ', data, 0x300, 1, 0x800, 0x10000, 0x800)
        struct.pack_into('<III', data, 32 + 12 * 3, 3, 52, 0x340)
        struct.pack_into('<I', data, 0x340, 1)
        struct.pack_into('<I', data, 0x344, 7)
        struct.pack_into('<II', data, 0x344 + 40, 716, 0x500)
        result = module.Dump(data).inspect()
        self.assertIsNone(result['recorded_exception'])
        self.assertEqual(result['earlier_contexts'][0]['thread'], 7)
        self.assertEqual(result['earlier_contexts'][0]['access_address'], '0x78')

    def test_invalid_full_memory_descriptor_rejected(self):
        data = fixture()
        struct.pack_into('<III', data, 32 + 12 * 2, 9, 32, 0x300)
        struct.pack_into('<QQQQ', data, 0x300, 1, 0x800, 0x10000, 0x10000)
        with self.assertRaises(ValueError): module.Dump(data)
