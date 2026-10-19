import copy
import hashlib
import struct
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import audit_scene_crash_evidence as t
from test_inspect_minidump import fixture,module

class MemoryInfoTests(unittest.TestCase):
    def data(self):
        d=fixture();struct.pack_into('<I',d,8,5);struct.pack_into('<III',d,32+12*4,16,64,0x400)
        struct.pack_into('<IIQ',d,0x400,16,48,1)
        struct.pack_into('<QQI4xQIII4x',d,0x410,0x10000,0x10000,4,0x1000,0x2000,0,0x20000)
        return d
    def test_region_is_snapshot_only_and_reserved_not_missing(self):
        r=module.Dump(self.data()).memory_region(0x10020)
        self.assertEqual(r['state'],'0x2000');self.assertEqual(r['timing'],'snapshot_only')
    def test_missing_stream_is_unknown(self):self.assertIsNone(module.Dump(fixture()).memory_region(0x10000))
    def test_uncovered_address_is_unknown(self):self.assertIsNone(module.Dump(self.data()).memory_region(0x11000))
    def test_truncated_descriptor_stride_rejected(self):
        d=self.data();struct.pack_into('<I',d,0x404,47)
        with self.assertRaises(ValueError):module.Dump(d).memory_region(0x10000)
    def test_huge_count_rejected(self):
        d=self.data();struct.pack_into('<Q',d,0x408,2**64-1)
        with self.assertRaises(ValueError):module.Dump(d).memory_region(0x10000)
    def test_zero_region_rejected(self):
        d=self.data();struct.pack_into('<Q',d,0x410+24,0)
        with self.assertRaises(ValueError):module.Dump(d).memory_region(0x10000)
    def test_address_overflow_rejected(self):
        with self.assertRaises(ValueError):module.Dump(self.data()).memory_region(2**64)
    def test_ambiguous_regions_rejected(self):
        d=self.data();struct.pack_into('<I',d,32+12*4+4,112);struct.pack_into('<Q',d,0x408,2);d[0x440:0x470]=d[0x410:0x440]
        with self.assertRaises(ValueError):module.Dump(d).memory_region(0x10020)

class FakeDump:
    def __init__(self,_):
        self.modules=[dict(name='MCAlpha.dll',base=0x52000000,size=0x10b000,timestamp=0x3ed73966)];self.streams={};self.changed=False
    def read(self,a,n):
        if a==0x5201e940:return t.FAULT_PREFIX
        if a==0x520f220c:return struct.pack('<I',0xbaef30)
        if a==0xbaef30:return struct.pack('<III',0x520bd604,2,0)
        raise ValueError('Unexpected read')
    def inspect(self):
        c=dict(fault_location=dict(module='MCAlpha.dll',rva='0x1e94f'),registers=dict(ecx='0xbaf024'),exception='0xc0000005',access='read',access_address='0xbaf024',frame_chain=[dict(return_site=dict(module='MCAlpha.dll',rva=hex(v))) for v in t.STARTUP_CHAIN])
        return dict(earlier_contexts=[c])
    def memory_region(self,_):return dict(state='0x2000',timing='snapshot_only')

class AttributionTests(unittest.TestCase):
    def run_audit(self,factory=FakeDump):
        b=b'owned image'
        with patch.object(t,'SOURCE_SHA',hashlib.sha256(b).hexdigest()),patch.object(t,'Dump',factory):return t.audit(b'owned dump',b)
    def test_exact_startup_chain_is_not_scene_acceptance(self):
        r=self.run_audit();self.assertTrue(r['root_parent_bounds_fault_confirmed']);self.assertFalse(r['scene_transition_verified']);self.assertFalse(r['scene_root_cause_confirmed']);self.assertFalse(r['game_started_this_analysis'])
    def test_no_context_is_not_promoted_to_scene_proof(self):
        class Empty(FakeDump):
            def inspect(self):return dict(earlier_contexts=[])
        r=self.run_audit(Empty);self.assertEqual(r['classification'],'unclassified');self.assertFalse(r['scene_transition_verified'])
    def test_unrelated_stack_not_classified_as_startup(self):
        class Other(FakeDump):
            def inspect(self):
                d=super().inspect();d['earlier_contexts'][0]['frame_chain'][4]['return_site']['rva']='0x63146';return d
        self.assertEqual(self.run_audit(Other)['classification'],'unclassified')
    def test_snapshot_instruction_mismatch_rejected(self):
        class Other(FakeDump):
            def read(self,a,n):return b'bad' if a==0x5201e940 else super().read(a,n)
        with self.assertRaises(ValueError):self.run_audit(Other)
    def test_engine_identity_mismatch_rejected(self):
        class Other(FakeDump):
            def __init__(self,x):super().__init__(x);self.modules[0]['timestamp']=0
        with self.assertRaises(ValueError):self.run_audit(Other)
    def test_unknown_engine_rejected(self):
        with patch.object(t,'Dump') as d:
            with self.assertRaises(ValueError):t.audit(b'owned dump',b'owned unsupported engine')
            d.assert_not_called()

if __name__=='__main__':unittest.main()
