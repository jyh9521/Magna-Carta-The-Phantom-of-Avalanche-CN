from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_font_overlay as m
from test_glyph_probe import inputs
from resource_font import parse


class Notice:
    nameID = 13
    def toUnicode(self): return 'SIL Open Font License'


class FakeOutline:
    def __init__(self, path): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def __contains__(self, key): return False
    def __getitem__(self, key):
        class Name: names = [Notice()]
        return Name()
    def getBestCmap(self): return {ord(char): char for char in '中文测试汉龙'}


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source=self.root/'native';self.source.mkdir()
        self.data=inputs()
        for n in ['Chi0.dat','Chi1.dat']:(self.source/n).write_bytes(self.data[n])
        self.outline=self.root/'outline.ttf';self.outline.write_bytes(b'explicit-outline-fixture')
        self.output=self.root/'output'

    def build(self, text='中文'):
        with patch('fontTools.ttLib.TTFont', FakeOutline), patch.object(m,'rasterize',side_effect=lambda c,p,h,w,*rest:b'\x03'*(h*w)):
            return m.build(self.source,self.outline,m.sha(self.outline.read_bytes()),text,self.output)

    def test_controlled_build_changes_only_mapped_glyphs(self):
        state=self.build()
        for i in [0,1]:
            old=self.data[f'Chi{i}.dat'];new=(self.output/f'Chi{i}.dat').read_bytes();f=parse(old)
            allowed={j for item in state['mapping'].values() for j in range(100+item['index']*f.glyph_bytes,100+(item['index']+1)*f.glyph_bytes)}
            self.assertEqual(len(old),len(new));self.assertTrue(all(j in allowed for j,(a,b) in enumerate(zip(old,new)) if a!=b))
            self.assertEqual((self.source/f'Chi{i}.dat').read_bytes(),old)
        self.assertFalse(state['in_game_verified'])

    def test_source_font_hash_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            m.build(self.source,self.outline,'0'*64,'中文',self.output)
        self.assertFalse(self.output.exists())

    def test_source_glyph_coverage_refused(self):
        with self.assertRaisesRegex(ValueError,'lacks codepoints'):self.build('不存在')
        self.assertFalse(self.output.exists())

    def test_output_reuse_refused(self):
        self.build()
        with self.assertRaisesRegex(ValueError,'new separate'):self.build()


if __name__=='__main__':unittest.main()
