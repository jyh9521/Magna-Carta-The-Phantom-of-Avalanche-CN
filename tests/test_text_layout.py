import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import verify_text_layout as m


class TextLayoutTests(unittest.TestCase):
    def test_all_lead_semantics(self):
        for i in range(256):
            self.assertEqual(m.step(i,False),2 if 0xa4<=i<0xca else 1)
            self.assertEqual(m.step(i,True),2 if i>=0xa4 else 1)
        for i in [-1,256,True]:
            with self.assertRaises(ValueError):m.step(i,True)

    def test_mixed_private_prefix_not_split(self):
        data=b'A\xca\xa0$nB\xcb\x40'
        self.assertEqual(m.prefix_boundaries(data,True),[1,3,4,5,6,8])
        self.assertIn(2,m.prefix_boundaries(data,False))
        with self.assertRaises(ValueError):m.prefix_boundaries(b'\xca',True)
        with self.assertRaises(ValueError):m.prefix_boundaries(b'A\0',True)

    def test_runtime_function_context_matches_lock(self):
        lock=json.loads((ROOT/'assets/runtime/native-text-step.json').read_text('utf8'))
        cpp=(ROOT/'src/runtime/native_text_step.cpp').read_text('utf8')
        array=cpp.split('expected[] = {')[1].split('};')[0]
        code=bytes(int(x,16) for x in re.findall(r'0x([0-9a-f]+)',array))
        self.assertEqual(code.hex(),lock['function_original_hex'])
        self.assertEqual(lock['patch_rva']-lock['function_rva'],51)
        self.assertIn(lock['sha256'],(ROOT/'src/runtime/workspace_launcher.cpp').read_text('utf8'))

    def test_controlled_file_guards(self):
        actual=json.loads((ROOT/'assets/runtime/native-text-step.json').read_text('utf8'))
        body=bytes.fromhex(actual['function_original_hex']); data=b'fixture'+body+b'end'
        lock={**actual,'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),
              'function_file_offset':7,'patch_file_offset':7+51}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fixture.bin';path.write_bytes(data)
            self.assertEqual(m.verify(path,lock)['private_pairs'],4795)
            self.assertEqual(path.read_bytes(),data)
            bad={**lock,'sha256':'0'*64}
            with self.assertRaisesRegex(ValueError,'version'):m.verify(path,bad)
            bad={**lock,'function_original_hex':'00'*72}
            with self.assertRaisesRegex(ValueError,'context'):m.verify(path,bad)


if __name__=='__main__':unittest.main()
