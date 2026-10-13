import hashlib
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_field_labels import patch
from native_text_codec import plan
from resource_font import parse


class FieldLabelTests(unittest.TestCase):
    def setUp(self):
        self.mapping={'中':{'index':0,'encoded_hex':'ca40'}}
        # Use a valid real encoder mapping shape from a synthetic native font.
        import struct
        header=bytearray(100);struct.pack_into('<H',header,88,14);header[90]=2
        struct.pack_into('<II',header,92,13151,13151*28)
        f=parse(bytes(header)+bytes(13151*28));self.mapping=plan('中',[f,f])
        self.raw=b'H'*252+'로웰숲'.encode('cp949')+bytes(12)+b'UNTOUCHED'
        self.row=dict(offset=252,capacity=18,source_sha256=hashlib.sha256(self.raw).hexdigest(),
                      expected_hex=self.raw[252:270].hex(),source='로웰숲',target='中')

    def test_label_only_no_length_or_tail_change(self):
        changed=patch(self.raw,self.row,self.mapping)
        self.assertEqual(len(changed),len(self.raw));self.assertEqual(changed[:252],self.raw[:252])
        self.assertEqual(changed[270:],self.raw[270:]);self.assertNotEqual(changed,self.raw)

    def test_reject_unknown_source_or_overflow(self):
        with self.assertRaises(ValueError):patch(self.raw+b'x',self.row,self.mapping)
        with self.assertRaises(ValueError):patch(self.raw,dict(self.row,target='中'*9),self.mapping)

    def test_reject_nonzero_tail_and_source_drift(self):
        with self.assertRaises(ValueError):patch(self.raw,dict(self.row,source='wrong'),self.mapping)
        modified=self.raw[:259]+b'X'+self.raw[260:]
        row=dict(self.row,source_sha256=hashlib.sha256(modified).hexdigest(),expected_hex=modified[252:270].hex(),target='中'*5)
        with self.assertRaises(ValueError):patch(modified,row,self.mapping)
