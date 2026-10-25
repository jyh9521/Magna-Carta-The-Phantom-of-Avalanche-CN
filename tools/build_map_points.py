"""Build source-locked, per-Field candidate exit markers without starting the game.

Only condition 304 (an actor inside one region) paired with action 4 or 5
(a Field transition) is interpreted. Unknown conditions and event repeat limits
are not evaluated. The runtime must also match the current player's actor ID.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from resource_field import ENGINE_SHA256S, parse as parse_prefix
from resource_field_script import parse_script_tail

HEADER = struct.Struct('<4sIII')
ROW = struct.Struct('<iiiiiIfff')
MAX_POINTS = 64
FLAG_UNEVALUATED = 1
FLAG_LIMITED = 2


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_field(data):
    prefix = parse_prefix(data)
    script = parse_script_tail(data, prefix['parsed_bytes'])
    if not -1 <= prefix['map_resource_id'] <= 9999:
        raise ValueError('Field map ID is outside -1..9999')
    regions = {row['id']: row for row in prefix['region_volumes']}
    if len(regions) != len(prefix['region_volumes']):
        raise ValueError('Duplicate Field region ID')
    return prefix, script, regions


def extract_points(parsed, target_maps):
    """Extract potential exits, never claiming that their conditions are active."""
    _, script, regions = parsed
    points, skipped = [], []
    for event in script['events']:
        transitions = [(index, action) for index, action in enumerate(event['actions'])
                       if action['opcode'] in (4, 5)]
        if not transitions:
            continue
        spatial = [condition for condition in event['conditions'] if condition['opcode'] == 304]

        def skip(reason):
            skipped.append({'event_index': event['index'], 'reason': reason})

        if len(spatial) != 1:
            skip('expected exactly one actor-region condition 304')
            continue
        condition = spatial[0]
        actor, region_id = condition['parameters'][:2]
        if not 10000 <= actor <= 19999:
            skip('condition 304 does not select a supported actor')
            continue
        if region_id < 0 or region_id not in regions:
            skip('condition 304 region is missing or unsupported')
            continue
        region = regions[region_id]
        flags = FLAG_UNEVALUATED if len(event['conditions']) > 1 or len(transitions) > 1 else 0
        flags |= FLAG_LIMITED if event['flag'] > 0 else 0
        for action_index, action in transitions:
            target = action['parameters'][0]
            if not 0 <= target <= 9999:
                skip(f'transition action {action_index} target is outside 0..9999')
                continue
            x, y, z = region['center']
            points.append({'event_index': event['index'], 'region_id': region_id,
                           'target_field': target, 'target_map': target_maps.get(target, -1),
                           'trigger_actor': actor - 10000, 'flags': flags,
                           'x': x, 'y': y, 'z': z,
                           'action_index': action_index, 'action_opcode': action['opcode'],
                           'condition_offset': condition['offset'], 'action_offset': action['offset'],
                           'region_min': [min(p[i] for p in region['corners']) for i in range(3)],
                           'region_max': [max(p[i] for p in region['corners']) for i in range(3)]})
    if len(points) > MAX_POINTS:
        raise ValueError('Field candidate exit count exceeds 64; no markers emitted')
    return points, skipped


def encode_points(field_id, map_id, points):
    if not 0 <= field_id <= 9999 or not -1 <= map_id <= 9999 or len(points) > MAX_POINTS:
        raise ValueError('Invalid MCP1 identity or count')
    body = b''.join(ROW.pack(*(point[key] for key in
                              ('event_index', 'region_id', 'target_field', 'target_map',
                               'trigger_actor', 'flags', 'x', 'y', 'z'))) for point in points)
    return HEADER.pack(b'MCP1', field_id, map_id & 0xffffffff, len(points)) + body


def build(source, engine, output):
    source, engine, output = Path(source).resolve(strict=True), Path(engine).resolve(strict=True), Path(output).resolve()
    if not source.is_dir() or not engine.is_file():
        raise ValueError('Expected a Field directory and engine file')
    if output.exists() or output.is_relative_to(source) or output == engine:
        raise ValueError('Output must be new and outside source resources')
    engine_sha = digest(engine.read_bytes())
    if engine_sha not in ENGINE_SHA256S:
        raise ValueError('Unsupported Field loader image SHA256')
    sources, parsed, accepted, rejected, payloads = {}, {}, [], [], {}
    paths = sorted(source.glob('*.fld'))
    if not paths:
        raise ValueError('No Field resources found')
    for path in paths:
        if not re.fullmatch(r'[0-9]{4}\.fld', path.name, re.IGNORECASE):
            raise ValueError(f'Unsupported Field filename: {path.name}')
        field_id = int(path.stem)
        data = path.read_bytes()
        item = {'field_id': field_id, 'file': path.name, 'source_sha256': digest(data)}
        sources[path] = item['source_sha256']
        try:
            parsed[field_id] = (item, parse_field(data))
        except ValueError as error:
            rejected.append({**item, 'reason': str(error)})
    target_maps = {field_id: value[1][0]['map_resource_id'] for field_id, value in parsed.items()}
    for field_id, (item, value) in parsed.items():
        try:
            points, skipped = extract_points(value, target_maps)
            map_id = value[0]['map_resource_id']
            payload = encode_points(field_id, map_id, points)
            payloads[f'{field_id:04d}.poi'] = payload
            accepted.append({**item, 'map_id': map_id, 'poi_sha256': digest(payload),
                             'points': points, 'skipped_events': skipped})
        except ValueError as error:
            rejected.append({**item, 'reason': str(error)})

    def verify_sources():
        if sorted(source.glob('*.fld')) != paths or any(digest(path.read_bytes()) != sha for path, sha in sources.items()):
            raise ValueError('Field sources changed during points build')
        if digest(engine.read_bytes()) != engine_sha:
            raise ValueError('Field loader image changed during points build')

    verify_sources()
    manifest = {'schema': 1, 'format': 'MCP1', 'header_bytes': HEADER.size, 'row_bytes': ROW.size,
                'source_engine_sha256': engine_sha, 'accepted': accepted, 'rejected': rejected,
                'source_unchanged': True, 'game_started': False,
                'current_passability_evaluated': False,
                'marker_count': sum(len(row['points']) for row in accepted)}
    output.mkdir(parents=True)
    for name, payload in payloads.items():
        with (output / name).open('xb') as stream:
            stream.write(payload)
    verify_sources()
    with (output / 'manifest.json').open('x', encoding='utf8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(args.source, args.engine, args.output)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"MAP_POINTS PASS accepted={len(result['accepted'])} rejected={len(result['rejected'])} "
          f"markers={result['marker_count']} source_unchanged=true passability_evaluated=false game_started=false")


if __name__ == '__main__':
    main()
