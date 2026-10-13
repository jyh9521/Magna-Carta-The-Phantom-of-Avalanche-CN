import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_feedback_trial as tool


class FeedbackTrialTests(unittest.TestCase):
    def test_shared_data_and_isolated_switches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = root / 'game'
            prior = game / '.advanced-runtime'
            prior.mkdir(parents=True)
            native = root / 'native'
            native.mkdir()
            for name in ['StartEnhanced.ps1', 'EnhancementSettings.psm1', 'manifest.json',
                         'title-background.json', 'workspace_profile.dll', 'workspace_launcher.exe']:
                (prior / name).write_bytes(b'baseline')
            for name in ['workspace_profile.dll', 'workspace_launcher.exe']:
                (native / name).write_bytes(b'candidate')
            out = root / 'feedback'
            tool.prepare(game, native, out)
            motion = json.loads((out / 'motion-repair.json').read_text())
            menu = json.loads((out / 'menu-repair.json').read_text())
            self.assertTrue(motion['motion60'])
            self.assertFalse(motion['native_gamepad'])
            self.assertFalse(menu['motion60'])
            self.assertTrue(menu['native_gamepad'])
            self.assertEqual((prior / 'workspace_profile.dll').read_bytes(), b'baseline')
            self.assertFalse((out / 'MAP').exists())
            self.assertIn('-WithoutTextureGuard', (out / 'Play-motion-repair.cmd').read_text())
            self.assertTrue((out / 'Play-baseline.cmd').is_file())
            self.assertRaises(ValueError, tool.prepare, game, native, out)
