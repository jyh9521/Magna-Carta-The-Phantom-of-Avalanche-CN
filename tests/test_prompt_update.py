from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_prompt_update as m
from native_text_codec import encode, decode


class PromptUpdateTests(unittest.TestCase):
    def test_existing_mapping_roundtrip_without_reallocation(self):
        # Minimal generated-header fixture uses a verified native private pair.
        header='const SystemGlyph localeSystemGlyphs[] = {\n{0xcaa0,L"\\u3002"},\n};'
        mapping=m.mapping_from_header(header)
        self.assertEqual(mapping['。']['encoded_hex'],'caa0')
        self.assertEqual(decode(encode('%s。',mapping),mapping),'%s。')

    def test_duplicate_mapping_rejected(self):
        header='const SystemGlyph localeSystemGlyphs[] = {\n{0xcaa0,L"\\u3002"},\n{0xcb40,L"\\u3002"},\n};'
        with self.assertRaisesRegex(ValueError,'duplicate'):
            m.mapping_from_header(header)

    def test_shortened_field_preserves_neighbors_and_padding(self):
        raw=b'PREFIXprompt.\0\x99SUFFIX'
        result=m.checked_replace(raw,6,b'prompt.',b'prompt',8)
        self.assertEqual(result,b'PREFIXprompt\0\0\x99SUFFIX')
        self.assertEqual(len(result),len(raw))

    def test_unknown_baseline_expansion_and_capacity_fail(self):
        for before,after,capacity in [(b'wrong',b'new',8),(b'old',b'longer',8),(b'old',b'x',3)]:
            with self.assertRaises(ValueError):
                m.checked_replace(b'old\0',0,before,after,capacity)


if __name__=='__main__':
    unittest.main()
