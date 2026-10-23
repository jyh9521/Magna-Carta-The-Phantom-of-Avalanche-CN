"""Compiled controller-context regressions; native GUI replay has a separate suite."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'src/runtime'


class BattleGamepadContextTests(unittest.TestCase):
    def executable(self, name):
        path = ROOT / 'build/native/Release' / (name + '.exe')
        if not path.exists():
            self.skipTest('Build the owned ' + name + ' target first')
        return path

    def invoke(self, name, *args):
        result = subprocess.run([str(self.executable(name)), *args], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_actual_compiled_context_boundary_and_physical_preservation(self):
        output = self.invoke('modern_gamepad_fixture', '--battle-context')
        for marker in ['B=RMB_release', 'held_context_rearm=true',
                       'mouse_cancel_on_focus=true', 'unknown_mode=blocked',
                       'physical_keyboard=preserved', 'mixed_mouse_priority=true']:
            self.assertIn(marker, output)

    def test_fresh_edge_is_not_blocked_like_carried_hold(self):
        source = (RUNTIME / 'battle_pad_context.h').read_text(encoding='utf-8')
        self.assertIn('buttons&previous_&semantic', source)
        fixture = (RUNTIME / 'modern_gamepad_fixture.cpp').read_text(encoding='utf-8')
        self.assertIn('fresh edge at boundary', fixture)
        self.assertIn('gate.update(1,4,XINPUT_GAMEPAD_A)', fixture)
        self.assertIn('gate.update(1,5,XINPUT_GAMEPAD_A)', fixture)
        self.invoke('modern_gamepad_fixture', '--battle-context')

    def test_actual_compiled_route_outputs_for_each_native_mode(self):
        for mode, confirm in [(1, 32), (4, 1), (5, 1), (6, 1), (7, 32), (99, None)]:
            with self.subTest(mode=mode):
                rows = [json.loads(line) for line in self.invoke(
                    'battle_gamepad_chain_fixture', str(mode)).splitlines() if line]
                frames = {row['action']: row for row in rows if row.get('kind') == 'frame'}
                keys = bytes.fromhex(frames['A_down']['keys'])
                active = [i for i, value in enumerate(keys) if value & 0x80]
                self.assertEqual(active, [] if confirm is None else [confirm])
                self.assertEqual(frames['up_down']['nav_active'], mode in (4, 5, 6))
                if mode != 99:
                    keys = bytes.fromhex(frames['B_down']['keys'])
                    self.assertTrue(keys[2] & 0x80)
                    self.assertFalse(keys[27] & 0x80)

    def test_constructor_owner_and_unknown_cursor_guards_are_production_checks(self):
        source = (RUNTIME / 'modern_gamepad.cpp').read_text(encoding='utf-8')
        for marker in ['bytes[0xae411]!=0xc7', 'bytes+0xae413',
                       'gui+0x1bc)!=scene', 'engine+0xc203c',
                       'elapsed,w,h,eligible)', '!battleBlocked&&triggers']:
            self.assertIn(marker, source)
        self.assertNotIn('BATTLE_INPUT_READY A=Space B=Esc', source)

    def test_actual_native_constructor_and_inherited_button_bytes(self):
        sample = ROOT / 'runtime/data/MCAlpha.dll'
        if not sample.exists():
            self.skipTest('Supported original engine is not supplied')
        import pefile
        data = sample.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         '7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e')
        mapped = pefile.PE(data=data).get_memory_mapped_image()
        self.assertEqual(mapped[0xae411:0xae417], bytes.fromhex('c7023c200c52'))
        self.assertEqual(mapped[0x5c57e:0x5c583], bytes.fromhex('e8cda2ffff'))
        self.assertEqual(mapped[0x5c586:0x5c58c], bytes.fromhex('c700dc000c52'))
        self.assertEqual(mapped[0x56896:0x5689c], bytes.fromhex('c70080ee0b52'))
        self.assertEqual(struct.unpack_from('<I', mapped, 0xc00dc + 4)[0],
                         struct.unpack_from('<I', mapped, 0xbee80 + 4)[0])

    def test_compiled_inherited_press_cancellation_retains_other_routes(self):
        output = self.invoke('world_gamepad_fixture')
        self.assertIn('GAMEPAD_DERIVED_BUTTON_CANCEL PASS class=C00DC', output)
        self.assertIn('release_action=false', output)
        self.assertIn('WORLD_GAMEPAD_FIXTURE PASS', output)
        source = (RUNTIME / 'gamepad_ui.cpp').read_text(encoding='utf-8')
        self.assertIn('vt==engine+0xbee80||vt==engine+0xc00dc', source)
        self.assertIn('memcmp(p+0x5c57e,inheritedButton', source)


if __name__ == '__main__':
    unittest.main()
