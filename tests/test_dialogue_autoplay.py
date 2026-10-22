from pathlib import Path
import importlib.util
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import replay_native_dialogue_autoplay as replay


class DialogueAutoplayTests(unittest.TestCase):
    def test_unsupported_source_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'Unsupported full sample'):
            replay.run(b'owned fixture')

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and (ROOT/'runtime/data/MCAlpha.dll').is_file(),
                         'Optional native replay/sample')
    def test_original_native_expiry_waits_for_voice_after_adapter(self):
        image=(ROOT/'runtime/data/MCAlpha.dll').read_bytes()
        for modified,manual,expected in [(False,False,0),(True,False,400),(True,True,10)]:
            row=replay.voice_tail_case(image,modified,manual)
            self.assertEqual(row['dialogue_ends_tick'],expected)

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and (ROOT/'runtime/data/MCAlpha.dll').is_file(),
                         'Optional native replay/sample')
    def test_native_multi_page_scroll_preserves_every_byte(self):
        image=(ROOT/'runtime/data/MCAlpha.dll').read_bytes()
        row=replay.scroll_case(image,b'ABCDEFGHIJKLMNOPQRSTUVWX','owned_ascii')
        self.assertTrue(row['labels_complete'])
        self.assertEqual(row['label_count'],6)
        self.assertEqual(row['inputs'],0)
