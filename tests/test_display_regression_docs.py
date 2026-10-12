"""Check regression status and testing coordination without starting the game."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DisplayRegressionDocsTests(unittest.TestCase):
    def test_report_and_coordination(self):
        issue = (ROOT / 'docs/KNOWN_ISSUES.md').read_text(encoding='utf-8')
        testing = (ROOT / 'docs/RUNTIME_TESTING.md').read_text(encoding='utf-8')
        contribution = (ROOT / 'CONTRIBUTING.md').read_text(encoding='utf-8')
        isolation = (ROOT / 'docs/RUNTIME_ISOLATION.md').read_text(encoding='utf-8')
        for token in ('DISPLAY-01', '未修复', '尚未独立复现'):
            self.assertIn(token, issue)
        for token in ('明确测试确认', '手动启动', '不启动游戏', '每次只改变一个'):
            self.assertIn(token, testing)
        self.assertIn('持续开发指令不包含自动启动游戏的授权', contribution)
        self.assertIn('不自动调用', isolation)


if __name__ == '__main__':
    unittest.main()
