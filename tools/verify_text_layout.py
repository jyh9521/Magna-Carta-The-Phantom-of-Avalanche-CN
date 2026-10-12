"""Version-bound text-step static verification. No module execution or writes."""
import argparse
import hashlib
import json
from pathlib import Path

from native_text_codec import private_slots


def step(lead, enabled):
    if type(lead) is not int or not 0 <= lead <= 255:
        raise ValueError('lead byte outside byte range')
    signed = lead if lead < 128 else lead-256
    if signed < -80:
        return 1 if signed < -92 else 2
    return 2 if signed < (0 if enabled else -54) else 1


def prefix_boundaries(data, enabled):
    if b'\0' in data:
        raise ValueError('unexpected text terminator')
    offset = 0; result = []
    while offset < len(data):
        offset += step(data[offset], enabled)
        if offset > len(data):
            raise ValueError('truncated text prefix')
        result.append(offset)
    return result


def verify(path, lock):
    before = Path(path).read_bytes()
    if len(before) != lock['size'] or hashlib.sha256(before).hexdigest() != lock['sha256']:
        raise ValueError('unsupported engine version')
    start = lock['function_file_offset']; code = bytes.fromhex(lock['function_original_hex'])
    if before[start:start+len(code)] != code:
        raise ValueError('text step function context mismatch')
    patch = lock['patch_file_offset']
    if before[patch] != lock['original_byte'] or code[patch-start-2:patch-start+1] != bytes.fromhex('83faca'):
        raise ValueError('text step instruction mismatch')
    class NativeFont: count = 13151
    pairs = list(private_slots([NativeFont(), NativeFont()]))
    if not all(step(pair[0], False) == 1 and step(pair[0], True) == 2 for pair, _ in pairs):
        raise ValueError('private pair step verification failed')
    if not all(step(i, True) == (1 if i < 0xa4 else 2) for i in range(256)):
        raise ValueError('lead byte semantics mismatch')
    if not all(step(i, False) == step(i, True) for i in range(0xca)):
        raise ValueError('original supported lead changed')
    sample = b'A' + pairs[0][0] + b'$n B' + pairs[1][0]
    fixed = prefix_boundaries(sample, True)
    if 2 in fixed or len(sample)-1 in fixed:
        raise ValueError('mapped pair split across prefix')
    if Path(path).read_bytes() != before:
        raise ValueError('source changed during verification')
    return dict(leads=256, private_pairs=len(pairs), baseline_step=1, modified_step=2,
                source_unchanged=True, game_started=False, commercial_code_executed=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--module', type=Path, required=True)
    p.add_argument('--lock', type=Path, default=Path(__file__).resolve().parents[1]/'assets/runtime/native-text-step.json')
    a = p.parse_args(); result = verify(a.module, json.loads(a.lock.read_text('utf8')))
    print('TEXT_LAYOUT_STATIC PASS leads=256 private_pairs='+str(result['private_pairs'])+
          ' baseline_step=1 modified_step=2 source_unchanged=true commercial_code_executed=false game_started=false')
