"""Source-locked roster inventory and common numeric-popup sink audit.

This is not a replay of every character's skill scripts or a rendered battle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from replay_damage_render_chain import DamageReplay, BASE, require
from replay_native_combo_scoring import ABI_SHA, resource_rows


def audit(data):
    data = Path(data)
    q = DamageReplay(data)
    # Read source-bound native save-switch targets rather than an independently
    # maintained list of character names or party composition.
    targets = struct.unpack('<8I', q.cpu.mem_read(BASE + 0xb37cd, 32))
    roster = []
    for address in targets:
        prefix = bytes(q.cpu.mem_read(address, 10))
        require(prefix[0] == 0x6a and prefix[2:5] == b'\x8b\x4d\xf0'
                and prefix[5] == 0xe8, 'Native roster switch shape')
        require(address + 10 + struct.unpack_from('<i', prefix, 6)[0]
                == BASE + 0xb3854, 'Native roster lookup target')
        roster.append(prefix[1])
    require(len(set(roster)) == 8, 'Eight unique native persistent party records')
    manager = q.hooks.allocate(0x40)
    q.call(0x1aa0, manager + 4)
    q.call(0xb216c, manager, 0)
    abi = resource_rows((data/'Abi/0000.abi').read_bytes(), ABI_SHA, 205, 7, 0x158)
    rows = []
    for char_id in roster:
        row = q.call(0xb3854, manager, char_id)
        require(row and q.read(row + 4) == char_id, 'Native party row identity')
        actions = struct.unpack('<10i', q.cpu.mem_read(row + 0xe8, 40))
        abilities = []
        for action in actions:
            if action < 0:
                continue
            matches = [abi[i:i+0x158] for i in range(0, len(abi), 0x158)
                       if struct.unpack_from('<I', abi, i)[0] == action]
            require(len(matches) == 1, 'Unique actual ability record')
            rage = struct.unpack_from('<i', matches[0], 0x54)[0]
            abilities.append(dict(action=action, apocalypse_action=rage))
        rows.append(dict(char_id=char_id, model_id=q.call(0xb1cb1, row, 0),
                         abilities=abilities,
                         source_row_sha256=hashlib.sha256(bytes(q.cpu.mem_read(row, 300))).hexdigest()))
    # Exact native argument-building sequences bind the popup to the victim
    # (frame -1f8), not the attacker's model or a character-specific screen slot.
    producers = [(0x8c3ab, '6a268b9508feffff528b45f0508b8d08feffff518b55ec528b4db8'),
                 (0x8c860, '6a268b8d08feffff518b55f0528b8508feffff508b4dec518b8d28feffff')]
    for start, expected in producers:
        raw = bytes.fromhex(expected)
        require(bytes(q.cpu.mem_read(BASE+start, len(raw))) == raw, 'Victim-bound popup arguments')
        call = BASE+start+len(raw)
        require(bytes(q.cpu.mem_read(call, 1)) == b'\xe8' and
                call+5+struct.unpack('<i', q.cpu.mem_read(call+1, 4))[0] == BASE+0xa9ef0,
                'Both native numeric damage producers share constructor')
    return dict(schema=1, roster=rows, roster_switch_rva='b37cd',
                numeric_producer_calls=['8c3c6', '8c87e'],
                popup_constructor_rva='a9ef0', anchor_subject='victim_model',
                engine_sha256=hashlib.sha256((data/'MCAlpha.dll').read_bytes()).hexdigest(),
                game_started=False, limits=[
                    'Roster and initial ability slots are native resource inventory, not execution of every learned skill.',
                    'Numeric popup sink receives victim and damage, not attacker identity; common sink tests are separate.',
                    'Attack resolution, skill camera lifecycle, multi-target timing and full battle pixels require game acceptance.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    require(not a.report.exists() and not a.report.resolve().is_relative_to(a.data.resolve()), 'New external report')
    result = audit(a.data)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    require(json.loads(a.report.read_text(encoding='utf8')) == result, 'Reopen roster report')
    print('DAMAGE_ROSTER PASS characters=8 numeric_producers=2 subject=victim game_started=false')


if __name__ == '__main__':
    main()
