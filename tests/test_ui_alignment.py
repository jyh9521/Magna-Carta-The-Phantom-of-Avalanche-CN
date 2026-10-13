import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class AlignmentPlansTests(unittest.TestCase):
    def setUp(self):
        data=json.loads((ROOT/'locales/zh-CN/image-text-plans.json').read_text('utf8'))
        self.rows={r['resource']:r['plans'] for r in data['resources']}

    def test_silver_key_cleanup_preserves_ea_badge(self):
        p=next(p for p in self.rows['BGR/0261.BGR'] if p.get('target')=='银钥匙')
        for rect in [p['mask_xyxy'],*p['erase_rects_xyxy']]:self.assertLessEqual(rect[2],205)

    def test_page_labels_use_original_visible_width(self):
        for n in [284,285,423,424]:
            p=self.rows[f'BGR/{n:04}.BGR'][0]
            self.assertEqual(p['mask_xyxy'],[5,1,88,18])
            self.assertIn([0,0,91,21],p['erase_rects_xyxy'])

    def test_item_status_characters_are_upright(self):
        p=self.rows['BGR/0262.BGR'][1]
        self.assertEqual(p.get('rotation',0),0)
        self.assertEqual(p.get('flow'),'vertical')

    def test_audio_left_residue_column_is_in_cleanup(self):
        p=next(p for p in self.rows['BGR/0191.BGR'] if p.get('target')=='音效')
        self.assertTrue(any(r[0]<=23 and r[1]<=91 and r[2]>24 and r[3]>=105 for r in p['erase_rects_xyxy']))
