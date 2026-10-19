"""Offline outline-raster cache prototype. Does not install hooks or modify a runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from build_font_coverage import coverage, raster_layout


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_inputs(native_header, mapping_header):
    raw = native_header.read_bytes()
    text = raw.decode('ascii')
    match = re.search(r'coveragePairs\[\]\s*=\s*\{([^}]+)\}', text)
    if not match:
        raise ValueError('Missing native pair table')
    pairs = [int(p, 16) for p in match[1].split(',') if p.strip()]
    if not 0 < len(pairs) <= 4096 or pairs != sorted(set(pairs)):
        raise ValueError('Invalid pair table')
    mapping_raw = mapping_header.read_bytes()
    rows = re.findall(r'\{0x([0-9a-f]+),L"\\u([0-9a-f]{4})"\}', mapping_raw.decode('ascii'))
    mapping = {int(p, 16): chr(int(c, 16)) for p, c in rows}
    if len(mapping) != len(rows) or set(mapping) != set(pairs) or len(set(mapping.values())) != len(pairs):
        raise ValueError('Native and Unicode mappings differ')
    planes = []
    for i, height in enumerate((14, 22)):
        m = re.search(r'coveragePlane' + str(i) + r'\[\]\s*=\s*\{([^}]+)\}', text)
        if not m:
            raise ValueError('Missing native coverage')
        plane = bytes(int(v) for v in m[1].split(',') if v.strip())
        if len(plane) != len(pairs) * height * height:
            raise ValueError('Native coverage length mismatch')
        planes.append(plane)
    return pairs, mapping, planes, raw, mapping_raw


def scaled_layout(font, logical_height, scale, chars, layout, cache, variations):
    """Keep the original point-size ratio and one shared baseline, not per-glyph fitting."""
    from PIL import ImageFont
    size = layout['size'] * scale
    key = (size, variations)
    if key not in cache:
        cache[key] = ImageFont.truetype(str(font), size)
        if variations:
            cache[key].set_variation_by_axes(list(variations))
    boxes = [cache[key].getbbox(c, anchor='ls') for c in chars]
    top = min(b[1] for b in boxes)
    bottom = max(b[3] for b in boxes)
    edge = logical_height * scale
    if bottom - top > edge - scale or max(b[2] - b[0] for b in boxes) > edge:
        raise ValueError('Scaled outline exceeds preserved cell; no per-glyph resizing')
    baseline = max(-top, min(layout['baseline'] * scale, edge - scale - bottom))
    return dict(size=size, baseline=baseline, source_top=top, source_bottom=bottom, anchor='ls')


def cache_bytes(height, scale, pairs, plane):
    if height not in (14, 22) or type(scale) is not int or not 1 <= scale <= 4:
        raise ValueError('Unsupported logical height or scale')
    if not 0 < len(pairs) <= 4096 or pairs != sorted(set(pairs)):
        raise ValueError('Invalid cache pairs')
    if len(plane) != len(pairs) * (height * scale) ** 2:
        raise ValueError('Invalid cache plane')
    return struct.pack('<4sIIII', b'SGC1', 1, height, scale, len(pairs)) + struct.pack('<' + 'H' * len(pairs), *pairs) + plane


def scaled_tiles(width, height, scale):
    """Native 256-logical-pixel chunks; never confuse logical width with HD texels."""
    if any(type(v) is not int or v < 1 for v in (width, height, scale)) or scale > 4 or width > 8192 or height > 64:
        raise ValueError('Invalid tile geometry')
    return [dict(logical_x=x, logical_y=0, logical_width=min(256, width-x), logical_height=height,
                 physical_x=x*scale, physical_y=0, physical_width=min(256, width-x)*scale, physical_height=height*scale)
            for x in range(0, width, 256)]


def build(font, source_lock, native_header, mapping_header, sample_path, output, scale=4, license_path=None):
    font = Path(font).resolve(strict=True)
    source_lock = Path(source_lock).resolve(strict=True)
    native_header = Path(native_header).resolve(strict=True)
    mapping_header = Path(mapping_header).resolve(strict=True)
    sample_path = Path(sample_path).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() or type(scale) is not int or not 2 <= scale <= 4:
        raise ValueError('New output and scale 2..4 required')
    snapshots = {p: p.read_bytes() for p in (font, source_lock, native_header, mapping_header, sample_path)}
    lock = json.loads(snapshots[source_lock])
    if digest(snapshots[font]) != lock['sha256']:
        raise ValueError('Outline hash mismatch')
    if license_path is None:
        raise ValueError('Explicit font license required')
    license_path=Path(license_path).resolve(strict=True)
    snapshots[license_path]=license_path.read_bytes()
    if digest(snapshots[license_path]) != lock['license_sha256']:
        raise ValueError('Font license hash mismatch')
    from fontTools.ttLib import TTFont
    from PIL import __version__ as pillow_version, features
    with TTFont(font) as outline:
        notices = sorted({r.toUnicode() for r in outline['name'].names if r.nameID in (0, 13, 14)})
        if not any('SIL Open Font License' in n for n in notices):
            raise ValueError('Explicit outline license required')
        cmap = outline.getBestCmap()
        axes = outline['fvar'].axes if 'fvar' in outline else []
        variations = tuple(500 if a.axisTag == 'wght' else a.defaultValue for a in axes)
    pairs, mapping, planes, _, _ = read_inputs(native_header, mapping_header)
    chars = [mapping[p] for p in pairs]
    if any(ord(c) not in cmap for c in chars):
        raise ValueError('Outline missing mapped glyphs')
    sample = json.loads(snapshots[sample_path])
    samples = sample['lines']
    if not samples or any(not isinstance(s, str) or not s or len(s) > 64 for s in samples):
        raise ValueError('Invalid sample rows')
    reverse = {c: p for p, c in mapping.items()}
    if any(c not in reverse for s in samples for c in s):
        raise ValueError('Sample contains a glyph outside the active mapping')
    cache = {}
    outputs = {'FONT-LICENSE.txt':snapshots[license_path]}
    layouts = []
    metrics = []
    for i, height in enumerate((14, 22)):
        low_layout = raster_layout(font, height, chars, cache, variations)
        rebuilt = b''.join(coverage(c, font, height, cache=cache, variations=variations, layout=low_layout) for c in chars)
        if rebuilt != planes[i]:
            raise ValueError('Outline raster differs from the active native baseline')
        high_layout = scaled_layout(font, height, scale, chars, low_layout, cache, variations)
        high = b''.join(coverage(c, font, height * scale, cache=cache, variations=variations, layout=high_layout) for c in chars)
        # Reserve the complete last logical row for native foreground offset y=1.
        stride = height * scale
        for g in range(len(pairs)):
            cell = high[g * stride * stride:(g + 1) * stride * stride]
            if any(cell[-stride * scale:]):
                raise ValueError('Scaled glyph consumes reserved foreground rows')
        for kind, factor, plane in [('baseline', 1, rebuilt), ('candidate', scale, high)]:
            outputs[f'{kind}-{height}.sgc'] = cache_bytes(height, factor, pairs, plane)
        layouts.append(dict(logical_height=height, baseline=low_layout, candidate=high_layout))
        metrics.append(dict(logical_height=height, baseline_advance=height, candidate_advance=height,
                            candidate_cell_pixels=height * scale, baseline_plane_sha256=digest(rebuilt),
                            candidate_plane_sha256=digest(high)))
    tile_reports = []
    for i, line in enumerate(samples):
        outputs[f'line-{i}.seq'] = struct.pack('<' + 'H' * len(line), *(reverse[c] for c in line))
        tile_reports.append(dict(row=i, heights={str(h):scaled_tiles(len(line)*h,h,scale) for h in (14,22)}))
    if any(p.read_bytes() != raw for p, raw in snapshots.items()):
        raise ValueError('Build input drift')
    output.mkdir(parents=True)
    for name, raw in outputs.items():
        (output / name).write_bytes(raw)
    report = dict(schema=1, derived_font_name='Locale Scaled Glyph Coverage', scale=scale, glyphs=len(pairs), axis_values=list(variations),
                  source_font_sha256=lock['sha256'], source_font_notices=notices, weight=500,
                  inputs={str(p): digest(raw) for p, raw in snapshots.items()},
                  files={n: digest(raw) for n, raw in outputs.items()}, layouts=layouts, metrics=metrics,
                  sample_lines=samples, tiles=tile_reports, baseline_matches_active_coverage=True, logical_metrics_unchanged=True,
                  pixel_source='rerasterized outline, not bitmap enlargement',
                  pillow=pillow_version, freetype=features.version('freetype2'),
                  game_started=False, runtime_installed=False, gpu_upload_verified=False)
    (output / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return report


def rollback(manifest, target, height):
    """Restore a separate owned cache copy only; never modify runtime or engine data."""
    manifest = Path(manifest).resolve(strict=True)
    target = Path(target)
    if target.is_symlink() or not target.is_file():
        raise ValueError('Ordinary existing cache copy required')
    target = target.resolve(strict=True)
    root = manifest.parent
    if target.is_relative_to(root) or height not in (14, 22):
        raise ValueError('Separate owned cache copy required')
    report = json.loads(manifest.read_bytes())
    before = (root / f'baseline-{height}.sgc').read_bytes()
    if report.get('schema') != 1 or digest(before) != report['files'][f'baseline-{height}.sgc']:
        raise ValueError('Baseline cache drift')
    if digest(target.read_bytes()) != report['files'][f'candidate-{height}.sgc']:
        raise ValueError('Candidate cache drift')
    import os
    import tempfile
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name+'.restore-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(before)
            stream.flush()
            os.fsync(stream.fileno())
        if digest(target.read_bytes()) != report['files'][f'candidate-{height}.sgc']:
            raise ValueError('Candidate changed during rollback')
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink()
    if target.read_bytes() != before:
        raise ValueError('Cache restoration mismatch')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    a = sub.add_parser('build')
    for n in ('font', 'source-lock', 'native-header', 'mapping-header', 'sample', 'output'):
        a.add_argument('--' + n, type=Path, required=True)
    a.add_argument('--scale', type=int, default=4)
    a.add_argument('--font-license', type=Path, required=True)
    a = sub.add_parser('rollback')
    a.add_argument('--manifest', type=Path, required=True)
    a.add_argument('--target', type=Path, required=True)
    a.add_argument('--height', type=int, choices=[14, 22], required=True)
    a = p.parse_args()
    if a.action == 'build':
        r = build(a.font, a.source_lock, a.native_header, a.mapping_header, a.sample, a.output, a.scale, a.font_license)
        print(f'SCALED_FONT_BUILD PASS glyphs={r["glyphs"]} scale={r["scale"]} active_baseline=exact metrics=unchanged runtime_installed=false')
    else:
        rollback(a.manifest, a.target, a.height)
        print('SCALED_FONT_ROLLBACK PASS owned_cache=exact game_files_changed=false')
