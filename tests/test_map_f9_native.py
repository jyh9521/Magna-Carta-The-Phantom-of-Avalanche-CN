"""Exercise the owned F9 canvas/state fixture; no game process is launched."""
from pathlib import Path
import hashlib
import struct
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_map_atlas import raster

EXE = ROOT/'build/native/Release/map_overlay_fixture.exe'
INPUT_EXE = ROOT/'build/native/Release/modern_gamepad_fixture.exe'


def point_fixtures(root):
    points = root/'points'
    points.mkdir()
    row = lambda actor=1, flags=0, x=-140, y=280: struct.pack(
        '<iiiiiIfff', 1, 4, 30, 9, actor, flags, x, y, 33)
    header = lambda field, map_id=9, count=1: struct.pack('<4sIII', b'MCP1', field, map_id, count)
    (points/'0029.poi').write_bytes(header(29, count=3)+row()
                                   +row(flags=1, x=-20, y=300)+row(actor=2, x=-20, y=220))
    (points/'0030.poi').write_bytes(header(30, count=0))
    (points/'0031.poi').write_bytes(b'BAD!'+header(31)[4:]+row())
    (points/'0032.poi').write_bytes(header(32)+row()[:10])
    (points/'0033.poi').write_bytes(header(33)+row(x=float('nan')))
    (points/'0034.poi').write_bytes(header(34, count=65))
    (points/'0035.poi').write_bytes(header(29)+row())
    (points/'0036.poi').write_bytes(header(36, map_id=10)+row())


