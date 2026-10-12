import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import build_text_resources as m
from extract_text_catalog import text_row
from native_text_codec import plan,encode
from resource_fpb import parse,rebuild
from resource_font import parse as parse_font
from translation_data import source_digest
from test_glyph_probe import inputs


class TextResourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'game';(self.source/'Fpb').mkdir(parents=True)
        self.original=rebuild([(7,'앞'.encode('cp949'))]);self.resource='Fpb/fixture.fpb'
        (self.source/self.resource).write_bytes(self.original)
        self.row=text_row(self.resource,0,7,'text',20,'앞'.encode('cp949'))
        self.targets=[dict(id=self.row['id'],source_sha256=source_digest(self.row),target='前文',state='translated')]
        self.catalog=[self.row];self.coverage=[dict(path=self.resource,sha256=m.digest(self.original),size=len(self.original))]
        self.package=self.root/'font';self.package.mkdir();(self.source/'Font').mkdir()
        stock=inputs();fonts=[parse_font(stock[f'Chi{i}.dat']) for i in (0,1)]
        self.mapping=plan('前文',fonts);deltas=[];originals=[];modified=[]
        for i,font in enumerate(fonts):
            raw=stock[f'Chi{i}.dat'];(self.source/'Font'/f'Chi{i}.dat').write_bytes(raw)
            new=font
            for c,item in self.mapping.items():
                bitmap=b'\x03'*font.glyph_bytes
                deltas.append(dict(font_set=i,index=item['index'],bitmap_hex=bitmap.hex(),
                                   original_glyph_sha256=m.digest(font.glyph(item['index']))))
                new=new.replace_glyph(item['index'],bitmap)
            result=new.to_bytes();(self.package/f'Chi{i}.dat').write_bytes(result)
            originals.append(m.digest(raw));modified.append(m.digest(result))
        self.font_state=dict(mapping=self.mapping,deltas=deltas,native_original_sha256=originals,native_modified_sha256=modified)
        self.output=self.root/'output'

    def build(self,partial=False):
        files={self.root/'catalog.json':self.catalog,self.root/'coverage.json':self.coverage,
               self.root/'targets.json':self.targets,self.package/'overlay.json':self.font_state}
        for p,data in files.items():p.write_text(json.dumps(data),encoding='utf8')
        return m.build(self.source,self.root/'catalog.json',self.root/'coverage.json',[self.root/'targets.json'],
                       self.package,self.output,allow_partial=partial)

    def test_native_fpb_rebuild_updates_offsets_without_changing_ids(self):
        original=rebuild([(7,b'A'),(3,b'B')])
        rows=[text_row(self.resource,i,tag,'text',20,raw) for i,(tag,raw) in enumerate(parse(original))]
        targets=[dict(id=r['id'],source_sha256=source_digest(r),target='前文',state='translated') for r in rows]
        modified=m.rebuild_fpb(original,self.resource,rows,targets,self.mapping)
        self.assertEqual(parse(modified),[(7,encode('前文',self.mapping)),(3,encode('前文',self.mapping))])
        self.assertNotEqual(original,modified)

    def test_candidate_build_preserves_source_and_never_claims_whole_game(self):
        state=self.build()
        self.assertEqual((self.source/self.resource).read_bytes(),self.original)
        self.assertFalse(state['all_game_text_complete']);self.assertFalse(state['deployed'])
        self.assertEqual(parse((self.output/self.resource).read_bytes())[0][0],7)
        self.assertTrue(state['requires_native_text_step'])

    def test_incomplete_catalog_blocks_default_and_partial_is_explicit(self):
        extra={**self.row,'id':'Fpb/other.fpb:text:0:7','resource':'Fpb/other.fpb'}
        self.catalog.append(extra)
        with self.assertRaisesRegex(ValueError,'validation failed'):self.build()
        self.assertFalse(self.output.exists())
        state=self.build(partial=True);self.assertFalse(state['catalog_validation']['complete'])

    def test_source_file_hash_and_catalog_bytes_are_checked(self):
        self.coverage[0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'coverage digest'):self.build()
        self.coverage[0]['sha256']=m.digest(self.original);self.row['identifier']=8
        with self.assertRaisesRegex(ValueError,'identifier'):self.build()
        self.assertFalse(self.output.exists())

    def test_missing_record_inside_resource_is_refused(self):
        self.targets=[]
        with self.assertRaisesRegex(ValueError,'incomplete'):m.rebuild_fpb(self.original,self.resource,self.catalog,self.targets,self.mapping)

    def test_font_changes_outside_declared_delta_are_refused(self):
        path=self.package/'Chi0.dat';data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
        self.font_state['native_modified_sha256'][0]=m.digest(data)
        with self.assertRaisesRegex(ValueError,'outside declared'):self.build()
        self.assertFalse(self.output.exists())

    def test_original_context_and_preserved_row(self):
        self.targets=[dict(id=self.row['id'],source_sha256=source_digest(self.row),target=None,state='preserved',
                           preservation_evidence='controlled internal-field classification')]
        self.build();self.assertEqual((self.output/self.resource).read_bytes(),self.original)

    def test_output_reuse_and_source_drift_are_refused(self):
        self.build()
        with self.assertRaisesRegex(ValueError,'new separate'):self.build()
        self.output=self.root/'second-output'
        checked=m.checked_fonts
        def change(*args):
            result=checked(*args);(self.source/self.resource).write_bytes(b'changed');return result
        with patch.object(m,'checked_fonts',side_effect=change):
            with self.assertRaisesRegex(ValueError,'input changed'):self.build()
        self.assertFalse(self.output.exists())

    def test_duplicate_ordinals_and_unknown_format_are_refused(self):
        wrong=[self.row,self.row]
        with self.assertRaisesRegex(ValueError,'count'):m.rebuild_fpb(self.original,self.resource,wrong,self.targets,self.mapping)
        self.row['resource']='Abi/fixture.abi';self.row['id']='Abi/fixture.abi:text:0:7';self.targets[0]['id']=self.row['id']
        with self.assertRaisesRegex(ValueError,'format not supported'):self.build()


if __name__=='__main__':unittest.main()
