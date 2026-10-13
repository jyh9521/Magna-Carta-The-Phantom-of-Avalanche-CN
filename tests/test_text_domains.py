import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import patch_text_domains as m


class FakePE:
    def __init__(self,**kwargs):
        self.FILE_HEADER=type('File',(),dict(Machine=0x14c))()
        self.OPTIONAL_HEADER=type('Opt',(),dict(SizeOfImage=4096))()
        self.sections=[]
    def get_rva_from_offset(self,value):return value
    def get_section_by_rva(self,value):return type('Section',(),dict(Name=b'.data\0\0\0'))()
    def close(self):pass


class TextDomainTests(unittest.TestCase):
    def setUp(self):
        self.raw=b'CODE\0%s item\0UNCHANGED'
        self.row=dict(offset=5,expected_hex=b'%s item'.hex(),target='%s x',display_domain='game_native_font',evidence='controlled native font fixture')
        self.plan=dict(source_sha256=m.sha(self.raw),source_size=len(self.raw),native_fields=[self.row],dialogs=[])
        self.pe=patch('pefile.PE',FakePE);self.pe.start();self.addCleanup(self.pe.stop)

    def test_native_field_changes_only_original_span(self):
        changed,r=m.patch(self.raw,self.plan,{})
        self.assertEqual(changed[:5],self.raw[:5]);self.assertEqual(changed[13:],self.raw[13:])
        self.assertEqual(changed[5:13],b'%s x\0\0\0\0');self.assertEqual(len(r),1)

    def test_original_hash_size_and_bytes_are_required(self):
        for key,value in [('source_sha256','0'*64),('source_size',1)]:
            p=copy.deepcopy(self.plan);p[key]=value
            with self.assertRaises(ValueError):m.patch(self.raw,p,{})
        self.row['expected_hex']=b'wrong'.hex()
        with self.assertRaises(ValueError):m.patch(self.raw,self.plan,{})

    def test_no_overflow_format_changes_or_system_ansi_private_bytes(self):
        for key,value in [('target','x'*20),('target','%d x'),('display_domain','messagebox_ansi'),('evidence','')]:
            p=copy.deepcopy(self.plan);p['native_fields'][0][key]=value
            with self.assertRaises(ValueError):m.patch(self.raw,p,{})

    def test_duplicate_and_out_of_range_offsets_are_rejected(self):
        self.plan['native_fields'].append(copy.deepcopy(self.row))
        with self.assertRaises(ValueError):m.patch(self.raw,self.plan,{})
        self.plan['native_fields'].pop()
        for offset in [-1,100,True]:
            self.row['offset']=offset
            with self.assertRaises(ValueError):m.patch(self.raw,self.plan,{})

    def test_non_data_section_is_rejected(self):
        with patch.object(FakePE,'get_section_by_rva',return_value=type('Code',(),dict(Name=b'.text\0\0\0'))()):
            with self.assertRaises(ValueError):m.patch(self.raw,self.plan,{})


if __name__=='__main__':unittest.main()
