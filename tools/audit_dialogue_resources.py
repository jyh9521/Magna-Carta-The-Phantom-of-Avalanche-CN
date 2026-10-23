"""Read-only Field -> FPB -> SVD audit, with optional original-audio decoding.

No game process, game DLL entry point, sound device, or resource modification is
used. Reports contain text digests, not dialogue payloads. Opcode bindings are
separate from runtime execution; unsupported Field variants remain explicit.
"""
import argparse
import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess

from resource_field_script import parse as parse_field
from resource_fpb import parse as parse_fpb, rebuild as rebuild_fpb

MAGIC = bytes.fromhex('19931225')
PCM_RATE = 44100
DECODE_ARGUMENTS = ['-v', 'error', '-f', 'mp3', '-i', 'pipe:0', '-f',
                    's16le', '-acodec', 'pcm_s16le', '-ac', '1', '-ar',
                    str(PCM_RATE), 'pipe:1']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf8')


def parse_sound(data):
    """Read the two observed wrapper headers without guessing unknown words."""
    if len(data) < 16 or data[:4] != MAGIC:
        raise ValueError('Unsupported or truncated sound wrapper')
    if struct.unpack_from('<I', data, 8)[0] in (0, 1) and struct.unpack_from('<I', data, 12)[0] == 18:
        header_size, words_offset, variant = 56, 8, 'compact'
    elif data[4:56] == b'SoftMax(C) 2001, SED File V0.1a, Dev#4 han-kue, Park':
        header_size, words_offset, variant = 108, 60, 'legacy_signature'
    else:
        raise ValueError('Unknown sound wrapper header variant')
    if len(data) <= header_size:
        raise ValueError('Truncated sound wrapper payload')
    return dict(header_bytes=header_size, header_variant=variant,
                header_sha256=digest(data[:header_size]),
                metadata_word=struct.unpack_from('<I', data, words_offset-4)[0],
                storage_word=struct.unpack_from('<I', data, words_offset)[0],
                filter_word=struct.unpack_from('<I', data, words_offset+4)[0],
                payload_sha256=digest(data[header_size:]),
                payload_bytes=len(data)-header_size)


def decoder_identity(executable):
    path = Path(shutil.which(str(executable)) or executable).resolve(strict=True)
    result = subprocess.run([str(path), '-version'], capture_output=True, check=False)
    if result.returncode:
        raise ValueError('Audio decoder version query failed')
    return dict(path=str(path), executable_sha256=digest(path.read_bytes()),
                version_sha256=digest(result.stdout),
                version=result.stdout.decode('utf8', 'replace').splitlines()[0])


