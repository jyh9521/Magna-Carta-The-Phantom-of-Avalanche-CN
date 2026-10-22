"""Replay source-bound 33 ms task dispatch at 30/60 presentation rates, never load a DLL."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

SOURCE_SHA = '7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e'
BASE = 0x52000000
START = BASE + 0xcee3
STOP = BASE + 0xcf61
CALLBACK = 0x60000000
TASK = 0x20000100
OWNER = 0x20000500
TABLE = 0x20000600
COUNTER = 0x20000700
FRAME = 0x4000f000
GUARDS = {
    0xcee3: bytes.fromhex('c745fc00000000'),
    0xcf01: bytes.fromhex('8b50103b51087302eb46'),
    0xcf3a: bytes.fromhex('ff5208'),
    0xcf43: bytes.fromhex('8b50102b51088b45f8895010'),
}

class ReplayError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise ReplayError(message)

def mapped_image(source: bytes):
    require(hashlib.sha256(source).hexdigest() == SOURCE_SHA, 'Unsupported complete engine SHA256')
    import pefile
    pe = pefile.PE(data=source)
    require(pe.FILE_HEADER.Machine == 0x14c and pe.OPTIONAL_HEADER.Magic == 0x10b,
            'Expected supported PE32 x86 engine')
    require(pe.OPTIONAL_HEADER.ImageBase == BASE and pe.OPTIONAL_HEADER.SizeOfImage == 0x10b000,
            'Unsupported engine image layout')
    image = pe.get_memory_mapped_image()
    for rva, expected in GUARDS.items():
        require(image[rva:rva+len(expected)] == expected, f'Scheduler instruction mismatch at RVA {rva:x}')
    return image

def run_case(image, hz, duration_ms, instruction_budget=500):
    require(hz in (30, 60), 'Only compared presentation rates 30 and 60 are supported')
    require(isinstance(duration_ms, int) and 1000 <= duration_ms <= 120000 and duration_ms % 100 == 0,
            'Duration must be 1000..120000 ms in complete 100 ms steps')
    require(isinstance(instruction_budget, int) and 1 <= instruction_budget <= 1000,
            'Per-frame instruction budget must be from 1 to 1000')
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP
    cpu = Uc(UC_ARCH_X86, UC_MODE_32)
    cpu.mem_map(BASE, 0x10b000);cpu.mem_write(BASE, image)
    cpu.mem_map(0x20000000, 0x2000)
    cpu.mem_map(0x40000000, 0x10000)
    cpu.mem_map(CALLBACK, 0x1000)
    def write(address, value):cpu.mem_write(address, struct.pack('<I', value))
    def read(address):return struct.unpack('<I', cpu.mem_read(address, 4))[0]
    write(TASK+4, OWNER);write(OWNER, TABLE);write(TABLE+8, CALLBACK)
    write(TASK+8, 33);write(FRAME-8, TASK)
    # Owned INC absolute-memory / RET callback only counts native virtual dispatches.
    callback = b'\xff\x05' + struct.pack('<I', COUNTER) + b'\xc3'
    cpu.mem_write(CALLBACK, callback)
    instruction_count = 0
    def instruction(_cpu, address, size, _data):
        nonlocal instruction_count
        require(START <= address < STOP or CALLBACK <= address < CALLBACK+len(callback),
                f'Unexpected instruction outside bounded scheduler/callback: {address:x}')
        instruction_count += 1
    cpu.hook_add(UC_HOOK_CODE, instruction)
    frames = duration_ms*hz//1000
    previous = 0
    for frame in range(1, frames+1):
        now = min(frame*1000//hz, duration_ms)
        write(TASK+0x10, read(TASK+0x10)+now-previous)
        previous = now
        cpu.reg_write(UC_X86_REG_EBP, FRAME);cpu.reg_write(UC_X86_REG_ESP, FRAME-0x100)
        cpu.emu_start(START, STOP, count=instruction_budget)
        require(cpu.reg_read(UC_X86_REG_EIP) == STOP,
                f'Scheduler did not reach stop before instruction budget at presentation frame {frame}')
    require(previous == duration_ms, 'Duration must end on a presentation frame for both compared rates')
    dispatches, remainder = read(COUNTER), read(TASK+0x10)
    require(dispatches == duration_ms//33 and remainder == duration_ms%33,
            'Native scheduler result differs from fixed-interval conservation')
    return dict(presentation_hz=hz, elapsed_ms=previous, presentation_frames=frames,
                native_dispatches=dispatches, remainder_ms=remainder,
                instructions=instruction_count, instruction_budget_per_frame=instruction_budget,
                expected_stop_rva='0xcf61', stop_verified_every_frame=True)

def verify(source: bytes, duration_ms=60000, instruction_budget=500):
    image = mapped_image(source)
    cases = [run_case(image, hz, duration_ms, instruction_budget) for hz in (30, 60)]
    require(cases[0]['native_dispatches'] == cases[1]['native_dispatches'] and
            cases[0]['remainder_ms'] == cases[1]['remainder_ms'],
            '30/60 Hz native dispatch results differ')
    return dict(engine_sha256=hashlib.sha256(source).hexdigest(), core_rva='0xcee3..0xcf61',
                task_interval_ms=33, cases=cases, game_started=False, dll_loaded=False,
                callback='Owned counter stub, not the commercial battle/keyboard body.',
                limits=['Elapsed accumulation supplied at the native dispatch-loop boundary.',
                        'Does not prove visual cue alignment, physical keyboard acceptance or complete battle behavior.'])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--duration-ms',type=int,default=60000)
    args=parser.parse_args()
    if args.report.resolve()==args.sample.resolve() or args.report.exists():
        parser.error('New report path distinct from source required')
    report=verify(args.sample.read_bytes(),args.duration_ms)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    for case in report['cases']:
        print(f"COMBAT_SCHEDULER hz={case['presentation_hz']} elapsed_ms={case['elapsed_ms']} native_dispatches={case['native_dispatches']} remainder_ms={case['remainder_ms']} core=CEE3-CF61 game_started=false")

if __name__=='__main__':main()
