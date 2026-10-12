"""Read x86 minidumps and recover preserved earlier exception contexts."""
import argparse
import json
from pathlib import Path
import struct

REGISTERS = {'edi': 156, 'esi': 160, 'ebx': 164, 'edx': 168, 'ecx': 172,
             'eax': 176, 'ebp': 180, 'eip': 184, 'esp': 196}


class Dump:
    def __init__(self, data):
        self.data = data
        if self.take(0, 4) != b'MDMP':
            raise ValueError('Invalid dump signature')
        count, directory = self.unpack('<II', 8)
        self.take(directory, count * 12)
        self.streams = {}
        for i in range(count):
            kind, size, offset = self.unpack('<III', directory + 12 * i)
            if kind:
                self.take(offset, size)
                if kind in self.streams:
                    raise ValueError('Duplicate stream')
                self.streams[kind] = (offset, size)
        system, _ = self.stream(7, 2)
        if self.unpack('<H', system)[0] != 0:
            raise ValueError('Only x86 contexts supported')
        at, size = self.stream(5, 4)
        count = self.unpack('<I', at)[0]
        if 4 + count * 16 > size:
            raise ValueError('Truncated memory descriptors')
        self.memory = [self.unpack('<QII', at + 4 + i * 16) for i in range(count)]
        for _, size, offset in self.memory:
            self.take(offset, size)
        at, size = self.stream(4, 4)
        count = self.unpack('<I', at)[0]
        if 4 + 108 * count > size:
            raise ValueError('Truncated module list')
        self.modules = []
        for i in range(count):
            base, length, checksum, timestamp, name = self.unpack('<QIIII', at + 4 + 108 * i)
            size = self.unpack('<I', name)[0]
            text = self.take(name + 4, size).decode('utf-16le')
            self.modules.append({'base': base, 'size': length, 'name': text.replace('\\', '/').split('/')[-1],
                                 'timestamp': timestamp, 'checksum': checksum})

    def take(self, at, size):
        if at < 0 or size < 0 or at + size > len(self.data):
            raise ValueError('Dump range outside file')
        return self.data[at:at + size]

    def unpack(self, fmt, at):
        return struct.unpack(fmt, self.take(at, struct.calcsize(fmt)))

    def stream(self, kind, minimum):
        if kind not in self.streams or self.streams[kind][1] < minimum:
            raise ValueError('Missing or truncated stream')
        return self.streams[kind]

    def read(self, address, size):
        for base, length, at in self.memory:
            if base <= address and address + size <= base + length:
                return self.take(at + address - base, size)
        raise ValueError('Address not captured')

    def location(self, address):
        for module in self.modules:
            if module['base'] <= address < module['base'] + module['size']:
                return {'module': module['name'], 'base': hex(module['base']),
                        'rva': hex(address - module['base'])}
        return {'module': None, 'address': hex(address)}

    def registers(self, data):
        if len(data) < 204:
            raise ValueError('Truncated x86 context')
        return {name: struct.unpack_from('<I', data, at)[0] for name, at in REGISTERS.items()}

    def frames(self, bp):
        rows = []
        for _ in range(128):
            try:
                next_bp, ret = struct.unpack('<II', self.read(bp, 8))
            except ValueError:
                break
            rows.append({'frame_pointer': hex(bp), 'return_site': self.location(ret)})
            if next_bp <= bp or next_bp > bp + 0x10000:
                break
            bp = next_bp
        return rows

    def inspect(self):
        at, _ = self.stream(6, 168)
        thread, code = self.unpack('<I4xI', at)
        address = self.unpack('<Q', at + 24)[0]
        size, context = self.unpack('<II', at + 160)
        regs = self.registers(self.take(context, size))
        result = {'thread': thread, 'recorded_exception': hex(code),
                  'recorded_location': self.location(address),
                  'recorded_registers': {n: hex(v) for n, v in regs.items()},
                  'recorded_frame_chain': self.frames(regs['ebp']), 'earlier_contexts': []}
        # Recover an exception record followed by an x86 CONTEXT preserved on
        # the recorded thread's stack. Do not scan unrelated heaps or emit text.
        for base, length, offset in self.memory:
            if not base <= regs['esp'] < base + length:
                continue
            data = self.take(offset, length)
            for pos in range(0, len(data) - 284, 4):
                values = struct.unpack_from('<7I', data, pos)
                if values[0] != 0xc0000005 or values[4] != 2:
                    continue
                context = data[pos + 80:pos + 284]
                flags = struct.unpack_from('<I', context)[0]
                if flags & 0xffff0000 != 0x10000:
                    continue
                prior = self.registers(context)
                if prior['eip'] != values[3] or not base <= prior['esp'] < base + length:
                    continue
                result['earlier_contexts'].append({
                    'record_address': hex(base + pos), 'exception': '0xc0000005',
                    'fault_location': self.location(prior['eip']),
                    'access': 'read' if values[5] == 0 else 'other', 'access_address': hex(values[6]),
                    'registers': {n: hex(v) for n, v in prior.items()},
                    'frame_chain': self.frames(prior['ebp'])})
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dump', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.resolve() == args.dump.resolve():
        parser.error('Use a new report path')
    result = Dump(args.dump.read_bytes()).inspect()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f"MINIDUMP_INSPECT_PASS recorded={result['recorded_exception']} earlier_contexts={len(result['earlier_contexts'])} game_started=false")
