"""Replay the version-bound battle-menu width decision, without loading the game."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from replay_native_title import NativeTitle, BASE
from replay_native_gui_parent import SOURCE_SHA

FIRST = 0xaefcc
SECOND = 0xaf068
WIDTH = 0xf1b48


class BattleWidth(NativeTitle):
    def __init__(self, image):
        if hashlib.sha256(image).hexdigest() != SOURCE_SHA:
            raise ValueError('Unsupported complete engine SHA256')
        super().__init__(image)
        for site, width in [(FIRST, 640), (SECOND, 800)]:
            expected = b'\x81\x3d' + struct.pack('<II', BASE+WIDTH, width)
            if bytes(self.cpu.mem_read(BASE+site, 10)) != expected:
                raise ValueError('Width comparison mismatch')
        for site, expected in [(0xaf028, b'\x6a\x64'), (0xaf0c4, b'\x68\xce\x00\x00\x00')]:
            if bytes(self.cpu.mem_read(BASE+site, len(expected))) != expected:
                raise ValueError('Resource selection mismatch')
        self.outcome = None

    def _instruction(self, cpu, address, size, data):
        if address in (BASE+0xaefdc, BASE+0xaf078):
            self.outcome = dict(assertion=None, resource_id=100 if address == BASE+0xaefdc else 206)
            cpu.emu_stop()
            return
        if address == BASE+0xaf11c:
            sp = cpu.reg_read(self.regs[1])
            expr, file, line = [self.read(sp+i*4) for i in range(3)]
            def string(a):
                return bytes(cpu.mem_read(a, 256)).split(b'\0')[0].decode('ascii')
            self.outcome = dict(assertion=dict(file=string(file).rsplit('\\', 1)[-1],
                                              line=line, expression=string(expr)), resource_id=None)
            cpu.emu_stop()
            return
        if not BASE+FIRST <= address <= BASE+0xaf11c:
            raise ValueError('Unexpected branch outside width decision')
        self.instructions += 1

    def run(self, width):
        self.write(BASE+WIDTH, width)
        self.cpu.reg_write(self.regs[1], 0x3001f000)
        self.cpu.emu_start(BASE+FIRST, BASE+0xaf125, count=50)
        if self.outcome is None:
            raise ValueError('Width replay did not reach a bounded outcome')
        return self.outcome


def verify(image):
    cases = {str(w): BattleWidth(image).run(w) for w in (640, 800, 853, 1067, 1024)}
    for w, rid in [(640, 100), (800, 206)]:
        if cases[str(w)] != dict(assertion=None, resource_id=rid):
            raise ValueError('Supported width changed')
    for w in (853, 1067, 1024):
        if cases[str(w)]['assertion'] != dict(file='MCBtlMenu.cpp', line=169, expression='0'):
            raise ValueError('Reported assertion not reproduced')
    return dict(engine_sha256=SOURCE_SHA, cases=cases, game_started=False,
                game_dll_loaded=False, limits=['Comparison instructions only; allocation/resource bodies not executed.',
                                               'Does not reproduce the complete player route or eye symptom.'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sample', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    if a.report.exists() or a.report.resolve() == a.sample.resolve():
        p.error('New report path distinct from the sample required')
    result = verify(a.sample.read_bytes())
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print('BATTLE_WIDTH_REPLAY PASS native=640:100,800:206 virtual=853,1067:MCBtlMenu.cpp:169:0 game_started=false')
