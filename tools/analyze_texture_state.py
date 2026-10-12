"""Inspect the version-locked texture-binding layout in an existing x86 dump."""
import argparse
import json
from pathlib import Path
import struct
from inspect_minidump import Dump


def inspect_binding(dump, context):
    location = context['fault_location']
    version = next((m for m in dump.modules if m['name'].lower() == 'd3dim700.dll'), None)
    if (location.get('module', '').lower() != 'd3dim700.dll' or location.get('rva') != '0x71b8'
            or not version or version['timestamp'] != 0xb546c162 or version['size'] != 0x67000):
        raise ValueError('Unsupported native binding layout')
    frames = context['frame_chain']
    if len(frames) < 2 or frames[0]['return_site'].get('module') != 'AsrD3DDrv.dll' or frames[0]['return_site'].get('rva') != '0x7bb6':
        raise ValueError('Expected locked driver binding caller')
    word = lambda address: struct.unpack('<I', dump.read(address, 4))[0]
    driver_frame = int(frames[1]['frame_pointer'], 16)
    driver = word(driver_frame - 4)
    device = word(driver + 0x2c)
    stage = word(driver + 0x108ef0)
    texture_id = word(driver_frame + 12)
    if stage >= 8 or texture_id >= 4096:
        raise ValueError('Texture index out of supported range')
    new_surface = word(driver + 0x100ea0 + texture_id * 4)
    previous = word(device + 0x2938 + stage * 4)
    if not new_surface or not previous:
        raise ValueError('Expected both old binding and replacement surface')
    old_words = struct.unpack('<13I', dump.read(previous, 52))
    new_words = struct.unpack('<4I', dump.read(new_surface, 16))
    return {'driver': hex(driver), 'device': hex(device), 'stage': stage, 'replacement_id': texture_id,
            'replacement_surface': hex(new_surface), 'replacement_vtable': dump.location(new_words[0]),
            'old_native_binding': hex(previous), 'old_first_words': [hex(v) for v in old_words[:4]],
            'old_internal_reference_2c': hex(old_words[11]), 'old_internal_reference_30': hex(old_words[12]),
            'finding': 'old binding lacks required internal reference pointers' if not old_words[11] and not old_words[12] else 'inspect references',
            'release_history': 'not established from snapshot alone'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dump', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.resolve() == args.dump.resolve():
        parser.error('Use a new report path')
    dump = Dump(args.dump.read_bytes())
    contexts = dump.inspect()['earlier_contexts']
    results = [inspect_binding(dump, context) for context in contexts]
    if not results:
        raise ValueError('No preserved exception context')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'TEXTURE_STATE_INSPECT_PASS contexts={len(results)} game_started=false')
