import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import normalize_prompt_punctuation as m

POLICY = json.loads((ROOT/'locales/zh-CN/prompt-punctuation-policy.json').read_text('utf8'))


class PromptPunctuationTests(unittest.TestCase):
    def test_short_prompt(self):
        self.assertEqual(m.normalize('获得%s。', POLICY), '获得%s')
        self.assertEqual(m.normalize('开启用金锁锁住的宝箱。', POLICY), '开启用金锁锁住的宝箱')

    def test_layout_lines_and_tokens(self):
        self.assertEqual(m.normalize('获得%s。\r\n', POLICY), '获得%s\r\n')
        self.assertEqual(m.normalize('获得%s。\n', POLICY), '获得%s\n')
        self.assertEqual(m.normalize('获得%s。$n消耗%s。', POLICY), '获得%s$n消耗%s')
        self.assertEqual(m.normalize('%s$n体力增加%d。$n%s', POLICY), '%s$n体力增加%d$n%s')
        self.assertEqual(m.normalize('$c12火<火>增加%d。', POLICY), '$c12火<火>增加%d')

    def test_compound_sentences_keep_period(self):
        for text in ['获得金币，继续前进。', '得到金币,继续前进。', '获得金币。继续前进。', '真的吗？继续前进。', '等等……走吧。']:
            self.assertEqual(m.normalize(text, POLICY), text)

    def test_dialogue_and_narrative_are_not_selected(self):
        for path in ['text/fpb-opening.json', 'image-group-plans.json', 'video-text-plans.json']:
            self.assertIsNone(m.selected(path, '/0/target', {'id':'Fpb/0000.fpb:text:0:0'}, POLICY))

    def test_all_prompt_domains_clean(self):
        report = m.audit(ROOT/'locales/zh-CN', POLICY)
        self.assertEqual(report['changes'], [])


if __name__ == '__main__':
    unittest.main()
