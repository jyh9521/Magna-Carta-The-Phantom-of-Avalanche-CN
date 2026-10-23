from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import replay_native_dialogue_chain as replay


class DialogueChainTests(unittest.TestCase):
    def trace(self, statuses=(4, 2)):
        rows = ['wall_ms,position_ms,total_ms,status,native_playing']
        for i in range(21):
            state = statuses[1] if i == 20 else statuses[0]
            rows.append(f'{i*100},{i*100},2000,{state},{int(state == 4)}')
        raw = ('\n'.join(rows)+'\n').encode()
        payload = b'owned audio sample'
        log = ('AUDIO_SHA256 '+hashlib.sha256(payload).hexdigest()+'\nTRACE_SHA256 '+
               hashlib.sha256(raw).hexdigest()+'\nentry_executed=false\n'
               'DIALOGUE_AUDIO PASS seek_ms=0 natural_end=true')
        return raw, log, payload

    def test_real_trace_schema_and_binding_validation(self):
        raw, log, payload = self.trace()
        rows = replay.playback_trace(raw, log, payload)
        self.assertEqual(rows[-1]['status'], 2)
        for changed in (raw+b'\n', raw.replace(b'2000,2,0', b'2000,4,1')):
            with self.assertRaisesRegex(RuntimeError, 'CSV/log mismatch'):
                replay.playback_trace(changed, log, payload)
        with self.assertRaisesRegex(RuntimeError, 'payload/log mismatch'):
            replay.playback_trace(raw, log, b'different')

    def test_seeked_and_incomplete_playback_rejected(self):
        raw, log, payload = self.trace()
        with self.assertRaisesRegex(RuntimeError, 'full natural playback'):
            replay.playback_trace(raw, log.replace('seek_ms=0 ', 'seek_ms=1000 '), payload)
        raw, log, payload = self.trace((4, 4))
        with self.assertRaisesRegex(RuntimeError, 'Incomplete natural playback'):
            replay.playback_trace(raw, log, payload)

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and all((ROOT/path).is_file()
                         for path in ('build/dialogue-chain-evidence/audio1500.csv',
                                      'build/dialogue-chain-evidence/audio1500-traced.txt',
                                      'runtime/data/MCAlpha.dll', 'runtime/data/Field/0766.fld')),
                         'Optional locally captured real Miles trace')
    def test_real_text_audio_barrier_and_transition(self):
        evidence = ROOT/'build/dialogue-chain-evidence'
        row = replay.run(ROOT/'runtime/data', evidence/'audio1500.csv',
                         evidence/'audio1500-traced.txt')
        self.assertTrue(row['original_premature_close_reproduced'])
        original, guarded = row['cases']
        self.assertTrue(original['original_audio_still_playing_at_close'])
        self.assertFalse(guarded['original_audio_still_playing_at_close'])
        self.assertGreater(guarded['held_ticks'], 0)
        for case in row['cases']:
            self.assertEqual(case['native_transition']['target_field'], 663)
            self.assertTrue(case['all_labels_revealed_before_delete'])
            self.assertGreater(case['scene_barrier_polls'], 100)
        self.assertFalse(row['game_started'])
        json.dumps(row)


if __name__ == '__main__':
    unittest.main()
