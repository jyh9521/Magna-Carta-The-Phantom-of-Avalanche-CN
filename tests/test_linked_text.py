import copy
import hashlib
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from extract_text_catalog import text_row
from translation_data import linked_conflicts,validate


class LinkedTextTests(unittest.TestCase):
    def test_committed_link_groups_match_source_digests_and_targets(self):
        root=Path(__file__).resolve().parents[1]
        links=json.loads((root/'locales/zh-CN/linked-text.json').read_text('utf8'))
        targets={r['id']:r for p in (root/'locales/zh-CN/text').glob('*.json')
                 for r in json.loads(p.read_text('utf8'))}
        seen=set()
        for group in links['groups']:
            self.assertTrue(group['evidence'])
            self.assertTrue(seen.isdisjoint(group['ids']));seen.update(group['ids'])
            self.assertEqual({targets[key]['source_sha256'] for key in group['ids']},{group['source_sha256']})
            self.assertEqual(len({targets[key]['target'] for key in group['ids']}),1)

    def setUp(self):
        self.catalog=[text_row(f'Fpb/{i}.fpb',0,0,'text',20,b'abc') for i in (0,1)]
        self.targets=[dict(id=r['id'],state='translated',target='相同译文',source_sha256=hashlib.sha256(b'abc').hexdigest()) for r in self.catalog]
        self.links=dict(schema=1,groups=[dict(ids=[r['id'] for r in self.catalog],source_sha256=hashlib.sha256(b'abc').hexdigest(),evidence='owned alternate-scene fixture')])

    def test_matching_and_partial_without_id_merge(self):
        self.assertEqual(linked_conflicts(self.catalog,self.targets,self.links),[])
        self.assertEqual(linked_conflicts(self.catalog,self.targets[:1],self.links),[])
        self.assertEqual(len(self.catalog),2)

    def test_conflict_surfaces_in_full_validator(self):
        self.targets[1]['target']='不同译文'
        report=validate(self.catalog,self.targets,links=self.links)
        self.assertEqual(report['errors'][0]['kind'],'linked_translation_conflict')
        self.assertFalse(report['complete'])

    def test_source_drift_rejected(self):
        self.links['groups'][0]['source_sha256']='0'*64
        with self.assertRaises(ValueError):linked_conflicts(self.catalog,self.targets,self.links)

    def test_unknown_duplicate_overlap_or_missing_evidence(self):
        for kind in ('unknown','duplicate','overlap','evidence'):
            links=copy.deepcopy(self.links);g=links['groups'][0]
            if kind=='unknown':g['ids'][0]='unknown'
            if kind=='duplicate':g['ids'][1]=g['ids'][0]
            if kind=='overlap':links['groups'].append(copy.deepcopy(g))
            if kind=='evidence':g.pop('evidence')
            with self.subTest(kind=kind),self.assertRaises(ValueError):linked_conflicts(self.catalog,self.targets,links)

    def test_preservation_not_equivalent_to_translation(self):
        self.targets[1].update(state='preserved',target=None)
        self.assertEqual(linked_conflicts(self.catalog,self.targets,self.links)[0]['kind'],'linked_translation_conflict')


if __name__=='__main__':unittest.main()
