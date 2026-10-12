"""Lossless reader for observed wrapped BGR TGA/BMP images, not TXRS."""
import argparse
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import struct

TGA_FOOTER = b'\0' * 8 + b'TRUEVISION-XFILE.\0'


@dataclass(frozen=True)
class ResourceImage:
    wrapper: bytes
    header: bytes
    bitmap: bytes
    suffix: bytes
    format: str
    width: int
    height: int
    stride: int

    def rgba(self):
        """Return top-left-origin, row-major RGBA bytes without changing storage."""
        channels = 4 if self.format == 'TGA' else 3
        result = bytearray(self.width * self.height * 4)
        for y in range(self.height):
            start = (self.height - 1 - y) * self.stride
            row = self.bitmap[start:start + self.width * channels]
            dest = y * self.width * 4
            result[dest:dest + self.width * 4:4] = row[2::channels]
            result[dest + 1:dest + self.width * 4:4] = row[1::channels]
            result[dest + 2:dest + self.width * 4:4] = row[0::channels]
            result[dest + 3:dest + self.width * 4:4] = row[3::4] if channels == 4 else b'\xff' * self.width
        return bytes(result)

    def replace_rgba(self, pixels):
        """Keep dimensions, header, wrapper, row padding and footer unchanged."""
        if not isinstance(pixels, (bytes, bytearray, memoryview)):
            raise ValueError('pixels must be a byte buffer')
        pixels = bytes(pixels)
        if len(pixels) != self.width * self.height * 4:
            raise ValueError('RGBA length mismatch')
        channels = 4 if self.format == 'TGA' else 3
        if channels == 3 and any(a != 255 for a in pixels[3::4]):
            raise ValueError('BMP cannot represent replacement alpha')
        bitmap = bytearray(self.bitmap)
        for y in range(self.height):
            row = pixels[y * self.width * 4:(y + 1) * self.width * 4]
            dest = (self.height - 1 - y) * self.stride
            stop = dest + self.width * channels
            bitmap[dest:stop:channels] = row[2::4]
            bitmap[dest + 1:stop:channels] = row[1::4]
            bitmap[dest + 2:stop:channels] = row[0::4]
            if channels == 4:
                bitmap[dest + 3:stop:4] = row[3::4]
        result = replace(self, bitmap=bytes(bitmap))
        result.to_bytes()
        return result

    def to_bytes(self):
        data = self.wrapper + self.header + self.bitmap + self.suffix
        parsed = parse(data)
        if parsed != self:
            raise ValueError('image metadata does not match stored headers')
        return data


def _candidate(data, offset):
    payload = data[offset:]
    if offset == 24 and payload[:2] == b'BM':
        if len(payload) < 54:
            raise ValueError('truncated BMP header')
        size = struct.unpack_from('<I', payload, 2)[0]
        pixel_offset, dib = struct.unpack_from('<II', payload, 10)
        width, height, planes, bits, compression, image_size = struct.unpack_from('<iiHHII', payload, 18)
        if pixel_offset != 54 or dib != 40 or planes != 1 or bits != 24 or compression != 0 or image_size != 0:
            raise ValueError('unsupported BMP variant')
        if not 1 <= width <= 4096 or not 1 <= height <= 4096:
            raise ValueError('unsupported BMP dimensions or direction')
        stride = ((width * 3 + 3) // 4) * 4
        if size != len(payload) or len(payload) != 54 + stride * height + 2 or payload[-2:] != b'\0\0':
            raise ValueError('BMP length mismatch')
        return ResourceImage(data[:offset], payload[:54], payload[54:-2], payload[-2:], 'BMP', width, height, stride)
    if len(payload) < 44:
        raise ValueError('truncated TGA')
    if payload[:3] != b'\0\0\x02' or payload[3:8] != b'\0' * 5 or payload[16:18] != b'\x20\x08':
        raise ValueError('unsupported TGA variant')
    width, height = struct.unpack_from('<HH', payload, 12)
    if not 1 <= width <= 4096 or not 1 <= height <= 4096:
        raise ValueError('unsupported TGA dimensions')
    stride = width * 4
    if len(payload) != 18 + stride * height + 26 or payload[-26:] != TGA_FOOTER:
        raise ValueError('TGA length/footer mismatch')
    return ResourceImage(data[:offset], payload[:18], payload[18:-26], payload[-26:], 'TGA', width, height, stride)


def parse(data):
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError('image must be a byte buffer')
    data = bytes(data)
    candidates = []
    for offset in (12, 24, 40, 56):
        try:
            candidates.append(_candidate(data, offset))
        except (ValueError, struct.error):
            pass
    if len(candidates) != 1:
        raise ValueError('unsupported or ambiguous wrapped BGR image')
    return candidates[0]


def inspect(source):
    files = sorted(Path(source).glob('*.BGR'))
    if not files:
        raise ValueError('no BGR files found')
    rows = []
    for path in files:
        data = path.read_bytes()
        parsed = parse(data)
        rebuilt = parsed.replace_rgba(parsed.rgba()).to_bytes()
        if rebuilt != data or path.read_bytes() != data:
            raise ValueError('pixel roundtrip mismatch or source changed')
        rows.append(dict(name=path.name, sha256=hashlib.sha256(data).hexdigest(),
                         size=len(data), format=parsed.format, width=parsed.width,
                         height=parsed.height, wrapper_size=len(parsed.wrapper),
                         pixel_offset=len(parsed.wrapper) + len(parsed.header),
                         pixel_bytes=len(parsed.bitmap), roundtrip_exact=True))
    return dict(schema=1, files=rows, evidence_type='static_pixel_roundtrip',
                original_files_changed=False, game_started=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.resolve().is_relative_to(args.source.resolve()):
        raise ValueError('report must be new and outside source directory')
    result = inspect(args.source)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=True, indent=2)
    print(f'IMAGE_PIXEL_ROUNDTRIP_PASS files={len(result["files"])} original_files_changed=false game_started=false')