@unittest.skipUnless(EXE.is_file(), 'Build owned map_overlay_fixture first')
class NativeMapF9Tests(unittest.TestCase):
    def test_field_point_payload_guards_and_same_map_field_switch(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='native-map-points-') as d:
            root = Path(d)
            point_fixtures(root)
            result = subprocess.run([str(EXE), '--points-self-test', str(root)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('MAP_POINTS_GUARD PASS format=MCP1 row_bytes=36', result.stdout)
            self.assertIn('same_map_field_clear=true actor_match=true', result.stdout)

    def test_exit_diamonds_are_actor_filtered_and_conditional_exits_are_hollow(self):
        meshes = [{'points': [(-300, 100, 0), (100, 100, 0),
                               (100, 500, 0), (-300, 500, 0)],
                   'triangles': [(0, 1, 2), (0, 2, 3)]}]
        bounds = [-300, 100, 100, 500]
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='native-map-exits-') as d:
            root = Path(d)
            point_fixtures(root)
            terrain, viewport = raster(meshes, bounds, 512)
            terrain.save(root/'0009.png')
            (root/'0009.map').write_bytes(struct.pack('<4sII7f', b'MCM1', 512, 512,
                                                    *bounds, *viewport))
            output = root/'mini.png'
            result = subprocess.run([str(EXE), str(root), str(output), '--mini'],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            with Image.open(output) as opened:
                image = opened.convert('RGB')
            def center(x, y):
                return round(268+(x+80)*500/240), round(286-(y-260)*500/240)
            cyan = (75, 205, 244)
            self.assertEqual(image.getpixel(center(-140, 280)), cyan)
            self.assertNotEqual(image.getpixel(center(-20, 300)), cyan)
            hx, hy = center(-20, 300)
            self.assertIn(cyan, [image.getpixel((x, y)) for x in range(hx+5, hx+9)
                                for y in range(hy-1, hy+2)])
            fx, fy = center(-20, 220)
            self.assertNotIn(cyan, [image.getpixel((x, y)) for x in range(fx-2, fx+3)
                                   for y in range(fy-2, fy+3)])

    def test_collectible_state_changes_marker_not_npc_position(self):
        meshes = [{'points': [(-300, 100, 0), (100, 100, 0),
                               (100, 500, 0), (-300, 500, 0)],
                   'triangles': [(0, 1, 2), (0, 2, 3)]}]
        bounds = [-300, 100, 100, 500]
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='native-map-items-') as d:
            root = Path(d)
            terrain, viewport = raster(meshes, bounds, 512)
            terrain.save(root/'0009.png')
            (root/'0009.map').write_bytes(struct.pack('<4sII7f', b'MCM1', 512, 512,
                                                    *bounds, *viewport))
            images = {}
            for flag in ['--mini', '--mini-rewards', '--mini-collected']:
                output = root/(flag[2:]+'.png')
                result = subprocess.run([str(EXE), str(root), str(output), flag],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                with Image.open(output) as opened:
                    images[flag] = opened.convert('RGB')
            def center(x, y):
                return round(268+(x+80)*500/240), round(286-(y-260)*500/240)
            npc = center(-100, 250)
            box = center(-180, 320)
            for image in images.values():
                self.assertEqual(image.getpixel(npc), (75, 220, 110))
            self.assertEqual(images['--mini'].getpixel(box), (181, 114, 235))
            self.assertNotEqual(images['--mini-rewards'].getpixel(box), (181, 114, 235))
            bx, by = box
            self.assertIn((181, 114, 235),
                          [images['--mini-rewards'].getpixel((x, y))
                           for x in range(bx+4, bx+7) for y in range(by-1, by+2)])
            self.assertNotIn((181, 114, 235),
                             [images['--mini-collected'].getpixel((x, y))
                              for x in range(bx-6, bx+7) for y in range(by-6, by+7)])
            nx, ny = npc
            self.assertIn((245, 213, 106),
                          [images['--mini-rewards'].getpixel((x, y))
                           for x in range(nx-9, nx+10) for y in range(ny-9, ny+10)])

    @unittest.skipUnless(INPUT_EXE.is_file(), 'Build owned modern_gamepad_fixture first')
    def test_source_message_iat_retains_short_f9_tap(self):
        result = subprocess.run([str(INPUT_EXE), '--map-edge'],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('MAP_F9_MESSAGE PASS short_tap=latched held=single_edge queue_bound=8',
                      result.stdout)
        self.assertIn('source_site=BE01 F8=preserved', result.stdout)
        self.assertIn('rollback=both_IATs game_started=false', result.stdout)

    def test_cycle_and_client_layout(self):
        result = subprocess.run([str(EXE), '--cycle-self-test'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('MAP_F9_CYCLE_V1 PASS', result.stdout)
        self.assertIn('cycle=off_mini_full_off', result.stdout)
        self.assertIn('release_to_rearm=true full_layout=client opacity=150', result.stdout)

    def test_full_canvas_is_transparent_and_preserves_square_projection(self):
        meshes = [{'points': [(-300, 100, 0), (100, 100, 0),
                               (100, 500, 0), (-300, 500, 0)],
                   'triangles': [(0, 1, 2), (0, 2, 3)]}]
        bounds = [-300, 100, 100, 500]
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='native-map-f9-') as d:
            root = Path(d)
            terrain, viewport = raster(meshes, bounds, 512)
            terrain.save(root/'0009.png')
            (root/'0009.map').write_bytes(struct.pack('<4sII7f', b'MCM1', 512, 512,
                                                    *bounds, *viewport))
            source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in root.iterdir()}
            output = root/'full.png'
            result = subprocess.run([str(EXE), str(root), str(output), '--full'],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('MAP_OVERLAY_RENDER PASS mode=full size=1280x720', result.stdout)
            self.assertIn('MAP_OVERLAY_F9 PASS', result.stdout)
            with Image.open(output) as opened:
                image = opened.convert('RGBA')
            self.assertEqual(image.size, (1280, 720))
            self.assertEqual(image.getpixel((0, 0)), (19, 32, 39, 0))
            self.assertEqual(image.getpixel((1279, 719)), (19, 32, 39, 0))
            self.assertEqual(set(image.getchannel('A').getdata()), {0, 150})
            # Full client is 1280x720; the atlas remains a 636px square at (322,36).
            # The owned fixture ends at player (-80,260), NPC (-100,250), box (-180,320).
            for point, color in [((-80, 260), (255, 166, 35, 150)),
                                 ((-100, 250), (75, 220, 110, 150)),
                                 ((-180, 320), (181, 114, 235, 150))]:
                px = viewport[0]+(point[0]-bounds[0])*viewport[2]
                py = 512-viewport[1]-(point[1]-bounds[1])*viewport[2]
                expected = (round(322+px*636/512), round(36+py*636/512))
                self.assertEqual(image.getpixel(expected), color)
            self.assertEqual(source_hashes,
                             {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                              for name in source_hashes})

    def test_live_heading_rotates_arrow_without_moving_player_center(self):
        meshes = [{'points': [(-300, 100, 0), (100, 100, 0),
                               (100, 500, 0), (-300, 500, 0)],
                   'triangles': [(0, 1, 2), (0, 2, 3)]}]
        bounds = [-300, 100, 100, 500]
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='native-map-heading-') as d:
            root = Path(d)
            terrain, viewport = raster(meshes, bounds, 512)
            terrain.save(root/'0009.png')
            (root/'0009.map').write_bytes(struct.pack('<4sII7f', b'MCM1', 512, 512,
                                                    *bounds, *viewport))
            for name, (dx, dy) in [('east', (1, 0)), ('north', (0, -1)),
                                    ('west', (-1, 0)), ('south', (0, 1))]:
                with self.subTest(direction=name):
                    output = root/(name+'.png')
                    result = subprocess.run([str(EXE), str(root), str(output), '--mini-'+name],
                                            capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                    self.assertIn('MAP_LIVE_MARKERS PASS NPC=live_green', result.stdout)
                    with Image.open(output) as opened:
                        image = opened.convert('RGB')
                    self.assertEqual(image.getpixel((268, 286)), (255, 166, 35))
                    self.assertEqual(image.getpixel((268+6*dx, 286+6*dy)), (255, 166, 35))
                    self.assertNotEqual(image.getpixel((268-7*dx, 286-7*dy)), (255, 166, 35))


if __name__ == '__main__':
    unittest.main()
