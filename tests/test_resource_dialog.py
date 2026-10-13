import copy
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import resource_dialog as m


def fixture():
    controls=[dict(ordinal=i,header_hex=struct.pack('<IIIhhhhI',10+i,0,0x50010000,4,5+i*12,40,10,100+i).hex(),
                   identifier=100+i,klass=dict(ordinal=128),title=text,extra_hex='aabb' if i==1 else '')
              for i,text in enumerate(['Original label',dict(ordinal=22)])]
    return dict(header_hex=struct.pack('<HHIIIHhhhh',1,65535,3,0,0x40,2,0,0,90,60).hex(),
                menu='',klass='',title='Dialog',font=dict(header_hex=struct.pack('<HHBB',10,0,0,1).hex(),face='System'),controls=controls)


class DialogTests(unittest.TestCase):
    def test_byte_exact_roundtrip_with_ordinals_and_creation_data(self):
        table=fixture();raw=m.rebuild(table)
        self.assertEqual(m.parse(raw),table);self.assertEqual(m.rebuild(m.parse(raw)),raw)

    def test_unicode_changes_realign_controls_and_preserve_attributes(self):
        original=m.rebuild(fixture())
        result=m.replace_text(original,'设置',[dict(ordinal=0,identifier=100,expected='Original label',target='确定')])
        a,b=m.parse(original),m.parse(result)
        self.assertEqual(b['title'],'设置');self.assertEqual(b['controls'][0]['title'],'确定')
        self.assertEqual(a['header_hex'],b['header_hex']);self.assertEqual(a['font'],b['font'])
        for x,y in zip(a['controls'],b['controls']):
            for key in ('header_hex','identifier','klass','extra_hex'):self.assertEqual(x[key],y[key])
        self.assertLess(len(result),len(original))

    def test_all_truncated_prefixes_are_rejected(self):
        raw=m.rebuild(fixture())
        for n in range(len(raw)):
            with self.assertRaises(ValueError):m.parse(raw[:n])

    def test_nonzero_alignment_and_trailing_bytes_are_rejected(self):
        raw=m.rebuild(fixture())
        with self.assertRaises(ValueError):m.parse(raw+b'\0')
        table=fixture();table['title']='D'
        raw=bytearray(m.rebuild(table));pos=26
        for _ in range(3):_,pos=m.atom(raw,pos)
        pos+=6;_,pos=m.atom(raw,pos)
        if pos%4:
            raw[pos]=0x13
            with self.assertRaises(ValueError):m.parse(bytes(raw))

    def test_source_text_and_control_id_mismatch_are_rejected(self):
        raw=m.rebuild(fixture())
        for key,value in [('expected','wrong'),('identifier',101),('ordinal',-1),('ordinal',True)]:
            target=dict(ordinal=0,identifier=100,expected='Original label',target='确定');target[key]=value
            with self.assertRaises(ValueError):m.replace_text(raw,'设置',[target])

    def test_ordinal_title_is_not_translated_or_used_as_string(self):
        raw=m.rebuild(fixture())
        with self.assertRaises(ValueError):m.replace_text(raw,'设置',[dict(ordinal=1,identifier=101,expected=dict(ordinal=22),target='X')])

    def test_duplicate_targets_nul_and_empty_title_are_rejected(self):
        raw=m.rebuild(fixture());target=dict(ordinal=0,identifier=100,expected='Original label',target='确定')
        with self.assertRaises(ValueError):m.replace_text(raw,'设置',[target,target])
        for title in ['',None,dict(ordinal=1),'a\0b']:
            with self.assertRaises(ValueError):m.replace_text(raw,title,[])
        target['target']='a\0b'
        with self.assertRaises(ValueError):m.replace_text(raw,'设置',[target])

    def test_corrupt_signature_control_order_and_count_are_rejected(self):
        raw=bytearray(m.rebuild(fixture()));raw[0]=2
        with self.assertRaises(ValueError):m.parse(bytes(raw))
        for change in ('count','order','id'):
            table=fixture()
            if change=='count':table['controls'].pop()
            if change=='order':table['controls'][0]['ordinal']=1
            if change=='id':table['controls'][0]['identifier']=99
            with self.assertRaises(ValueError):m.rebuild(table)


if __name__=='__main__':unittest.main()
