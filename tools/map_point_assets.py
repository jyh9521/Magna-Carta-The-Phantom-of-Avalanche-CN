"""Validate the small, source-bound MCP1 asset set shared by map deployments."""
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from resource_field import ENGINE_SHA256S

HEADER = struct.Struct('<4sIII')
ROW = struct.Struct('<iiiiiIfff')
FIELDS = ('event_index', 'region_id', 'target_field', 'target_map', 'trigger_actor', 'flags', 'x', 'y', 'z')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def point_assets(directory):
    """Return manifest-listed paths relative to the runtime root; never execute assets."""
    directory = Path(directory)
    path = directory/'manifest.json'
    if not path.exists():
        if directory.exists():
            raise ValueError('Map points directory has no manifest')
        return {}
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (type(manifest.get('schema')) is not int or manifest['schema'] != 1
            or manifest.get('format') != 'MCP1' or manifest.get('header_bytes') != HEADER.size
            or manifest.get('row_bytes') != ROW.size
            or manifest.get('source_engine_sha256') not in ENGINE_SHA256S
            or manifest.get('current_passability_evaluated') is not False
            or not isinstance(manifest.get('accepted'), list) or not manifest['accepted']):
        raise ValueError('Unsupported map point manifest')
    files = {'maps/points/manifest.json': sha(manifest_bytes)}
    seen = set()
    total = 0
    for record in manifest['accepted']:
        field, map_id = record.get('field_id'), record.get('map_id')
        if (type(field) is not int or not 0 <= field <= 9999 or field in seen
                or type(map_id) is not int or not -1 <= map_id <= 9999
                or record.get('file') != f'{field:04d}.fld'
                or not valid_sha(record.get('source_sha256'))
                or not valid_sha(record.get('poi_sha256'))):
            raise ValueError('Invalid map point source identity')
        seen.add(field)
        points = record.get('points')
        if not isinstance(points, list) or len(points) > 64:
            raise ValueError('Invalid map point count')
        expected = bytearray(HEADER.pack(b'MCP1', field, map_id & 0xffffffff, len(points)))
        for p in points:
            if not isinstance(p, dict) or any(key not in p for key in FIELDS):
                raise ValueError('Missing map point fields')
            if any(type(p[key]) is not int for key in FIELDS[:6]):
                raise ValueError('Invalid map point integer')
            if (p['event_index'] < 0 or p['region_id'] < 0
                    or not 0 <= p['target_field'] <= 9999 or not -1 <= p['target_map'] <= 9999
                    or not 0 <= p['trigger_actor'] <= 9999 or not 0 <= p['flags'] <= 3):
                raise ValueError('Invalid map point field range')
            if any(type(p[key]) not in (float, int) or not math.isfinite(p[key]) or abs(p[key]) >= 1e8
                   for key in FIELDS[6:]):
                raise ValueError('Invalid map point coordinates')
            try:
                expected.extend(ROW.pack(*(p[key] for key in FIELDS)))
            except struct.error as error:
                raise ValueError('Invalid map point representation') from error
        name = f'{field:04d}.poi'
        data = (directory/name).read_bytes()
        if data != expected or sha(data) != record['poi_sha256']:
            raise ValueError('Map point asset drift: ' + name)
        files['maps/points/'+name] = record['poi_sha256']
        total += len(points)
    if type(manifest.get('marker_count')) is not int or manifest['marker_count'] != total:
        raise ValueError('Map point total mismatch')
    expected_names = {Path(name).name for name in files}
    if {p.name for p in directory.iterdir()} != expected_names:
        raise ValueError('Unlisted map point assets')
    return files
