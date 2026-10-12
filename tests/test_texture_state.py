import sys
from pathlib import Path
import struct
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyze_texture_state import inspect_binding


class FakeDump:
    modules = [{'name': 'd3dim700.dll', 'timestamp': 0xb546c162, 'size': 0x67000}]
    def __init__(self):
        self.words = {0x2000-4: 0x3000, 0x2000+12: 6, 0x3000+0x2c: 0x4000,
                      0x3000+0x108ef0: 0, 0x3000+0x100ea0+24: 0x5000,
                      0x4000+0x2938: 0x6000, 0x5000: 0x7000}
    def read(self, address, size):
        return b''.join(struct.pack('<I', self.words.get(a, 0)) for a in range(address, address+size, 4))
    def location(self, address): return {'module': 'fixture.dll', 'rva': hex(address)}


class TextureStateTests(unittest.TestCase):
    def setUp(self):
        self.dump = FakeDump()
        self.context = {'fault_location': {'module': 'd3dim700.dll', 'rva': '0x71b8'},
                        'frame_chain': [{'return_site': {'module': 'AsrD3DDrv.dll', 'rva': '0x7bb6'}},
                                        {'frame_pointer': '0x2000'}]}
    def test_binding_fields(self):
        result = inspect_binding(self.dump, self.context)
        self.assertEqual(result['replacement_id'], 6)
        self.assertEqual(result['old_native_binding'], '0x6000')
        self.assertEqual(result['release_history'], 'not established from snapshot alone')
    def test_layout_rejected(self):
        self.context['fault_location']['rva'] = '0x9999'
        with self.assertRaises(ValueError): inspect_binding(self.dump, self.context)
    def test_index_rejected(self):
        self.dump.words[0x3000+0x108ef0] = 8
        with self.assertRaises(ValueError): inspect_binding(self.dump, self.context)
