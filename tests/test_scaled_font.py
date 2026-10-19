import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from build_scaled_font_coverage import build, cache_bytes, read_inputs, rollback, scaled_tiles

ROOT=Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_cache_layout_and_rejected_contracts(self):
        raw=cache_bytes(14,4,[0xca40],bytes(56*56))
        self.assertEqual(struct.unpack_from('<4sIIIIH',raw),(b'SGC1',1,14,4,1,0xca40))
        self.assertEqual(len(raw),22+56*56)
        for args in [(16,4,[1],bytes(64*64)),(14,0,[1],b''),(14,5,[1],bytes(70*70)),(14,1,[1,1],bytes(392)),(14,1,[1],bytes(195))]:
            with self.assertRaises(ValueError):cache_bytes(*args)

    def test_native_chunk_boundaries_and_normalized_uv(self):
        from fractions import Fraction
        for width in [1,255,256,257,512,513,8192]:
            for scale in [1,2,3,4]:
                tiles=scaled_tiles(width,22,scale)
                self.assertEqual(sum(x['logical_width'] for x in tiles),width)
                self.assertEqual(sum(x['physical_width'] for x in tiles),width*scale)
                for t in tiles:
                    self.assertLessEqual(t['logical_width'],256)
                    self.assertEqual(Fraction(t['logical_x'],width),Fraction(t['physical_x'],width*scale))
                    self.assertEqual(Fraction(t['logical_width'],width),Fraction(t['physical_width'],width*scale))
        for args in [(0,22,4),(8193,22,4),(256,65,4),(256,22,5),(True,22,4)]:
            with self.assertRaises(ValueError):scaled_tiles(*args)

    def test_pair_and_plane_identity(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            d=Path(d);h=d/'native.h';m=d/'mapping.h'
            h.write_text('const unsigned short coveragePairs[] = {0xca40};\n'+''.join('const unsigned char coveragePlane'+str(i)+'[] = {'+','.join(['0']*(n*n))+'};\n' for i,n in enumerate((14,22))))
            m.write_text('{0xca40,L"\\u4e2d"},\n')
            pairs,mapping,planes,_,_=read_inputs(h,m)
            self.assertEqual(pairs,[0xca40]);self.assertEqual(mapping[0xca40],'中');self.assertEqual([len(p) for p in planes],[196,484])
            m.write_text('{0xca41,L"\\u4e2d"},\n')
            with self.assertRaises(ValueError):read_inputs(h,m)

    def test_unknown_outline_rejected_before_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            d=Path(d)
            for n in ['font','native','mapping','sample']:(d/n).write_bytes(b'owned')
            (d/'lock').write_text(json.dumps(dict(sha256='0'*64)))
            with self.assertRaisesRegex(ValueError,'Outline hash'):
                build(d/'font',d/'lock',d/'native',d/'mapping',d/'sample',d/'output')
            self.assertFalse((d/'output').exists())

    def test_owned_copy_rollback_and_drift_rejection(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            d=Path(d);cache=d/'cache';cache.mkdir();target=d/'active.sgc'
            low=cache_bytes(22,1,[0xca40],bytes(484));high=cache_bytes(22,4,[0xca40],bytes(7744))
            (cache/'baseline-22.sgc').write_bytes(low);target.write_bytes(high)
            manifest=cache/'manifest.json';sha=lambda b:hashlib.sha256(b).hexdigest()
            manifest.write_text(json.dumps(dict(schema=1,files={'baseline-22.sgc':sha(low),'candidate-22.sgc':sha(high)})))
            rollback(manifest,target,22);self.assertEqual(target.read_bytes(),low)
            with self.assertRaises(ValueError):rollback(manifest,target,22)
            target.write_bytes(high);(cache/'baseline-22.sgc').write_bytes(b'drift')
            with self.assertRaises(ValueError):rollback(manifest,target,22)
            self.assertEqual(target.read_bytes(),high)


class LocalNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache=ROOT/'build/scaled-font-evidence/cache'
        cls.exe=ROOT/'build/native/Release/scaled_font_fixture.exe'
        if not cls.exe.exists() or not (cls.cache/'manifest.json').exists():raise unittest.SkipTest('Build owned scaled-font fixture and local digest-locked cache')

    def test_native_pixels_metrics_and_three_modes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            for h in (14,22):
                for mode in ['baseline','modified','rollback']:
                    p=subprocess.run([str(self.exe),mode,str(self.cache/f'baseline-{h}.sgc'),str(self.cache/f'candidate-{h}.sgc'),str(self.cache/'line-0.seq'),str(Path(d)/f'{mode}{h}.bmp')],capture_output=True,text=True,timeout=20)
                    self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                    self.assertIn('native_baseline=exact',p.stdout);self.assertIn('runtime_installed=false',p.stdout)
                    self.assertIn('physical_cell='+str(h*(4 if mode=='modified' else 1)),p.stdout)
                self.assertEqual((Path(d)/f'baseline{h}.bmp').read_bytes(),(Path(d)/f'rollback{h}.bmp').read_bytes())

    def test_modified_request_on_original_cells_is_red(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            low=str(self.cache/'baseline-22.sgc')
            p=subprocess.run([str(self.exe),'modified',low,low,str(self.cache/'line-0.seq'),str(Path(d)/'out.bmp')],capture_output=True,text=True,timeout=20)
            self.assertEqual(p.returncode,5);self.assertIn('candidate must contain rerasterized',p.stdout)

    def test_parser_rejects_malformed_cache_before_rendering(self):
        good=cache_bytes(14,1,[0xca40,0xca41],bytes(392))
        variants=[b'',b'WRNG'+good[4:],good+b'0',good[:-1]]
        for off,val in [(4,2),(8,16),(12,0),(12,5),(16,0),(16,4097)]:
            b=bytearray(good);struct.pack_into('<I',b,off,val);variants.append(bytes(b))
        b=bytearray(good);b[22:24]=b[20:22];variants.append(bytes(b))
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            d=Path(d)
            for raw in variants:
                (d/'bad.sgc').write_bytes(raw)
                p=subprocess.run([str(self.exe),'modified',str(d/'bad.sgc'),str(self.cache/'candidate-14.sgc'),str(self.cache/'line-0.seq'),str(d/'out.bmp')],capture_output=True,text=True,timeout=20)
                self.assertEqual(p.returncode,2,p.stdout+p.stderr);self.assertIn('REJECT',p.stdout)
                self.assertFalse((d/'out.bmp').exists())

    def test_true_detail_is_not_bitmap_filter_and_chunk_reassembly_is_exact(self):
        from PIL import Image
        r=json.loads((self.cache/'manifest.json').read_bytes());self.assertTrue(r['baseline_matches_active_coverage'])
        low=(self.cache/'baseline-22.sgc').read_bytes();high=(self.cache/'candidate-22.sgc').read_bytes()
        count=struct.unpack_from('<I',low,16)[0];pairs=struct.unpack_from('<'+'H'*count,low,20)
        _,mapping,_,_,_=read_inputs(ROOT/'runtime/build-inputs/native_font_data.h',ROOT/'runtime/build-inputs/system_message_rules.h')
        pair=next(k for k,v in mapping.items() if v=='其');i=pairs.index(pair);start=20+2*count
        a=Image.frombytes('L',(22,22),low[start+i*484:start+(i+1)*484]);b=high[start+i*7744:start+(i+1)*7744]
        for method in [Image.Resampling.NEAREST,Image.Resampling.BILINEAR]:self.assertNotEqual(a.resize((88,88),method).tobytes(),b)
        preview=ROOT/'build/scaled-font-evidence/preview-verified/modified-22-0.bmp'
        if not preview.exists():return
        with Image.open(preview) as im:
            im=im.convert('RGB');parts=scaled_tiles(im.width//4,22,4);rebuilt=Image.new('RGB',im.size)
            for t in parts:
                x=t['physical_x'];w=t['physical_width'];rebuilt.paste(im.crop((x,0,x+w,im.height)),(x,0))
            self.assertEqual(rebuilt.tobytes(),im.tobytes())


if __name__=='__main__':unittest.main()
