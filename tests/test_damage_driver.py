"""Native queue-to-DrawPrimitive replay; no commercial DLL is loaded."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
AVAILABLE = (importlib.util.find_spec('unicorn') is not None and
             importlib.util.find_spec('pefile') is not None and
             (ROOT / 'runtime/data/Drv/AsrD3DDrv.dll').is_file() and
             (ROOT / 'runtime/data/Asura.dll').is_file())


@unittest.skipUnless(AVAILABLE, 'Native replay needs user-supplied binaries and Unicorn/pefile')
class DamageDriverTests(unittest.TestCase):
    def replay(self):
        from replay_damage_driver import NativeFlush
        return NativeFlush()

    def test_hash_guard_also_works_when_python_assertions_are_disabled(self):
        with patch.object(Path, 'read_bytes', return_value=b'unsupported'):
            with self.assertRaisesRegex(ValueError, 'Unsupported native binary hash'):
                self.replay()

    def test_native_viewport_full_origin_and_nonzero_y_behavior(self):
        n = self.replay()
        n.put(n.obj + 0x14, 2160)
        n.slot(0x554, (0, 0, 3840, 2160))
        self.assertEqual(n.viewport, [0, 0, 3840, 2160, 0, 1])
        n.slot(0x554, (100, 50, 1920, 1080))
        self.assertEqual(n.viewport, [100, 1080, 1920, 1080, 0, 1])

    def test_real_registration_flush_xyz_uv_view_and_world_at_draw_boundary(self):
        n = self.replay()
        identity = [float(i % 5 == 0) for i in range(16)]
        previous = identity.copy()
        previous[12:15] = [10., 20., -100.]
        n.u.mem_write(n.obj + 0x5c, struct.pack('<16f', *previous))
        n.put(n.obj + 0x14, 600)
        n.slot(0x554, (0, 0, 800, 600))
        digit = identity.copy()
        digit[12:15] = [400., 300., -.008]
        vertices = [0., 0., 0., 0., 1., 0., 16., 0., 0., 0.,
                    16., 0., 0., 1., 1., 16., 16., 0., 1., 0.]
        captured = {'args': [0x102, 5, 0, 0, 4, 0xffffffff, 202,
                             0xffffffff, 2, 100, 0, 100, 0, 0],
                    'vertices': vertices, 'matrix': digit}
        draw = n.registered_flush(captured)
        self.assertEqual(draw['fvf'], 0x1e2)  # XYZ, not pre-transformed XYZRHW.
        self.assertEqual(draw['kind'], 5)
        self.assertEqual(draw['transforms']['2'], previous)
        self.assertEqual(draw['transforms']['1'][:14], digit[:14])
        self.assertAlmostEqual(draw['transforms']['1'][14], digit[14], places=7)
        self.assertEqual([v[:3] for v in draw['vertices']],
                         [vertices[i:i + 3] for i in range(0, 20, 5)])
        self.assertEqual([v[6:] for v in draw['vertices']],
                         [vertices[i + 3:i + 5] for i in range(0, 20, 5)])
        self.assertTrue(all(v[4] == 0xffffffff for v in draw['vertices']))
        self.assertEqual(n.word(n.obj + 0x10011c), 0)
        self.assertEqual(list(struct.unpack('<16f', n.transforms[2])), identity)

    def test_native_batch_sort_and_whole_render_loop_preserve_all_digit_textures(self):
        n = self.replay()
        n.put(n.obj + 0x14, 600)
        n.slot(0x554, (0, 0, 800, 600))
        draws = []
        for index, texture in enumerate((202, 201, 195)):
            matrix = [float(i % 5 == 0) for i in range(16)]
            matrix[12:15] = [400. + index * 14, 300., -.008]
            draws.append({'args': [0x102, 5, 0, 0, 4, 0xffffffff, texture,
                                    0xffffffff, 2, 100, 0, 100, 0, 0],
                          'vertices': [0., 0., 0., 0., 1., 0., 16., 0., 0., 0.,
                                       16., 0., 0., 1., 1., 16., 16., 0., 1., 0.],
                          'matrix': matrix})
        result = n.registered_batch(draws)
        self.assertEqual(sorted(n.queue_order), [0, 1, 2])
        self.assertEqual({d['texture_handle'] for d in result}, {202, 201, 195})
        self.assertEqual({d['transforms']['1'][12] for d in result}, {400., 414., 428.})
        self.assertEqual([len(d['vertices']) for d in result], [4, 4, 4])
        expected_x = {202: 400., 201: 414., 195: 428.}
        for draw in result:
            self.assertEqual(draw['transforms']['1'][12], expected_x[draw['texture_handle']])
            self.assertEqual([v[6:] for v in draw['vertices']],
                             [[0., 1.], [0., 0.], [1., 1.], [1., 0.]])
            self.assertEqual({key: draw['renderstates'][key] for key in (27, 19, 20, 60)},
                             {27: 1, 19: 5, 20: 6, 60: 0xffffffff})
            self.assertIn([0, 1, 4], draw['stagestates'])  # Native MODULATE.
            self.assertIn([0, 3, 3], draw['stagestates'])  # Native texture factor.
            self.assertIn([0, 13, 1], draw['stagestates'])  # Owned WRAP boundary.


if __name__ == '__main__':
    unittest.main()