def decode_pcm(payload, executable):
    result = subprocess.run([str(executable), *DECODE_ARGUMENTS], input=payload,
                            capture_output=True, check=False)
    if result.returncode:
        raise ValueError('Original audio decode failed: ' + result.stderr.decode('utf8', 'replace'))
    if not result.stdout or len(result.stdout) % 2:
        raise ValueError('Empty or misaligned decoded PCM')
    pcm = array.array('h')
    pcm.frombytes(result.stdout)
    import sys
    if sys.byteorder != 'little':
        pcm.byteswap()
    rms = []
    for offset in range(0, len(pcm), PCM_RATE//10):
        window = pcm[offset:offset+PCM_RATE//10]
        rms.append(round(math.sqrt(sum(x*x for x in window)/len(window)), 3))
    active = [index for index, value in enumerate(rms) if value > 100]
    return dict(command=[str(executable), *DECODE_ARGUMENTS], input='complete compressed wrapper payload',
                exit_status=result.returncode, stderr=result.stderr.decode('utf8', 'replace'),
                pcm_sha256=digest(result.stdout), pcm_samples=len(pcm),
                sample_rate=PCM_RATE, channels=1, sample_format='signed_s16le',
                duration_seconds=len(pcm)/PCM_RATE,
                nonzero_samples=sum(value != 0 for value in pcm), rms_100ms=rms,
                active_rms_gt100_first_seconds=active[0]/10 if active else None,
                active_rms_gt100_last_seconds=(active[-1]+1)/10 if active else None)


def decode_cached(data, decoder, cache=None):
    header = parse_sound(data)
    if header['storage_word'] != 1:
        raise ValueError('Selected original voice is not a compressed-stream wrapper')
    key = digest(canonical(dict(schema=1, source_sha256=digest(data),
                                decoder_sha256=decoder['executable_sha256'],
                                version_sha256=decoder['version_sha256'], args=DECODE_ARGUMENTS)))
    path = cache/(key+'.json') if cache else None
    if path and path.exists():
        entry = json.loads(path.read_text('utf8'))
        if (entry.get('schema') != 1 or entry.get('key') != key or
                entry.get('result_sha256') != digest(canonical(entry.get('result')))):
            raise ValueError('Audio decode cache identity or content mismatch')
        result = entry['result']
        if (result.get('exit_status') != 0 or result.get('sample_rate') != PCM_RATE or
                result.get('pcm_samples', 0) <= 0):
            raise ValueError('Invalid cached audio decode result')
        return dict(result, cache_hit=True, cache_key=key)
    result = decode_pcm(data[header['header_bytes']:], decoder['path'])
    result['payload_offset'] = header['header_bytes']
    if path:
        cache.mkdir(parents=True, exist_ok=True)
        entry = dict(schema=1, key=key, result_sha256=digest(canonical(result)), result=result)
        path.write_text(json.dumps(entry, indent=2)+'\n', encoding='utf8')
        if json.loads(path.read_text('utf8')) != entry:
            raise ValueError('Audio cache write verification failed')
    return dict(result, cache_hit=False, cache_key=key)


def outside_source(path, source):
    if path and path.resolve().is_relative_to(source):
        raise ValueError('Report/cache must remain outside the resource root')


def audit(source, *, decode='none', selected_count=12, cache=None, ffmpeg='ffmpeg'):
    source = Path(source).resolve(strict=True)
    if decode not in ('none', 'selected') or not 1 <= selected_count <= 100:
        raise ValueError('Invalid decode selection')
    cache = Path(cache).resolve() if cache else None
    outside_source(cache, source)
    snapshots = {}

    def read(path):
        data = path.read_bytes()
        previous = snapshots.setdefault(path, digest(data))
        if previous != digest(data):
            raise ValueError('Resource changed during audit: ' + path.name)
        return data

    fields = sorted((source/'Field').glob('*.fld'))
    if not fields:
        raise ValueError('No Field resources found')
    counts = Counter()
    rows, rejected = [], []
    for path in fields:
        data = read(path)
        try:
            field = parse_field(data)
        except ValueError as error:
            rejected.append(dict(field=path.name, source_sha256=digest(data), reason=str(error)))
            continue
        counts['accepted_fields'] += 1
        playbook = field['playbook_id']
        fp = source/'Fpb'/f'{playbook:04d}.fpb'
        fp_data = read(fp) if fp.exists() else b''
        records = parse_fpb(fp_data) if fp_data else []
        if fp_data and rebuild_fpb(records) != fp_data:
            raise ValueError('FPB roundtrip mismatch')
        by_tag = {}
        for ordinal, (tag, raw) in enumerate(records):
            if tag in by_tag:
                raise ValueError('Duplicate FPB tag prevents unambiguous script binding')
            by_tag[tag] = (ordinal, raw)
        for event in field['events']:
            for action_index, command in enumerate(event['actions']):
                if command['opcode'] != 700:
                    continue
                parameters = command['parameters']
                tag, voice_id = parameters[6:8]
                counts['opcode700'] += 1
                if tag not in by_tag:
                    raise ValueError(f'Missing dialogue tag: {path.name}/{playbook}:{tag}')
                ordinal, raw = by_tag[tag]
                counts['text_resolved'] += 1
                voice = source/'SVD'/f'{voice_id:04d}.SVD'
                if voice_id == -1:
                    counts['voice_none'] += 1
                elif voice_id < 0 or not voice.is_file():
                    raise ValueError(f'Missing original voice: {path.name}/{voice_id}')
                else:
                    counts['voice_resolved'] += 1
                rows.append(dict(field=path.name, field_sha256=digest(data),
                    playbook=playbook, fpb_sha256=digest(fp_data), event=event['index'],
                    action=action_index, offset=command['offset'], parameters=parameters,
                    text_tag=tag, text_ordinal=ordinal, text_bytes=len(raw), text_sha256=digest(raw),
                    voice_id=voice_id, script_parameter8=parameters[8],
                    next_commands=event['actions'][action_index+1:action_index+5],
                    event_last=event['actions'][-1]))
    if not rows:
        raise ValueError('No supported dialogue commands found')
    selected = sorted(rows, key=lambda row: (-row['text_bytes'], row['field'], row['event'], row['action']))[:selected_count]
    decoder = decoder_identity(ffmpeg) if decode == 'selected' else None
    for row in selected:
        if row['voice_id'] == -1:
            continue
        path = source/'SVD'/f"{row['voice_id']:04d}.SVD"
        data = read(path)
        row['audio'] = dict(path=path.relative_to(source).as_posix(),
                            source_sha256=digest(data), **parse_sound(data))
        if decoder:
            row['audio']['decode'] = decode_cached(data, decoder, cache)
    for path, expected in snapshots.items():
        if digest(path.read_bytes()) != expected:
            raise ValueError('Resource changed during audit: ' + path.name)
    return dict(schema=1, counts=dict(counts), binding_count=len(rows), bindings=rows,
                rejected_fields=rejected, selected=selected, decoder=decoder,
                sources=[dict(path=path.relative_to(source).as_posix(), sha256=value)
                         for path, value in sorted(snapshots.items())],
                game_started=False, game_dll_loaded=False, audio_played=False, source_modified=False,
                limitations=['Resource structure and binding are not game execution or rendered acceptance.',
                    'Unsupported Field variants are listed, not diagnosed as damaged.',
                    'PCM decoding is optional and does not execute the game or use a sound device.',
                    'RMS windows distinguish activity from silence, not speech recognition.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--decode', choices=['none', 'selected'], default='none')
    parser.add_argument('--selected-count', type=int, default=12)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    try:
        outside_source(args.report, args.source.resolve(strict=True))
        if args.report.exists():
            raise ValueError('Report must be a new file')
        result = audit(args.source, decode=args.decode, selected_count=args.selected_count,
                       cache=args.cache, ffmpeg=args.ffmpeg)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf8') as report:
            report.write(json.dumps(result, indent=2)+'\n')
        if json.loads(args.report.read_text('utf8')) != result:
            raise ValueError('Report write verification failed')
    except (ValueError, OSError) as error:
        parser.error(str(error))
    counts = result['counts']
    decoded = [row['audio']['decode'] for row in result['selected'] if 'decode' in row.get('audio', {})]
    print(f"RESOURCE_VOICE_AUDIT PASS fields={counts['accepted_fields']} opcode700={counts['opcode700']} "
          f"text_resolved={counts['text_resolved']} voice_resolved={counts.get('voice_resolved', 0)} "
          f"silent={counts.get('voice_none', 0)} decoded={len(decoded)} "
          f"cache_hits={sum(row['cache_hit'] for row in decoded)} "
          'game_started=false source_modified=false')


if __name__ == '__main__':
    main()
