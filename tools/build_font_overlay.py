"""Build native glyph deltas from an explicitly supplied, digest-locked font."""
import argparse
import hashlib
import json
from pathlib import Path

from native_text_codec import plan, encode, decode
from resource_font import parse


def sha(data): return hashlib.sha256(data).hexdigest()


def translation_corpus(path):
    """Read UTF-8 target rows instead of passing a whole game through argv."""
    path = Path(path).resolve(strict=True)
    original = path.read_bytes()
    rows = json.loads(original.decode('utf8'))
    if not isinstance(rows, list) or not rows:
        raise ValueError('translation corpus must be a nonempty row list')
    ids = set()
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']
                or row['id'] in ids or not isinstance(row.get('target'), str)):
            raise ValueError('translation corpus has missing target or invalid/duplicate ID')
        if '\0' in row['target']:
            raise ValueError('translation corpus contains embedded terminator')
        ids.add(row['id'])
    text = '\n'.join(row['target'] for row in sorted(rows, key=lambda row: row['id']))
    return text, (path, original, len(rows))


def rasterize(character, font_path, height, pitch, variations=(), face_cache=None):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('L', (height, height), 0)
    face_cache = {} if face_cache is None else face_cache
    for size in range(height - 1, 1, -1):
        key = (size, tuple(variations))
        if key not in face_cache:
            face_cache[key] = ImageFont.truetype(str(font_path), size=size)
            if variations:
                face_cache[key].set_variation_by_axes(list(variations))
        face = face_cache[key]
        bbox = face.getbbox(character)
        width, glyph_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if width <= height - 2 and glyph_height <= height - 2:
            break
    else:
        raise ValueError('glyph does not fit native cell')
    origin = ((height - width)//2 - bbox[0], (height - glyph_height)//2 - bbox[1])
    ImageDraw.Draw(image).text(origin, character, font=face, fill=255)
    data = bytearray(height * pitch)
    for y in range(height):
        for x in range(height):
            if image.getpixel((x, y)) >= 128:
                data[y * pitch + x//8] |= 1 << (x % 8)
    if not any(data) and not character.isspace():
        raise ValueError('glyph rasterized empty')
    return bytes(data)


def build(source, font_path, expected_font_sha, text, output, weight=500, corpus=None):
    from fontTools.ttLib import TTFont
    from PIL import __version__ as pillow_version, features
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    font_path = Path(font_path).resolve(strict=True)
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('output must be a new separate directory')
    font_data = font_path.read_bytes()
    if sha(font_data) != expected_font_sha:
        raise ValueError('source font hash mismatch')
    with TTFont(font_path) as tt:
        cmap = tt.getBestCmap()
        notices = [record.toUnicode() for record in tt['name'].names if record.nameID in (0, 13, 14)]
        if not any('SIL Open Font License' in notice for notice in notices):
            raise ValueError('explicit source font license metadata required')
        required = {char for char in text if ord(char) >= 0x80}
        missing = sorted(ord(char) for char in required if ord(char) not in cmap)
        if missing:
            raise ValueError('source font lacks codepoints: ' + ','.join(f'U+{cp:04X}' for cp in missing))
        variation_axes = list(tt['fvar'].axes) if 'fvar' in tt else []
        variations = [weight if axis.axisTag == 'wght' else axis.defaultValue for axis in variation_axes]
        if any(not axis.minValue <= value <= axis.maxValue for axis, value in zip(variation_axes, variations)):
            raise ValueError('requested outline variation outside source font range')
        applied_variations = {axis.axisTag: value for axis, value in zip(variation_axes, variations)}
    originals = [(source / f'Chi{i}.dat').read_bytes() for i in (0, 1)]
    fonts = [parse(data) for data in originals]
    if any(font.advances for font in fonts):
        raise ValueError('variable native Chi advances not supported')
    mapping = plan(text, fonts)
    if not mapping:
        raise ValueError('no mapped glyphs requested')
    outputs = []
    deltas = []
    face_cache = {}
    for font_set, font in enumerate(fonts):
        modified = font
        for character, item in mapping.items():
            glyph = rasterize(character, font_path, font.height, font.pitch, variations, face_cache)
            modified = modified.replace_glyph(item['index'], glyph)
            deltas.append(dict(font_set=font_set, index=item['index'],
                               original_glyph_sha256=sha(font.glyph(item['index'])), bitmap_hex=glyph.hex()))
        outputs.append(modified.to_bytes())
    encoded = encode(text, mapping)
    if decode(encoded, mapping) != text:
        raise ValueError('native text codec roundtrip failed')
    # Validate original source bytes before publishing any output.
    if [path.read_bytes() for path in [source/'Chi0.dat', source/'Chi1.dat']] != originals:
        raise ValueError('source fonts changed during build')
    if sha(font_path.read_bytes()) != expected_font_sha:
        raise ValueError('source outline font changed during build')
    if corpus is not None and corpus[0].read_bytes() != corpus[1]:
        raise ValueError('translation corpus changed during build')
    report = dict(schema=1, kind='private_native_glyph_overlay_candidate',
                  source_font_sha256=expected_font_sha, source_font_notices=notices,
                  derived_font_name='Locale Glyph Overlay', pillow_version=pillow_version,
                  freetype_version=features.version_module('freetype2'),
                  applied_variations=applied_variations,
                  native_original_sha256=[sha(data) for data in originals],
                  native_modified_sha256=[sha(data) for data in outputs],
                  mapping=mapping, deltas=deltas, encoded_text_hex=encoded.hex(),
                  source_unchanged=True, game_started=False, in_game_verified=False)
    if corpus is not None:
        report['translation_input'] = dict(sha256=sha(corpus[1]), rows=corpus[2],
                                         ordering='stable_id_ascending', semantic_approval_not_inferred=True)
    output.mkdir(parents=True)
    for font_set, data in enumerate(outputs):
        (output/f'Chi{font_set}.dat').write_bytes(data)
    with (output/'overlay.json').open('x', encoding='utf8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=True, indent=2); stream.write('\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source', type=Path, required=True)
    p.add_argument('--font', type=Path, required=True); p.add_argument('--font-sha256', required=True)
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--text'); inputs.add_argument('--translations', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--weight', type=int, default=500)
    a = p.parse_args()
    text, corpus = translation_corpus(a.translations) if a.translations else (a.text, None)
    result = build(a.source, a.font, a.font_sha256, text, a.output, a.weight, corpus)
    print(f'FONT_OVERLAY PASS glyphs={len(result["mapping"])} sets=2 source_unchanged=true game_started=false in_game_verified=false')
