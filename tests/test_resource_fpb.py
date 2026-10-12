import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('resource_fpb', Path(__file__).resolve().parents[1] / 'tools/resource_fpb.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FpbTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(module.rebuild(module.parse(b'\0' * 4)), b'\0' * 4)

    def test_tags_and_control_bytes_preserved(self):
        entries = [(17, b'A$nB'), (88, '시험'.encode('cp949'))]
        self.assertEqual(module.parse(module.rebuild(entries)), entries)

    def test_truncation(self):
        with self.assertRaises(ValueError):
            module.parse(struct.pack('<I', 0xffffffff))

    def test_terminator(self):
        data = module.rebuild([(1, b'A')])[:-1] + b'X'
        with self.assertRaises(ValueError):
            module.parse(data)

    def test_bad_offset(self):
        data = bytearray(module.rebuild([(1, b'A')]))
        struct.pack_into('<I', data, 8, 9)
        with self.assertRaises(ValueError):
            module.parse(data)

    def test_embedded_null_rejected(self):
        with self.assertRaises(ValueError):
            module.rebuild([(1, b'A\0B')])


if __name__ == '__main__':
    unittest.main()
