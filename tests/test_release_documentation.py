"""Player-facing release information agrees with the compiled desktop package."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ZH = '《真名法典：冰之魅影》简体中文汉化 + 全面增强补丁'
PROJECT_EN = ('Magna Carta: The Phantom of Avalanche '
              'Simplified Chinese Localization & Enhancement Patch')
ARTICLE = 'https://blog.blfy.cc/posts/magna-carta-the-phantom-of-avalanche-cn/'


class ReleaseDocumentationTests(unittest.TestCase):
    def read(self, name):
        return (ROOT / name).read_text(encoding='utf-8-sig')

    def test_project_names_match(self):
        for name in ('README.md', 'docs/RELEASE_V1.0.md', 'locales/zh-CN/desktop-readme.txt'):
            with self.subTest(name=name):
                text = self.read(name)
                self.assertIn(PROJECT_ZH, text)
                self.assertIn(PROJECT_EN, text)

    def test_original_article_is_in_release_and_package_not_homepage(self):
        for name in ('docs/RELEASE_V1.0.md', 'locales/zh-CN/desktop-readme.txt'):
            with self.subTest(name=name):
                self.assertIn(ARTICLE, self.read(name))
                self.assertIn('项目原始发布页', self.read(name))
        self.assertNotIn(ARTICLE, self.read('README.md'))

    def test_current_release_guides_do_not_describe_unpublished_or_legacy_entries(self):
        for name in ('README.md', 'BUILDING.md', 'docs/RELEASE_V1.0.md',
                     'docs/COMPILED_DESKTOP_RELEASE.md'):
            with self.subTest(name=name):
                text = self.read(name)
                self.assertIn('MagnaCarta-zh-CN-v1.0-release.zip', text)
                for stale in ('尚无 GitHub Release', '尚无 Release', 'Release 与标签列表为空',
                              '本轮不发布附件', '本次只生成本地 v1.0 ZIP'):
                    self.assertNotIn(stale, text)
        for name in ('docs/RELEASE_V1.0.md', 'locales/zh-CN/desktop-readme.txt'):
            text = self.read(name)
            for command in ('Verify-Overlay.ps1 -Action', 'Configure.cmd', 'Play.cmd'):
                self.assertNotIn(command, text)

    def test_player_commands_defaults_and_shortcuts(self):
        catalog = json.loads(self.read('locales/zh-CN/configuration-ui.json'))
        for name in ('docs/RELEASE_V1.0.md', 'locales/zh-CN/desktop-readme.txt'):
            with self.subTest(name=name):
                text = self.read(name)
                for key in ('F5', 'F9', 'F10', 'F11'):
                    self.assertIn(key, text)
                    self.assertIn(key, catalog['controls'])
                self.assertIn('1080P / 无边框窗口化 / 60 帧', text)
                self.assertIn('1080P / 无边框窗口化 / 60 帧', catalog['packaged_default_note'])
                for command in ('Game.exe --check-installed', 'Game.exe --verify-only',
                                'Configure.exe --self-test', 'Game.exe --check-baseline',
                                'Game.exe --rollback'):
                    self.assertIn(command, text)
                self.assertIn('enhancements.json', text)

    def test_preservation_and_feature_boundaries_remain_explicit(self):
        for name in ('docs/RELEASE_V1.0.md', 'locales/zh-CN/desktop-readme.txt'):
            with self.subTest(name=name):
                text = self.read(name)
                for value in ('存档', '手柄', '自由视角', 'SOFTMAX Logo', '原版备份',
                              '--without-test-candidates'):
                    self.assertIn(value, text)

    def test_cleanup_retains_current_release(self):
        self.assertIn("'MagnaCarta-zh-CN-v1.0-release.zip'", self.read('tools/cleanup_release.py'))


if __name__ == '__main__':
    unittest.main()
