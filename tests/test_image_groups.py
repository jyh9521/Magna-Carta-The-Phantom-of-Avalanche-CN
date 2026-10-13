import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_image_groups as m
from resource_image import parse
from test_resource_image import tga
from test_image_text_build import Outline


class ImageGroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir()
        self.raw=tga(width=40,height=40)
        self.rows=[]
        for i in range(2):
            name=f'{i}.BGR';(self.source/name).write_bytes(self.raw)
            self.rows.append(dict(resource=name,source_sha256=m.digest(self.raw),xy=[i*40,0]))

    def test_compose_and_split_are_exact_before_render(self):
        image,raw,tiles=m.compose(self.rows,self.source,[80,40])
        from PIL import Image
        combined=Image.frombytes('RGBA',(80,40),image.rgba())
        for name,tile,box in tiles:
            self.assertEqual(tile.replace_rgba(combined.crop(box).tobytes()).to_bytes(),raw[name])

    def test_locked_artwork_overlay_preserves_pixels_outside_mask(self):
        from PIL import Image
        overlay=Image.new('RGBA',(4,4));overlay.putpixel((1,1),(255,255,255,255))
        path=self.root/'overlay.png';overlay.save(path)
        row=dict(path='overlay.png',sha256=m.digest(path.read_bytes()),mask_xyxy=[10,10,20,20],text_lines=['owned'])
        image=parse(self.raw);changed,records=m.apply_artwork(image,dict(overlays=[row]),self.root,{})
        a,b=image.rgba(),changed.rgba()
        self.assertNotEqual(a,b)
        for y in range(40):
            for x in range(40):
                if not(10<=x<20 and 10<=y<20):
                    at=(y*40+x)*4;self.assertEqual(a[at:at+4],b[at:at+4])
        self.assertEqual(records[0]['text_lines'],['owned'])
        row['sha256']='0'*64
        with self.assertRaises(ValueError):m.apply_artwork(image,dict(overlays=[row]),self.root,{})

    def test_background_delta_exceeding_mask_is_rejected(self):
        from locale_package import delta
        image=parse(self.raw);raw=image.rgba();after=bytearray(raw);after[0]^=1
        path=self.root/'background.lpd';path.write_bytes(delta(raw,bytes(after)))
        row=dict(path=path.name,sha256=m.digest(path.read_bytes()),source_rgba_sha256=m.digest(raw),
                 target_rgba_sha256=m.digest(after),mask_xyxy=[10,10,20,20])
        with self.assertRaisesRegex(ValueError,'exceeds reviewed'):m.apply_artwork(image,dict(background_patch=row),self.root,{})

    def test_opaque_artwork_overlay_is_rejected(self):
        from PIL import Image
        path=self.root/'opaque.png';Image.new('RGBA',(4,4),(255,255,255,255)).save(path)
        row=dict(path=path.name,sha256=m.digest(path.read_bytes()),mask_xyxy=[10,10,20,20],text_lines=['owned'])
        with self.assertRaisesRegex(ValueError,'transparency'):m.apply_artwork(parse(self.raw),dict(overlays=[row]),self.root,{})

    def test_holes_overlaps_bad_dimensions_and_coordinates_are_rejected(self):
        for position in [[39,0],[41,0],[-1,0],[True,0]]:
            rows=copy.deepcopy(self.rows);rows[1]['xy']=position
            with self.assertRaises(ValueError):m.compose(rows,self.source,[80,40])
        with self.assertRaises(ValueError):m.compose(self.rows,self.source,[80,True])

    def test_source_hash_and_tile_identity_are_locked(self):
        for key,value in [('source_sha256','0'*64),('resource','../0.BGR')]:
            rows=copy.deepcopy(self.rows);rows[0][key]=value
            with self.assertRaises(ValueError):m.compose(rows,self.source,[80,40])
        with self.assertRaises(ValueError):m.compose([self.rows[0],self.rows[0]],self.source,[80,40])

    def test_phrase_crosses_boundary_without_changing_tile_headers(self):
        font=self.root/'font';font.write_bytes(b'outline');plans=self.root/'plans.json'
        data=dict(schema=1,groups=[dict(id='fixture',dimensions=[80,40],tiles=self.rows,
            layout_evidence='controlled adjacent tiles',plans=[dict(target='Boundary',mask_xyxy=[5,5,75,35],
            background_anchor=[0,0],font_size=12,minimum_font_size=10,stroke_width=0,source_text_evidence='fixture')])])
        plans.write_text(json.dumps(data),encoding='utf8');output=self.root/'output'
        with patch('fontTools.ttLib.TTFont',Outline),patch('PIL.ImageFont.truetype',return_value=ImageFont.load_default()):
            report=m.build(self.source,plans,font,m.digest(font.read_bytes()),output)
        for row in self.rows:
            before=parse(self.raw);after=parse((output/row['resource']).read_bytes())
            self.assertEqual(before.header,after.header);self.assertEqual(before.wrapper,after.wrapper)
            self.assertEqual(before.suffix,after.suffix)
        self.assertFalse(report['game_started']);self.assertFalse(report['groups'][0]['runtime_placement_verified'])


if __name__=='__main__':unittest.main()
