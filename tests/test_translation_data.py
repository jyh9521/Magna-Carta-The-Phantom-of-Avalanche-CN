import copy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from extract_text_catalog import text_row
from translation_data import validate, source_digest
from native_text_codec import plan


class TranslationDataTests(unittest.TestCase):
    def setUp(self):
        self.row=text_row('Fpb/fixture.fpb',0,7,'text',20,'앞$d05$n %s'.encode('cp949'))
        self.target=dict(id=self.row['id'],source_sha256=source_digest(self.row),target='前$d05$n %s',state='translated')

    def test_valid_source_bound_controls(self):
        result=validate([self.row],[self.target],require_complete=True)
        self.assertTrue(result['complete']);self.assertFalse(result['game_started'])

    def test_stale_source_and_unknown_duplicate_ids_refused(self):
        bad=copy.deepcopy(self.target);bad['source_sha256']='0'*64
        self.assertEqual(validate([self.row],[bad])['errors'][0]['kind'],'stale_source')
        with self.assertRaises(ValueError):validate([self.row],[self.target,self.target])
        bad['id']='unknown'
        with self.assertRaises(ValueError):validate([self.row],[bad])

    def test_catalog_decoded_text_and_record_types_are_checked(self):
        row={**self.row,'source':'different source'}
        with self.assertRaisesRegex(ValueError,'original bytes'):validate([row],[self.target])
        for target in ['invalid',dict(id=[]),dict(id=7)]:
            with self.assertRaisesRegex(ValueError,'string ID'):validate([self.row],[target])

    def test_control_parameters_and_order_are_preserved(self):
        for text in ['前$d06$n %s','前$n$d05 %s','前$d05 %s','前$d05$n %d']:
            bad={**self.target,'target':text}
            self.assertEqual(validate([self.row],[bad])['errors'][0]['kind'],'protected_tokens_changed')

    def test_missing_rows_block_complete_build(self):
        result=validate([self.row],[],require_complete=True)
        self.assertFalse(result['complete']);self.assertEqual(result['errors'][0]['kind'],'incomplete_catalog')
        self.assertFalse(validate([self.row],[])['complete'])

    def test_empty_and_embedded_terminator_refused(self):
        for text in ['', '前\0$d05$n %s']:
            self.assertEqual(validate([self.row],[{**self.target,'target':text}])['errors'][0]['kind'],'unexpected_empty_or_terminator')

    def test_preserved_internal_field_requires_evidence(self):
        row={**self.target,'target':None,'state':'preserved'}
        self.assertTrue(validate([self.row],[row])['errors'])
        row['preservation_evidence']='controlled identifier consumer'
        result=validate([self.row],[row],require_complete=True)
        self.assertTrue(result['complete']);self.assertEqual(result['preserved_fields'],1)

    def test_private_glyph_coverage_and_term_conflicts(self):
        class Font:count=13151
        mapping=plan('前',[Font()])
        self.assertFalse(validate([self.row],[self.target],mapping=mapping)['errors'])
        self.assertTrue(validate([self.row],[self.target],mapping={})['errors'])
        terms=dict(schema=1,terms=[dict(id='one',source='앞',target='前面',meaning='fixture',status='待复核',
                translation_state='approved',resource_ids=[self.row['id']],relation='pending')])
        self.assertTrue(validate([self.row],[self.target],terms=terms)['errors'])


if __name__=='__main__':unittest.main()
