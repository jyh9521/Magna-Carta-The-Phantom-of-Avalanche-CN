"""Read-only audit of the supported localized opening's actual FDI/BGR ink.

The translation composite plan is intentionally NOT used as runtime geometry.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image
from resource_image import parse


def read_tiles(source, layout):
    """Read actual FDI children, including source pixels outside the old viewport."""
    fdi = source / 'FrameData' / f'{layout:04d}.fdi'
    data = fdi.read_bytes()
    if len(data) != 787 or data[:8] != bytes.fromhex('ba00000001000000'):
        raise ValueError('unsupported FDI layout')
    digests = {str(fdi.relative_to(source)): hashlib.sha256(data).hexdigest()}
    tiles = []
    for index in range(15):
        tile = data[157 + index * 42:157 + (index + 1) * 42]
        if tile[0] == 0:
            continue
        anchor, x, y, kind, resource = struct.unpack_from('<iiiii', tile, 2)
        if anchor != 1 or kind != 3 or not (0 <= x <= 768 and 0 <= y <= 512):
            raise ValueError('unsupported FDI tile geometry')
        path = source / 'BGR' / f'{resource:04d}.BGR'
        raw = path.read_bytes()
        digests[str(path.relative_to(source))] = hashlib.sha256(raw).hexdigest()
        image = parse(raw)
        if (image.width, image.height) != (256, 256):
            raise ValueError('unsupported BGR tile dimensions')
        pixels = Image.frombytes('RGBA', (256, 256), image.rgba()).convert('RGB')
        tiles.append((index, resource, x, y, pixels))
    return tiles, digests


def audit(source, layout, threshold=160):
    canvas = Image.new('RGB', (1024, 768))
    tiles, digests = read_tiles(source, layout)
    for _, _, x, y, pixels in tiles:
        canvas.paste(pixels, (x, y))
    box = canvas.convert('L').point(lambda pixel: 255 if pixel > threshold else 0).getbbox()
    if not box:
        raise ValueError('opening has no bright ink')
    return {'layout': layout, 'threshold': threshold, 'ink_xyxy': box,
            'ink_center': [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2],
            'sha256': digests, 'game_started': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--layout', type=int, action='append', required=True)
    args = parser.parse_args()
    print(json.dumps([audit(args.source, layout) for layout in args.layout], indent=2))
