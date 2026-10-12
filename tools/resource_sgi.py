"""Byte-preserving SGI records and bounded, diagnostic display-name replacement."""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class Table:
    header: bytes
    records: tuple

    def to_bytes(self):
        data = self.header + b''.join(self.records)
        parse(data)
        return data

    def name(self, ordinal):
        if type(ordinal) is not int or not 0 <= ordinal < len(self.records):
            raise ValueError('record ordinal outside table')
        field = self.records[ordinal][4:104]
        if b'\0' not in field:
            raise ValueError('name has no terminator in observed field')
        return field.split(b'\0', 1)[0]

    def replace_name(self, ordinal, identifier, expected, target):
        source = self.name(ordinal)
        record = self.records[ordinal]
        if struct.unpack_from('<I', record)[0] != identifier or source != expected:
            raise ValueError('record identifier or expected name mismatch')
        if not target or b'\0' in target or any(c < 0x20 for c in target):
            raise ValueError('empty target or unsupported control bytes')
        # The actual maximum runtime field length is not yet proved.
        # This probe never extends beyond the existing string and its terminator.
        if len(target) > len(source):
            raise ValueError('target exceeds observed original string span')
        span = len(source) + 1
        rewritten = record[:4] + target + bytes(span - len(target)) + record[4 + span:]
        rows = list(self.records)
        rows[ordinal] = rewritten
        return Table(self.header, tuple(rows))


def parse(data):
    if len(data) < 8:
        raise ValueError('truncated SGI header')
    count = struct.unpack_from('<I', data)[0]
    if not 1 <= count <= 65536 or len(data) != 8 + count * 164:
        raise ValueError('SGI record count or size mismatch')
    # Header word 2 and all non-name bytes remain uninterpreted and preserved.
    return Table(bytes(data[:8]), tuple(bytes(data[8 + i * 164:8 + (i + 1) * 164]) for i in range(count)))
