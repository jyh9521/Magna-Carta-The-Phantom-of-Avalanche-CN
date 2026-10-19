"""Replay actual opening pixels through final x86 fixture setter positions.

Reads user-supplied local resources only. Output previews stay outside source.
This verifies the observed dark strip, not actual graphics-driver execution.
"""
import argparse
import json
from pathlib import Path
import subprocess
from PIL import Image
from audit_opening_layout import read_tiles


def verify(source, metadata, fixture, output=None, expect_artifact=False):
    rows = json.loads(metadata.read_text(encoding='utf8'))['layouts']
    replay = subprocess.run([str(fixture.resolve()), '--opening-grid'], text=True, capture_output=True, check=True)
    positions = {}
    for line in replay.stdout.splitlines():
        if line.startswith('OPENING_TILE '):
            _, layout, x, y, final_x, final_y, z = line.split()
            if float(z) != 7:
                raise ValueError('final setter changed depth')
            positions[(int(layout), int(x), int(y))] = (float(final_x), float(final_y))
    canvas_size = (853, 600)  # --opening-grid uses the fixture's default current canvas.
    artifact_pixels = 0
    for row in rows:
        layout = row['layout']
        tiles, _ = read_tiles(source, layout)
        canvas = Image.new('RGB', canvas_size)
        body_only = Image.new('RGB', canvas_size)
        left, top, right, bottom = row['source_tile_bounds']
        for _, _, x, y, pixels in tiles:
            position = positions[(layout, x, y)]
            origin = tuple(round(value) for value in position)
            canvas.paste(pixels, origin)
            if left <= x < right and top <= y < bottom:
                body_only.paste(pixels, origin)
        # Compare rendered pixels against the exact body-only source tiles, rather
        # than an arbitrary dark-color threshold or just a center coordinate.
        a, b = canvas.tobytes(), body_only.tobytes()
        differences = sum(a[i:i + 3] != b[i:i + 3] for i in range(0, len(a), 3))
        artifact_pixels += differences
        if output:
            output.mkdir(parents=True, exist_ok=True)
            canvas.save(output / f'opening-{layout}.png')
    passed = (artifact_pixels > 0) if expect_artifact else (artifact_pixels == 0)
    print(f'OPENING_PIXELS {"PASS" if passed else "FAIL"} artifact_pixels={artifact_pixels} canvas=853x600 source=actual_FDI_BGR positions=final_x86_setter body_pixels=unchanged game_started=false')
    return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--expect-artifact', action='store_true')
    args = parser.parse_args()
    raise SystemExit(verify(args.source, args.metadata, args.fixture, args.output, args.expect_artifact))
