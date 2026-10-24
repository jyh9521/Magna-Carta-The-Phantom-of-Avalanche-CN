"""Read-only diagnostic summary. Failure assertions do not predict a repaired trace."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib


def analyze(data, save=None):
    fields, capacities, occupancy = Counter(), Counter(), Counter()
    failures, transitions = [], []
    audio = valid = contacts = 0
    ready = False
    lines = data.decode('utf-8', errors='replace').splitlines()
    for line, text in enumerate(lines, 1):
        if 'CONTACT_AUDIO_READY ' in text:
            ready = True
        if 'CONTACT_AUDIO_SOUND ' not in text and 'CONTACT_AUDIO_CONTACT ' not in text:
            continue
        row = dict(re.findall(r'(\w+)=([^ ]+)', text))
        if 'CONTACT_AUDIO_SOUND ' in text:
            audio += 1
            if row.get('snapshot_valid') != '1':
                continue
            try:
                state, channel, busy, cap = [int(row[k]) for k in
                    ('state_after', 'channel_after', 'slots_busy', 'slots_capacity')]
            except (KeyError, ValueError):
                continue
            valid += 1
            capacities[cap] += 1
            occupancy[busy] += 1
            if state == 0 and channel == -1:
                failures.append(dict(line=line, slots_busy=busy, slots_capacity=cap,
                    pool_full=cap > 0 and busy == cap))
        elif row.get('snapshot_valid') == '1' and 'field' in row:
            contacts += 1
            fields[row['field']] += 1
            if not transitions or transitions[-1]['field'] != row['field']:
                transitions.append(dict(field=row['field'], map=row.get('map'),
                    first_line=line, last_line=line))
            transitions[-1]['last_line'] = line
    result = dict(schema=1, source_sha256=hashlib.sha256(data).hexdigest(),
        lines=len(lines), observer_ready=ready, sound_starts=audio, valid_sound_starts=valid,
        allocation_failures=len(failures), full_pool_failures=sum(f['pool_full'] for f in failures),
        capacities=dict(capacities), occupancy=dict(occupancy), first_failures=failures[:8],
        contacts=contacts, fields=dict(fields), transitions=transitions,
        rendered_picture_observed=False, gameplay_fix_verified=False)
    if save is not None:
        if len(save) < 30:
            raise ValueError('Truncated save header/checksum')
        version, = struct.unpack_from('<I', save)
        if version != 4:
            raise ValueError('Unsupported save version')
        stored, = struct.unpack_from('<I', save, len(save)-4)
        computed = zlib.crc32(save[:-4])
        result['save'] = dict(sha256=hashlib.sha256(save).hexdigest(), size=len(save),
            version=version, field_id=struct.unpack_from('<I', save, 22)[0],
            stored_crc32=f'{stored:08x}', computed_crc32=f'{computed:08x}',
            checksum_valid=stored == computed, full_structure_verified=False)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--save', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--assert-no-audio-failures', action='store_true')
    args = p.parse_args()
    data = args.log.read_bytes()
    save = args.save.read_bytes() if args.save else None
    report = analyze(data, save)
    if args.output:
        if args.output.resolve() in {args.log.resolve(), args.save.resolve() if args.save else None}:
            raise ValueError('Output conflicts with input')
        with args.output.open('x', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
            f.write('\n')
    if args.log.read_bytes() != data or (args.save and args.save.read_bytes() != save):
        raise ValueError('Input changed during inspection')
    ok = report['observer_ready'] and report['valid_sound_starts'] > 0
    status = 'FAIL' if not ok or (args.assert_no_audio_failures and report['allocation_failures']) else 'PASS'
    print(f"CONTACT_AUDIO_ANALYSIS {status} starts={report['sound_starts']} failures={report['allocation_failures']} full_pool={report['full_pool_failures']} source_unchanged=true")
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
