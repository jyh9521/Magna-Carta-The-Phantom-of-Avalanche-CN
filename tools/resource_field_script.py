"""Read the bounded native FLD event tail; preserve unknown opcode parameters.

Layout corroborated against the native loader at RVA 0x4ab93: signed event
count, then nonnegative flag, counted conditions and counted actions per event.
Each command contains fifteen signed little-endian DWORDs (60 bytes). Parsing
requires exact EOF. This structural reader does not prove opcode semantics,
navigation, collision behavior, or runtime event activation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from resource_field import parse as parse_static_prefix

MAX_EVENTS = 4096
MAX_COMMANDS = 65536
COMMAND_SIZE = 60


def parse_script_tail(data, offset, *, max_events=MAX_EVENTS, max_commands=MAX_COMMANDS):
    """Parse at an already validated static-prefix end, without altering data."""
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= len(data):
        raise ValueError('Invalid Field script offset')
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0
           for n in (max_events, max_commands)):
        raise ValueError('Invalid Field script limit')
    pos, total_commands = offset, 0

    def integer():
        nonlocal pos
        if pos + 4 > len(data):
            raise ValueError(f'Truncated Field script DWORD at {pos}')
        value = struct.unpack_from('<i', data, pos)[0]
        pos += 4
        return value

    def commands():
        nonlocal pos, total_commands
        count = integer()
        if count < 0 or count > max_commands - total_commands:
            raise ValueError('Field script command count exceeds limit')
        if count > (len(data) - pos) // COMMAND_SIZE:
            raise ValueError(f'Truncated Field script commands at {pos}')
        total_commands += count
        rows = []
        for _ in range(count):
            values = struct.unpack_from('<15i', data, pos)
            rows.append({'offset': pos, 'opcode': values[0], 'parameters': list(values[1:])})
            pos += COMMAND_SIZE
        return rows

    count = integer()
    if count < 0 or count > max_events:
        raise ValueError('Field script event count exceeds limit')
    if count > (len(data) - pos) // 12:
        raise ValueError('Truncated Field script event headers')
    events = []
    for index in range(count):
        start = pos
        flag = integer()
        if flag < 0:
            raise ValueError(f'Negative Field script flag at {start}')
        conditions = commands()
        actions = commands()
        events.append({'index': index, 'offset': start, 'flag': flag,
                       'conditions': conditions, 'actions': actions})
    if pos != len(data):
        raise ValueError(f'Unexpected Field script trailing bytes: {len(data) - pos}')
    return {'schema': 1, 'format': 'native_field_event_tail', 'offset': offset,
            'consumed': pos - offset, 'command_count': total_commands,
            'events': events, 'exact_eof': True, 'opcode_semantics_verified': False}


def parse(data):
    """Validate the existing static prefix before accepting the event tail."""
    prefix = parse_static_prefix(data)
    result = parse_script_tail(data, prefix['parsed_bytes'])
    result.update(source_sha256=hashlib.sha256(data).hexdigest(), size=len(data),
                  map_resource_id=prefix['map_resource_id'], playbook_id=prefix['playbook_id'])
    return result


def inspect(source):
    """Return a compact read-only report, not original resource payloads."""
    before = source.read_bytes()
    result = parse(before)
    events = []
    for event in result['events']:
        row = {key: event[key] for key in ('index', 'offset', 'flag')}
        for key in ('conditions', 'actions'):
            row[key] = [{'offset': c['offset'], 'opcode': c['opcode']} for c in event[key]]
        events.append(row)
    result['events'] = events
    if hashlib.sha256(source.read_bytes()).hexdigest() != result['source_sha256']:
        raise ValueError('Field source changed during script inspection')
    result.update(source_unchanged=True, parameters_exported=False, game_started=False,
                  collision_verified=False, navigation_verified=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    try:
        source = args.source.resolve(strict=True)
        report = args.report.resolve()
        if not source.is_file() or report.exists() or report.is_relative_to(source.parent):
            parser.error('Report must be new and outside the source directory')
        result = inspect(source)
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open('x', encoding='utf8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"FIELD_SCRIPT_INSPECT PASS events={len(result['events'])} "
          f"commands={result['command_count']} exact_eof=true source_unchanged=true game_started=false")


if __name__ == '__main__':
    main()
