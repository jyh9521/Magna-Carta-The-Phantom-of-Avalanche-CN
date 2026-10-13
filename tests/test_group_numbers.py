"""Locale-specific squad numbering; ordinary quantities remain untouched."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GroupNumberTests(unittest.TestCase):
    def test_numbered_squads_use_arabic_digits_in_all_targets(self):
        violations = []
        for path in (ROOT / 'locales/zh-CN').rglob('*.json'):
            def visit(value):
                if isinstance(value, dict):
                    if isinstance(value.get('target'), str) and re.search(r'第[一二三四五六七八九十百零〇两]+组', value['target']):
                        violations.append((path.name, value.get('id'), value['target']))
                    for child in value.values():
                        visit(child)
                elif isinstance(value, list):
                    for child in value:
                        visit(child)
            visit(json.loads(path.read_text(encoding='utf8')))
        self.assertEqual(violations, [])

    def test_screenshot_line_and_ordinary_quantity(self):
        rows = json.loads((ROOT/'locales/zh-CN/text/fpb-alternate-scenes.json').read_text(encoding='utf8'))
        self.assertTrue(any('你所在的第7组，成立不久' in (row.get('target') or '') for row in rows))
        rows = json.loads((ROOT/'locales/zh-CN/text/fpb-remaining-scenes.json').read_text(encoding='utf8'))
        self.assertTrue(any('奇怪的一组' in (row.get('target') or '') for row in rows))


if __name__ == '__main__':
    unittest.main()
