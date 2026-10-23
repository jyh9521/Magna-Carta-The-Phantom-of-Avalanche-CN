from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import replay_native_dialogue_scene as replay


class DialogueSceneTests(unittest.TestCase):
    def test_unknown_image_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Unsupported full sample'):
            replay.run(b'owned unknown image', b'owned field')

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and
                         (ROOT / 'runtime/data/MCAlpha.dll').is_file(),
                         'Optional native replay dependency/sample')
    def test_field_binding_rejected_on_mismatch(self):
        with self.assertRaisesRegex(RuntimeError, 'Unsupported Field source'):
            replay.run((ROOT / 'runtime/data/MCAlpha.dll').read_bytes(), b'owned field')

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and
                         (ROOT / 'runtime/data/MCAlpha.dll').is_file() and
                         (ROOT / 'runtime/data/Field/0766.fld').is_file(),
                         'Optional native replay dependency/sample/field')
    def test_real_completion_barrier_and_transition_request(self):
        row = replay.run((ROOT / 'runtime/data/MCAlpha.dll').read_bytes(),
                         (ROOT / 'runtime/data/Field/0766.fld').read_bytes())
        self.assertFalse(row['game_started'])
        self.assertFalse(row['scene_loader_executed'])
        self.assertEqual([r['event_cursor'] for r in row['held_before_phase6']], [51] * 6)
        self.assertEqual(row['native_cleanup']['active_actions'], 0)
        self.assertEqual(row['native_cleanup']['destroyed'], 1)
        self.assertEqual(row['transition']['target_field'], 663)
        self.assertEqual(row['transition']['kind'], 31)
        self.assertGreater(row['native_instructions'], 500)

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and
                         (ROOT / 'runtime/data/MCAlpha.dll').is_file() and
                         (ROOT / 'runtime/data/Field/0766.fld').is_file(),
                         'Optional native replay dependency/sample/field')
    def test_attach_to_same_text_replay_preserves_phase(self):
        from replay_native_dialogue_autoplay import Scroll

        class Joined(Scroll):
            scene_poll = False

            def _instruction(self, cpu, address, size, user):
                if self.scene_poll and replay.scene_instruction(self, cpu, address, size, user):
                    return
                super()._instruction(cpu, address, size, user)

        sample = (ROOT / 'runtime/data/MCAlpha.dll').read_bytes()
        joined = Joined(sample, b'owned text boundary')
        replay.initialize_scene(joined, (ROOT / 'runtime/data/Field/0766.fld').read_bytes())
        joined.scene_poll = True
        held = replay.poll_scene(joined)
        self.assertEqual(held['phase'], 2)
        self.assertEqual(joined.read(replay.BUTTON + 0x190), 2)
        self.assertEqual(held['event_cursor'], 51)
        joined.write(replay.BUTTON + 0x190, 6)
        advanced = replay.poll_scene(joined)
        self.assertEqual(advanced['active_after_dialogue_poll'], 0)
        self.assertTrue(advanced['transition_requested'])
        self.assertEqual(joined.transition['target_field'], 663)
