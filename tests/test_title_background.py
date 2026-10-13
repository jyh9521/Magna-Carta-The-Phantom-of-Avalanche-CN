from pathlib import Path
import sys
import unittest
import tempfile
import json

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_title_background as background
import refresh_title_background as refresh
from resource_image import ResourceImage, TGA_FOOTER, parse
import struct


class TitleBackgroundTests(unittest.TestCase):
    def test_artwork_drift_is_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'source.png').write_bytes(b'owned drift fixture')
            (root/'logo.png').write_bytes(b'owned logo fixture')
            plan={'source':'source.png','wordmark':'logo.png','source_sha256':'0','wordmark_sha256':'0'}
            with self.assertRaisesRegex(ValueError,'Artwork input drift'):
                background.master(root,plan)

    def test_4by3_crop_is_centered(self):
        image=Image.new('RGBA',(3840,2160),(1,2,3,255))
        image.paste((255,0,0,255),(480,0,481,2160))
        image.paste((0,255,0,255),(3359,0,3360,2160))
        cropped=background.centered_view(image,2880,2160)
        self.assertEqual(cropped.size,(2880,2160))
        self.assertEqual(cropped.getpixel((0,0)),(255,0,0,255))
        self.assertEqual(cropped.getpixel((2879,0)),(0,255,0,255))

    def test_low_resolution_keeps_aspect(self):
        image=Image.new('RGBA',(3840,2160),(1,2,3,255))
        for size in [(1920,1080),(1280,720),(640,480),(800,600)]:
            self.assertEqual(background.centered_view(image,*size).size,size)

    def tile(self):
        header=bytearray(18);header[2]=2;header[16:18]=bytes([32,8])
        struct.pack_into('<HH',header,12,256,256)
        return ResourceImage(b'\0'*24,bytes(header),b'\0'*(256*256*4),TGA_FOOTER,'TGA',256,256,1024).to_bytes()

    def test_padded_edge_stays_transparent(self):
        image=Image.new('RGBA',(16,16),(1,2,3,255))
        packed=parse(background.pack(self.tile(),image,0,0,32))
        self.assertEqual((packed.width,packed.height),(32,32))
        result=Image.frombytes('RGBA',(32,32),packed.rgba())
        self.assertEqual(result.getpixel((15,15)),(1,2,3,255))
        self.assertEqual(result.getpixel((16,16)),(0,0,0,0))

    def test_overlapping_tiles_use_same_master_pixels(self):
        image=Image.new('RGBA',(48,16),(1,2,3,255))
        image.paste((9,8,7,255),(16,0,32,16))
        left=parse(background.pack(self.tile(),image,0,0,32))
        right=parse(background.pack(self.tile(),image,16,0,32))
        a=Image.frombytes('RGBA',(32,32),left.rgba())
        b=Image.frombytes('RGBA',(32,32),right.rgba())
        self.assertEqual(a.crop((16,0,32,16)).tobytes(),b.crop((0,0,16,16)).tobytes())

    def test_background_opt_in_preserves_accepted_path(self):
        source=(ROOT/'src/runtime/title_layout.cpp').read_text('utf8')
        self.assertIn('MC_TITLE_BACKGROUND4K',source)
        self.assertIn('if(!hdBackground)',source)
        self.assertIn('position[0]+=',source)
        self.assertIn('size[0]=scale;size[1]=scale',source)


class BackgroundRefreshTests(unittest.TestCase):
    def pair(self,folder):
        a=Path(folder)/'a';b=Path(folder)/'b'
        for root,tag in [(a,'old'),(b,'new')]:
            records={}
            for name in sorted(refresh.TILES):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((tag+name).encode())
                records[name]={'before':'original-version','after':background.sha(p)}
            for name in refresh.EXTRAS:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((tag+name).encode())
            (root/refresh.MANIFEST).write_text(json.dumps({'active':True,'tiles':records,'master_sha256':background.sha(root/refresh.EXTRAS[0])}),encoding='utf8')
        return a,b

    def test_refresh_backs_up_exact_previous_files(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=self.pair(folder)
            names=sorted(refresh.TILES)+refresh.EXTRAS+[refresh.MANIFEST]
            before={name:(a/name).read_bytes() for name in names}
            backup=refresh._refresh(a,b)
            for name in names:
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
                self.assertEqual((backup/'files'/name).read_bytes(),before[name])
            self.assertTrue((a/'Restore-previous-background.cmd').is_file())

    def test_drift_rejects_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=self.pair(folder);name=sorted(refresh.TILES)[0]
            (a/name).write_bytes(b'owned drift')
            with self.assertRaisesRegex(ValueError,'Title tile drift'):
                refresh._refresh(a,b)
            self.assertEqual((a/name).read_bytes(),b'owned drift')
            self.assertFalse(list((a/'.advanced-runtime').glob('previous-title-*')))

    def test_names_are_source_backed_and_exact(self):
        plan=json.loads((ROOT/'locales/zh-CN/title-background-plan.json').read_text('utf8'))
        names=plan['background_names']
        self.assertEqual(names['english'],'MagnaCarta: The Phantom of Avalanche')
        self.assertEqual(names['korean_art_lines'],['마그나카르타','눈사태의 망령'])
        self.assertGreaterEqual(len(names['sources']),2)


if __name__=='__main__':
    unittest.main()
