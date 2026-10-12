import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import collect_translation_corpus as m
from extract_text_catalog import text_row


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.catalog=self.root/'catalog.json'
        self.sources=[text_row('Fpb/fixture.fpb',i,i,'text',20,b'abc') for i in (0,1)]
        self.catalog.write_text(json.dumps(self.sources),encoding='utf8')
        self.paths=[]
        for i,row in enumerate(self.sources):
            p=self.root/f'{i}.json';p.write_text(json.dumps([dict(id=row['id'],source_sha256=hashlib.sha256(b'abc').hexdigest(),target='文本',state='translated')]),encoding='utf8');self.paths.append(p)

    def test_sorted_deterministic(self):
        a=m.collect(self.catalog,self.paths[::-1],self.root/'a')
        b=m.collect(self.catalog,self.paths,self.root/'b')
        self.assertEqual((self.root/'a/corpus.json').read_bytes(),(self.root/'b/corpus.json').read_bytes())
        self.assertEqual(a['corpus_sha256'],b['corpus_sha256']);self.assertTrue(a['catalog_complete'])

    def test_missing_rejected_and_partial_explicit(self):
        with self.assertRaises(ValueError):m.collect(self.catalog,self.paths[:1],self.root/'a')
        self.assertFalse((self.root/'a').exists())
        self.assertFalse(m.collect(self.catalog,self.paths[:1],self.root/'b',allow_partial=True)['catalog_complete'])

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):m.collect(self.catalog,[self.paths[0]]*2,self.root/'a')

    def test_stale_rejected(self):
        data=json.loads(self.paths[0].read_text());data[0]['source_sha256']='0'*64
        self.paths[0].write_text(json.dumps(data))
        with self.assertRaises(ValueError):m.collect(self.catalog,self.paths,self.root/'a')

    def test_preserved_excluded(self):
        data=json.loads(self.paths[1].read_text());data[0].update(state='preserved',target=None,preservation_evidence='owned fixture internal identifier')
        self.paths[1].write_text(json.dumps(data))
        result=m.collect(self.catalog,self.paths,self.root/'a')
        self.assertEqual(result['target_rows'],1);self.assertEqual(result['preserved_fields_excluded'],1)

    def test_existing_output_and_input_drift_rejected(self):
        with self.assertRaises(ValueError):m.collect(self.catalog,self.paths,self.root)
        actual=m.validate
        def change(*args,**kwargs):
            result=actual(*args,**kwargs);self.paths[0].write_text('[]');return result
        with patch.object(m,'validate',side_effect=change):
            with self.assertRaises(ValueError):m.collect(self.catalog,self.paths,self.root/'a')
        self.assertFalse((self.root/'a').exists())


if __name__=='__main__':unittest.main()
