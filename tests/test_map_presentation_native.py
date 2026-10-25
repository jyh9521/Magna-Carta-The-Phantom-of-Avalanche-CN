"""Render/composite owned fixtures; never start the game or create a desktop window."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_map_atlas import raster

EXE = ROOT/'build/native/Release/map_presentation_fixture.exe'
FRAME = ROOT/'build/native/Release/frame_overlay_fixture.exe'


class MapPresentationTests(unittest.TestCase):
    @unittest.skipUnless(EXE.is_file(), 'Build map_presentation_fixture first')
    def test_exclusive_native_panel_cached_drawing_and_compass_anchor(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='map-presentation-') as d:
            root = Path(d)
            bounds = [-300, 100, 100, 500]
            mesh = dict(points=[(-300,100,0), (100,100,0), (100,500,0), (-300,500,0)],
                        triangles=[(0,1,2), (0,2,3)])
            terrain, viewport = raster([mesh], bounds, 512)
            terrain.save(root/'0009.png')
            (root/'0009.map').write_bytes(struct.pack('<4sII7f', b'MCM1', 512, 512,
                                                     *bounds, *viewport))
            result = subprocess.run([str(EXE), str(root)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            for proof in ('MAP_PRESENTATION PASS window_dc_blits=0 recurring_bitmap_allocations=0',
                          'mini_span=720', 'MAP_NATIVE_PANEL moving_blend_ms=',
                          'mini_full_off=exclusive stale=hidden resize=rebuilt',
                          'moving_full_cache=retained resolutions=24 compass_alpha_bottom=97'):
                self.assertIn(proof, result.stdout)

    @unittest.skipUnless(FRAME.is_file(), 'Build frame_overlay_fixture first')
    def test_single_present_transparent_map_below_captions(self):
        result = subprocess.run([str(FRAME)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('MAP_FRAME_COMPOSITOR PASS alpha=premultiplied transparent=preserved', result.stdout)
        self.assertIn('layer_order=map_caption_notice presents=one window_dc=false', result.stdout)
        self.assertIn('rollback=byte_exact game_started=false', result.stdout)

    def test_no_window_paint_or_periodic_window_management_path(self):
        source = (ROOT/'src/runtime/map_overlay.cpp').read_text(encoding='utf8')
        for removed in ('BeginPaint(', 'CreateWindowExW(', 'SetWindowPos(', 'SetTimer(', 'CreateThread('):
            self.assertNotIn(removed, source)
        self.assertIn('setFramePanel(2,&mapFramePanel)', source)
        self.assertIn('MAP_FRAME_PRESENT_V2', source)
        self.assertIn('engine+0xf1b4c', source)


if __name__ == '__main__':
    unittest.main()
