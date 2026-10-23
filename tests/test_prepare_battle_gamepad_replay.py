"""Reproducible owned-source stage preparation, independent of a game install."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import prepare_battle_gamepad_replay as tool


class PrepareBattleGamepadReplay(unittest.TestCase):
    def test_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'new, independent'):
                tool.prepare(directory, 'cmake')

    def test_game_runtime_destination_rejected_before_subprocess(self):
        with patch.object(tool.subprocess, 'check_output') as git:
            with self.assertRaisesRegex(ValueError, 'new, independent'):
                tool.prepare(ROOT/'runtime'/'owned-replay-rejected', 'cmake')
            git.assert_not_called()

    def run_fixture(self, drift=False):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); source = base/'source'; source.mkdir()
            original = {name: ('baseline '+name).encode() for name in (*tool.CORE, *tool.COMMON)}
            for name in (*tool.CORE, *tool.COMMON, *tool.ADAPTERS):
                data = original[name] if name in tool.COMMON else ('modified '+name).encode()
                (source/name).write_bytes(data)
            (source/'owned.h').write_text('// owned fixture\n', encoding='utf-8')
            original['owned.h'] = b'// owned fixture\n'
            if drift:
                (source/tool.COMMON[0]).write_bytes(b'changed dependency')
            output = base/'prepared'

            def git(args, **kwargs):
                self.assertEqual(args[:2], ['git', 'show'])
                self.assertTrue(args[2].startswith(tool.BASELINE+':src/runtime/'))
                return original[args[2].rsplit('/', 1)[1]]

            def run(args, **kwargs):
                stdout = ('{"kind":"metadata","game_started":false}\n'
                          if str(args[0]).endswith('.exe') else 'owned build succeeded\n')
                return subprocess.CompletedProcess(args, 0, stdout, '')

            with patch.object(tool, 'SOURCE', source), patch.object(tool.subprocess, 'check_output', side_effect=git), patch.object(tool.subprocess, 'run', side_effect=run):
                if drift:
                    with self.assertRaisesRegex(ValueError, 'common-source drift'):
                        tool.prepare(output, 'cmake')
                    self.assertFalse(output.exists())
                else:
                    result = tool.prepare(output, 'cmake')
                    self.assertEqual(result['sources']['baseline'], result['sources']['rollback'])
                    self.assertNotEqual(result['sources']['baseline'][tool.CORE[0]], result['sources']['modified'][tool.CORE[0]])
                    self.assertEqual(len(result['commands']), 24)
                    self.assertEqual(len(list(output.glob('*-mode*.jsonl'))), 18)
                    self.assertTrue(all(row['exit_status'] == 0 for row in result['commands']))
                    self.assertFalse(result['game_data_copied'])
                    self.assertFalse(result['game_started'])
                    self.assertEqual(json.loads((output/'prepared.json').read_text())['baseline_commit'], tool.BASELINE)
                    self.assertIn('Win32', result['commands'][0]['command'])

    def test_three_stages_and_six_mode_traces_have_exact_rollback(self):
        self.run_fixture()

    def test_changed_common_code_rejected_before_output_creation(self):
        self.run_fixture(drift=True)


if __name__ == '__main__':
    unittest.main()
