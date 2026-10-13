import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FeedbackLayoutTests(unittest.TestCase):
    def test_visible_vow_canvas_center(self):
        data = json.loads((ROOT/'locales/zh-CN/image-group-plans.json').read_text(encoding='utf8'))
        groups = [g for g in data['groups'] if g['id'].startswith('opening-vow-')]
        self.assertEqual(len(groups), 2)
        for group in groups:
            width = 640 if 'first' in group['id'] else 768
            for plan in group['plans']:
                if plan.get('target'):
                    self.assertEqual(plan['mask_xyxy'][2], width)

    def test_audio_labels_stay_inside_original_bars(self):
        data = json.loads((ROOT/'locales/zh-CN/image-text-plans.json').read_text(encoding='utf8'))
        row = next(r for r in data['resources'] if r['resource']=='BGR/0191.BGR')
        for target, (top,bottom) in zip(['音乐','音效','语音'], [(64,84),(89,109),(114,134)]):
            plan = next(p for p in row['plans'] if p.get('target')==target)
            self.assertGreaterEqual(plan['mask_xyxy'][1], top+1)
            self.assertLessEqual(plan['mask_xyxy'][3], bottom-1)
            for rect in plan['erase_rects_xyxy']:
                self.assertGreaterEqual(rect[1], top+1)
                self.assertLessEqual(rect[3], bottom-1)
        tip = next(p for p in row['plans'] if p.get('target')=='请调整音量。')
        self.assertIn([90,144,166,157],tip['erase_rects_xyxy'])


if __name__ == '__main__':
    unittest.main()
