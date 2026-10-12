"""Deterministic private two-byte glyph mapping for the observed native Chi route."""
from resource_font import native_slot


RESERVED_TRAIL = {0x5c, 0x7b, 0x7d}


def private_slots(fonts):
    """Use only native-range pairs invalid in CP949, not presumed-empty bitmap slots."""
    for lead in range(0xca, 0xfe):
        for trail in range(0x40, 0xa1):
            if trail in RESERVED_TRAIL:
                continue
            pair = bytes([lead, trail])
            try:
                pair.decode('cp949', 'strict')
            except UnicodeDecodeError:
                pass
            else:
                continue
            family, index, consumed = native_slot(pair)
            if family == 'Chi' and consumed == 2 and all(0 <= index < font.count for font in fonts):
                yield pair, index


def plan(characters, fonts):
    required = sorted({char for char in characters if ord(char) >= 0x80}, key=ord)
    if any(0xd800 <= ord(char) <= 0xdfff for char in required):
        raise ValueError('surrogate codepoint cannot be mapped')
    available = list(private_slots(fonts))
    if len(required) > len(available):
        raise ValueError('native private glyph capacity exceeded')
    return {char: dict(encoded_hex=pair.hex(), index=index) for char, (pair, index) in zip(required, available)}


def validate(mapping):
    seen = set()
    for char, item in mapping.items():
        if len(char) != 1 or ord(char) < 0x80 or 0xd800 <= ord(char) <= 0xdfff:
            raise ValueError('invalid mapped codepoint')
        pair = bytes.fromhex(item['encoded_hex'])
        if len(pair) != 2 or pair in seen:
            raise ValueError('duplicate or invalid encoded pair')
        family, index, consumed = native_slot(pair)
        if not (family == 'Chi' and index >= 0 and consumed == 2 and 0xca <= pair[0] <= 0xfd and pair[1] >= 0x40
                and pair[1] <= 0xa0 and pair[1] not in RESERVED_TRAIL and item['index'] == index):
            raise ValueError('mapping does not follow reserved native Chi route')
        try:
            pair.decode('cp949', 'strict')
        except UnicodeDecodeError:
            pass
        else:
            raise ValueError('mapping overwrites a valid CP949 code')
        seen.add(pair)


def encode(text, mapping):
    validate(mapping)
    result = bytearray()
    for char in text:
        if char == '\0':
            raise ValueError('embedded terminator is not text')
        if ord(char) < 0x80:
            result.append(ord(char))
        else:
            if char not in mapping:
                raise ValueError(f'unmapped codepoint U+{ord(char):04X}')
            result.extend(bytes.fromhex(mapping[char]['encoded_hex']))
    return bytes(result)


def decode(data, mapping):
    validate(mapping)
    reverse = {bytes.fromhex(item['encoded_hex']): char for char, item in mapping.items()}
    result = []
    offset = 0
    while offset < len(data):
        if data[offset] == 0:
            raise ValueError('embedded terminator is not text')
        if data[offset] < 0x80:
            result.append(chr(data[offset])); offset += 1
        else:
            pair = data[offset:offset + 2]
            if pair not in reverse:
                raise ValueError('unknown native encoded pair')
            result.append(reverse[pair]); offset += 2
    return ''.join(result)
