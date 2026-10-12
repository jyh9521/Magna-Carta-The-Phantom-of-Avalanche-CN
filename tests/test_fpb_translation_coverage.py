"""Repository-only regression checks for the complete extracted FPB row set."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FpbTranslationCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [r for p in (ROOT / 'locales/zh-CN/text').glob('fpb-*.json')
                    for r in json.loads(p.read_text('utf8'))]
        cls.by_id = {r['id']: r for r in cls.rows}

    def test_complete_extracted_fpb_ids_are_distinct(self):
        self.assertEqual(len(self.rows), 3524)
        self.assertEqual(len(self.by_id), 3524)
        for row in self.rows:
            self.assertRegex(row['id'], r'^Fpb/[0-9]{4}\.fpb:text:[0-9]+:[0-9]+$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')

    def test_preservations_are_explicit_and_excluded_from_translation_count(self):
        preserved = [r for r in self.rows if r['state'] == 'preserved']
        self.assertEqual(len(preserved), 37)
        for row in preserved:
            self.assertIsNone(row['target'])
            self.assertTrue(row['preservation_evidence'])
        self.assertEqual(sum(r['state'] == 'translated' for r in self.rows), 3487)

    def test_final_scene_ordinal_is_not_replaced_by_similar_dialogue(self):
        self.assertEqual(self.by_id['Fpb/0319.fpb:text:0:0']['target'], '卡林兹……')
        self.assertEqual(self.by_id['Fpb/0319.fpb:text:1:1']['target'],
                         '终于来了？心里一直在等，来晚了。')
        self.assertEqual(self.by_id['Fpb/0319.fpb:text:2:2']['target'], '……')

    def test_alternate_scene_changes_and_tags_remain_distinct(self):
        self.assertNotEqual(self.by_id['Fpb/0315.fpb:text:10:10']['target'],
                            self.by_id['Fpb/0721.fpb:text:10:10']['target'])
        self.assertEqual(self.by_id['Fpb/0320.fpb:text:19:22']['target'],
                         self.by_id['Fpb/0743.fpb:text:22:22']['target'])
        self.assertEqual(self.by_id['Fpb/0322.fpb:text:46:94']['state'], 'preserved')

    def test_targets_do_not_contain_generator_placeholders(self):
        for row in self.rows:
            if row['state'] == 'translated':
                self.assertTrue(row['target'])
                self.assertNotIn('\0', row['target'])
                self.assertNotIn('<PRESERVE>', row['target'])
                self.assertNotIn('<REPEAT>', row['target'])
                # Deliberate source emoticons retain Jamo; ordinary Hangul prose does not.
                self.assertIsNone(re.search('[\uac00-\ud7a3]', row['target']), row['id'])


if __name__ == '__main__':
    unittest.main()
