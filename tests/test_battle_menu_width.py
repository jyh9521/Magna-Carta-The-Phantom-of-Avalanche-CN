"""Bounded native branch replay and owned production-hook checks, no game launch."""
import hashlib
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import replay_battle_menu_width as tool

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT/'runtime/data/MCAlpha.dll'


class Guards(unittest.TestCase):
    def test_unknown_engine_rejected_before_emulation(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported complete engine SHA256'):
            tool.BattleWidth(b'owned unknown engine')

    def test_source_mutation_rejected(self):
        if not SAMPLE.exists():
            self.skipTest('Local supported engine not supplied')
        image = bytearray(SAMPLE.read_bytes());image[-1] ^= 1
        with self.assertRaises(ValueError):
            tool.BattleWidth(bytes(image))

    def test_site_mutation_rejected_even_with_test_digest(self):
        if not SAMPLE.exists():
            self.skipTest('Local supported engine not supplied')
        import pefile
        image = bytearray(SAMPLE.read_bytes());pe = pefile.PE(data=image)
        image[pe.get_offset_from_rva(tool.FIRST)] ^= 1
        import replay_native_title
        digest = hashlib.sha256(image).hexdigest()
        with patch.object(tool, 'SOURCE_SHA', digest), patch.object(replay_native_title, 'SUPPORTED_SHAS', {digest}):
            with self.assertRaises(ValueError):
                tool.BattleWidth(bytes(image))

    def test_original_assertion_and_resource_branches(self):
        if not SAMPLE.exists():
            self.skipTest('Local supported engine not supplied')
        result = tool.verify(SAMPLE.read_bytes())
        self.assertFalse(result['game_started']);self.assertFalse(result['game_dll_loaded'])
        self.assertEqual(result['cases']['1067']['assertion']['line'], 169)
        self.assertEqual(result['cases']['800']['resource_id'], 206)

    def test_production_physical_operand(self):
        exe = ROOT/'build/native/Release/wide_ui_fixture.exe'
        if not exe.exists():
            self.skipTest('Build wide_ui_fixture first')
        r = subprocess.run([str(exe), '--battle-width-check'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('BATTLE_WIDTH PASS', r.stdout)


if __name__ == '__main__':
    unittest.main()
