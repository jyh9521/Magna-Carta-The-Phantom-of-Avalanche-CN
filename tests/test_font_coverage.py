import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_font_coverage import coverage,validate_module,raster_layout


class Face:
    def __init__(self,size):self.size=size
    def getbbox(self,character,anchor=None):
        top=3 if character=='Y' else 0
        return (0,top-self.size if anchor=='ls' else top,self.size,0 if anchor=='ls' else self.size)


class Drawer:
    def __init__(self,image):self.image=image
    calls=[]
    def text(self,origin,character,font,fill,anchor=None):
        self.calls.append((character,origin,font.size,anchor));b=font.getbbox(character,anchor)
        for y in range(b[3]-b[1]):
            for x in range(font.size):
                self.image.putpixel((origin[0]+x,origin[1]+b[1]+y),128)


class CoverageTests(unittest.TestCase):
    def test_uniform_face_and_baseline_despite_different_ink_heights(self):
        with patch('PIL.ImageFont.truetype',side_effect=lambda path,size:Face(size)),patch('PIL.ImageDraw.Draw',Drawer):
            cache={};layout=raster_layout('controlled-outline',14,['X','Y'],cache);Drawer.calls=[]
            for char in ['X','Y']:coverage(char,'controlled-outline',14,cache=cache,layout=layout)
            self.assertEqual(Drawer.calls[0][1][1],Drawer.calls[1][1][1])
            self.assertEqual(Drawer.calls[0][2],Drawer.calls[1][2])
            self.assertEqual(Drawer.calls[0][3],'ls')
    def test_module_contract_rejects_unknown_code_and_entries(self):
        from types import SimpleNamespace
        from hashlib import sha256
        raw=bytes(range(32))*3
        section=SimpleNamespace(Name=b'.text\0',get_data=lambda:b'controlled code')
        pe=SimpleNamespace(FILE_HEADER=SimpleNamespace(Machine=332),OPTIONAL_HEADER=SimpleNamespace(Magic=267,SizeOfImage=4096),sections=[section],get_offset_from_rva=lambda r:r)
        c=dict(schema=1,machine=332,optional_magic=267,image_size=4096,text_sha256=sha256(b'controlled code').hexdigest(),entries=[dict(name=k,rva=i*32,expected_hex=raw[i*32:(i+1)*32].hex()) for i,k in enumerate(['GLYPH','MEASURE','TEXT'])])
        with patch('pefile.PE',return_value=pe):
            self.assertEqual(set(validate_module(raw,c)),{'GLYPH','MEASURE','TEXT'})
            with self.assertRaises(ValueError):validate_module(bytes([255])+raw[1:],c)
            with self.assertRaises(ValueError):validate_module(raw,dict(c,text_sha256='0'*64))

    def test_foreground_y_offset_keeps_last_source_row_empty(self):
        with patch('PIL.ImageFont.truetype',side_effect=lambda path,size:Face(size)),patch('PIL.ImageDraw.Draw',Drawer):
            for h in [14,22]:
                raw=coverage('X','controlled-outline',h)
                self.assertEqual(len(raw),h*h)
                self.assertEqual(raw[-h:],bytes(h))
                self.assertIn(128,raw)
