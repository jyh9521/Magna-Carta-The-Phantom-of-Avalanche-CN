import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import term_glossary as m


def fixture():
    return dict(schema=1,reference=dict(repository='https://example.org/reference',commit='fixture',sha256='fixture'),
                terms=[dict(id='one',source='카르타',target='卡尔塔',category='力量',status='待复核',
                            meaning='受控概念',resource_ids=['row'],translation_state='approved',relation='pending')])


class TermGlossaryTests(unittest.TestCase):
    def test_longest_phrase_and_no_unreviewed_resource_matching(self):
        data=fixture();long=copy.deepcopy(data['terms'][0]);long.update(id='two',source='마그나 카르타',target='真名法典')
        data['terms'].append(long)
        self.assertEqual([h['term']['id'] for h in m.matches('마그나 카르타','row',data['terms'])],['two'])
        self.assertEqual(m.matches('카르타','unknown',data['terms']),[])

    def test_inheritance_requires_confirmed_semantics(self):
        data=fixture();term=data['terms'][0];term['status']='继承自《真红的圣痕》'
        with self.assertRaises(ValueError):m.validate(data)
        term.update(relation='confirmed_shared',confirmed_reference_line=4,concept_match_evidence='same controlled concept',
                    reference_candidates=[dict(line=4,status='已统一',target='卡尔塔')])
        m.validate(data);term['target']='新名字'
        with self.assertRaises(ValueError):m.validate(data)

    def test_duplicate_concept_or_resource_rejected(self):
        data=fixture();data['terms'].append(copy.deepcopy(data['terms'][0]))
        with self.assertRaises(ValueError):m.validate(data)
        data=fixture();data['terms'][0]['resource_ids']=['row','row']
        with self.assertRaises(ValueError):m.validate(data)

    def test_conflict_report_not_replacement(self):
        data=fixture()
        self.assertEqual(m.conflicts('카르타','卡尔塔','row',data['terms']),[])
        result=m.conflicts('카르타','其他','row',data['terms'])
        self.assertEqual(result[0]['expected'],'卡尔塔')
        self.assertEqual(result[0]['kind'],'review_required_not_automatic_replacement')

    def test_candidate_is_not_forced_into_translation(self):
        data=fixture();data['terms'][0]['translation_state']='candidate'
        self.assertEqual(m.conflicts('카르타','其他','row',data['terms']),[])

    def test_canonical_glossary_matches_structured_data(self):
        data=json.loads((ROOT/'locales/zh-CN/terms.json').read_text('utf8'))
        self.assertEqual((ROOT/'GLOSSARY.md').read_text('utf8'),m.render(data))
        self.assertEqual(len(data['terms']),110)


if __name__=='__main__':unittest.main()
