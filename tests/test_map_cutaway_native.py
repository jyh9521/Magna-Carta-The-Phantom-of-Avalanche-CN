from pathlib import Path
import hashlib
import struct
import subprocess
import sys
import tempfile
import unittest
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_map_atlas import raster
EXE = ROOT/'build/native/Release/map_overlay_fixture.exe'


@unittest.skipUnless(EXE.is_file(), 'Build owned map_overlay_fixture first')
class NativeMapCutawayTests(unittest.TestCase):
    def run_overlay(self, assets, output, mini):
        result = subprocess.run([str(EXE), str(assets), str(output)]+(['--mini'] if mini else []),
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('MAP_OVERLAY_RENDER PASS mode='+('mini' if mini else 'large')+
                      ' size=536x584 source=owned_fixture pixels=rendered game_started=false', result.stdout)
        return Image.open(output).convert('RGB')

    def test_unknown_render_flag_rejected_before_any_window_or_asset_load(self):
        result = subprocess.run([str(EXE), 'unused-assets', 'unused-output.png', '--minni'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
        self.assertIn('MAP_OVERLAY_USAGE_ERROR', result.stderr)

    def compare_mode(self, mini):
        meshes = [{'points': [(-300, 100, 0), (100, 100, 0), (100, 500, 0), (-300, 500, 0),
                               (-200, 200, 70), (0, 200, 70), (0, 400, 70), (-200, 400, 70)],
                   'triangles': [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]}]
        bounds = [-300, 100, 100, 500]
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='native-cutaway-') as d:
            root = Path(d); baseline = root/'baseline'; cutaway = root/'cutaway'; baseline.mkdir(); cutaway.mkdir()
            images = []
            for assets, height in [(baseline, None), (cutaway, 30)]:
                terrain, viewport = raster(meshes, bounds, 512, height)
                terrain.save(assets/'0009.png')
                (assets/'0009.map').write_bytes(struct.pack('<4sII7f', b'MCM1', 512, 512, *bounds, *viewport))
                hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets.iterdir()}
                images.append(self.run_overlay(assets, root/(assets.name+'.png'), mini))
                self.assertEqual(hashes, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets.iterdir()})
            self.assertIsNotNone(ImageChops.difference(*images).getbbox(), 'Cutaway must alter rendered terrain')
            for color in [(255, 166, 35), (75, 220, 110), (181, 114, 235)]:
                masks = []
                for image in images:
                    raw = image.tobytes()
                    masks.append({(i % 536, i // 536) for i, pixel in enumerate(zip(raw[0::3], raw[1::3], raw[2::3])) if pixel == color})
                self.assertTrue(masks[0], 'Expected original player/NPC/box color in native output')
                self.assertEqual(*masks, 'Marker moved when only terrain pixels changed')
            # Original fixture player ends at (-80,260); compute the same metadata projection.
            px = viewport[0]+220*viewport[2]; py = 512-viewport[1]-160*viewport[2]
            if mini:
                expected = (268, 292)  # 516px square at (10,34), player-centered.
            else:
                expected = (round(10+px*516/512), round(34+py*516/512))
            self.assertEqual(images[1].getpixel(expected), (255, 166, 35))

    def test_large_native_view_keeps_markers_and_coordinates(self):
        self.compare_mode(False)

    def test_mini_native_view_keeps_player_centered_and_markers_fixed(self):
        self.compare_mode(True)
