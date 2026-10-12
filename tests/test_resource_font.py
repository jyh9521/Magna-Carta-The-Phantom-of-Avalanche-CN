import sys
from pathlib import Path
import struct
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import resource_font as m

def fixture(variable=False):
    header=bytearray(100);header[:4]=b'TEST';header[42]=int(variable)
    struct.pack_into('<H',header,88,8);header[90]=1
    struct.pack_into('<II',header,92,3,24)
    return bytes(header)+(bytes([4,8,7]) if variable else b'')+bytes([1,2,4,8,16,32,64,128])*3

class FontTests(unittest.TestCase):
    def test_roundtrip_preserves_unknown_header(self):
        for variable in [False,True]:
            data=fixture(variable);self.assertEqual(m.parse(data).to_bytes(),data)

    def test_lsb_first_pixels_and_advance(self):
        font=m.parse(fixture(True));self.assertEqual(font.width(0),4)
        self.assertEqual(font.pixels(0)[0],[1,0,0,0]);self.assertEqual(font.pixels(0)[1],[0,1,0,0])

    def test_glyph_replace_changes_only_slot(self):
        original=m.parse(fixture());modified=original.replace_glyph(1,b'\xff'*8)
        self.assertEqual(modified.header,original.header);self.assertEqual(modified.glyph(0),original.glyph(0))
        self.assertEqual(modified.glyph(2),original.glyph(2));self.assertEqual(modified.glyph(1),b'\xff'*8)

    def test_truncation_and_bitmap_length_rejected(self):
        for data in [fixture()[:99],fixture()[:-1],fixture()+b'\0']:
            with self.assertRaises(ValueError):m.parse(data)

    def test_invalid_metrics_rejected(self):
        data=bytearray(fixture());struct.pack_into('<I',data,96,999)
        with self.assertRaises(ValueError):m.parse(data)
        with self.assertRaises(ValueError):m.parse(fixture(True)[:100]+bytes([9,8,7])+fixture()[100:])

    def test_slot_and_replacement_bounds(self):
        font=m.parse(fixture())
        for index in [-1,3,True]:
            with self.assertRaises(ValueError):font.glyph(index)
        with self.assertRaises(ValueError):font.replace_glyph(0,b'\xff')

    def test_native_ascii_hangul_hanja_routes(self):
        self.assertEqual(m.native_slot(b'A'),('Eng',33,1))
        self.assertEqual(m.native_slot('가'.encode('cp949')),('Kor',1,2))
        self.assertEqual(m.native_slot('中'.encode('cp949')),('Chi',0xf1e9-0xcaa0,2))

    def test_pair_control_and_encoding_failures(self):
        for data in [b'',b'\n',b'\xca']:
            with self.assertRaises(ValueError):m.native_slot(data)
        rows=m.coverage('测试',{})
        self.assertEqual([r['status'] for r in rows],['not_cp949','not_cp949'])

    def test_extended_cp949_is_not_assumed_supported(self):
        pair=b'\x81\x41';family,index,count=m.native_slot(pair)
        self.assertEqual(count,1);self.assertNotEqual(count,len(pair))

if __name__=='__main__':unittest.main()
