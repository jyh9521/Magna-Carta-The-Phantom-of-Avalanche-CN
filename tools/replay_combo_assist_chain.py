"""Closed-loop compiled production input -> original battle/combo instructions.

Each native keyboard poll sends the current original scene fields to a persistent
owned Win32 producer. Its complete key snapshot re-enters original keyboard
counters, GUI dispatch, battle listener, handler and timer. No game is launched.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess

from replay_battle_message_queue import QueueReplay, SCENE, ACTOR, BASE, require
from replay_combo_cue import value_data
from replay_native_title import NativeTitle, STOP
from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EAX, UC_X86_REG_ECX

from replay_native_combo_scoring import setupCombatResources


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Producer:
    def __init__(self, path, keyboard_only=False):
        self.path = Path(path).resolve(strict=True)
        self.identity = sha(self.path.read_bytes())
        self.command = [str(self.path)]+(['--keyboard-only'] if keyboard_only else [])
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self.ready = self.receive()
        require(self.ready.get('ready') is True and self.ready.get('gameStarted') is False,
                'Unknown owned producer protocol')
        self.rows = []

    def receive(self):
        raw = self.process.stdout.readline()
        require(bool(raw), 'Owned input producer ended unexpectedly')
        return json.loads(raw)

    def sample(self, fields):
        self.process.stdin.write(' '.join(map(str, fields))+'\n')
        self.process.stdin.flush()
        row = self.receive()
        require(row['seq'] == fields[0] and len(bytes.fromhex(row['keysHex'])) == 256,
                'Incomplete production keyboard snapshot')
        self.rows.append(dict(input=fields, output=row))
        return row

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write('QUIT\n')
            self.process.stdin.flush()
            result = self.receive()
            require(result.get('rollback') == 'both_IATs_byte_exact' and
                    result['iatBeforeHex'] == result['iatAfterHex'], 'Production IAT rollback failed')
            self.process.wait(timeout=10)
            require(self.process.returncode == 0, 'Owned producer failure')
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()
            return result
        raise ValueError('Owned producer did not reach exact rollback')


class AssistReplay(QueueReplay):
    def __init__(self, image, values, abi, producer, hz, scenario, data):
        self.producer, self.scenario, self.sequence = producer, scenario, 0
        self.accepted_inputs, self.completed = [], False
        self.values = values
        super().__init__(image, values, hz, [])
        resources = setupCombatResources(self, data)
        require(sha(abi) == resources['abi'], 'Ability argument does not match mapped resource')
        self.resource_config = resources['config']
        value_rows = self.hooks.allocate(8*len(values))
        self.cpu.mem_write(value_rows, b''.join(struct.pack('<ii', k, v) for k, v in values.items()))
        self.write(self.resource_config+0x1088, value_rows)
        self.write(self.resource_config+0x108c, len(values))
        # Actual actor-ready getter, not an unconditional success predicate.
        del self.stubs[BASE+0x8e0ef]
        self.write(ACTOR+0x404, 0)
        self.settlement = None
        self.scoring_phase = None
        self.transition_calls = 0
        self.stub(0xa7303, 'selected_action_animation_boundary', 0, self.action_transition)
        self.stubs.pop(BASE+0xa4ecd)
        self.native_resources = dict(**resources, ability_sha256=sha(abi), ability_id=3,
                                    interval=values[0x23], window=values[0x24], precision=values[0x25])

    def action_transition(self):
        self.transition_calls += 1
        return 0

    def _instruction(self, cpu, address, size, data):
        if hasattr(self, 'native_resources'):
            fp = 0x30018000
            if address == BASE+0xa4ecd:
                require(self.settlement is None, 'Unexpected repeated native settlement')
                self.completion_context = (cpu.reg_read(UC_X86_REG_ESP), cpu.reg_read(UC_X86_REG_EBP))
                self.completion_active = self.read(SCENE+0x1dc4)
                cpu.reg_write(UC_X86_REG_EBP, fp)
                cpu.reg_write(UC_X86_REG_ESP, fp-0x500)
                self.write(fp-0x390, SCENE)
                self.scoring_phase = 'score'
                cpu.reg_write(UC_X86_REG_EIP, BASE+0xa57a0)
                return
            if address == BASE+0xa58ba and self.scoring_phase == 'score':
                self.settlement = dict(perfect=self.read(fp-0x298), success_count=self.read(fp-0x2b4))
                self.scoring_phase = 'getter'
                sp = fp-0x600
                self.write(sp, STOP+0x600); self.write(sp+4, 3)
                cpu.reg_write(UC_X86_REG_ESP, sp)
                cpu.reg_write(UC_X86_REG_ECX, self.resource_config)
                cpu.reg_write(UC_X86_REG_EIP, BASE+0xb5967)
                return
            if address == STOP+0x600 and self.scoring_phase == 'getter':
                row = cpu.reg_read(UC_X86_REG_EAX)
                self.write(fp-0x30, row); self.write(fp-0x44, 3); self.write(fp-0x158, 0)
                cpu.reg_write(UC_X86_REG_EBP, fp); cpu.reg_write(UC_X86_REG_ESP, fp-0x500)
                self.scoring_phase = 'selection'
                cpu.reg_write(UC_X86_REG_EIP, BASE+0xa58ba)
                return
            if address == BASE+0xa5ef1 and self.scoring_phase == 'selection':
                self.settlement.update(selected_action=self.read(SCENE+0x1744),
                    popup_kinds=[p['kind'] for p in self.hooks.popups])
                sp, bp = self.completion_context
                cpu.reg_write(UC_X86_REG_ESP, sp); cpu.reg_write(UC_X86_REG_EBP, bp)
                # The remainder of A4ECD constructs the animation. Its successful
                # return is an explicit leaf; original timer chooses A7303.
                self.ret(0, 1)
                self.completed = True
                return
        # ComboHooks used by old input tests stubs these predicates. Here the
        # original functions and original resource getters must execute instead.
        if hasattr(self, 'native_resources') and address in (
                BASE+0xa40df, BASE+0xa412d, BASE+0xb5b0e):
            NativeTitle._instruction(self, cpu, address, size, data)
            return
        super()._instruction(cpu, address, size, data)

    def keyboard(self):
        seq = self.sequence
        self.sequence += 1
        trigger_at = 0 if self.scenario.startswith('f10') else 6
        f10 = int(self.scenario.startswith('f10') and seq == trigger_at)
        buttons = 0x80 if self.scenario in ('r3', 'r3_disconnect') and seq == trigger_at else 0
        if self.scenario in ('held_a', 'held_x') and seq >= 4:
            buttons = (0x1000 if self.scenario == 'held_a' else 0x4000) | (0x80 if seq == trigger_at else 0)
        fields = [seq, 1, 1, self.read(SCENE+0x1dc4), self.read(SCENE+0x1dcc),
            self.read(SCENE+0x1de0), self.read(SCENE+0x1ddc), self.values[0x23],
            self.values[0x24], int(not(self.scenario == 'f10_focus' and seq >= 5)),
            int(not(self.scenario == 'r3_disconnect' and seq >= 10)), 0, f10, buttons, 0, 1,
            int(not self.scenario.startswith('f10')), self.read(BASE+0xf1c9c+32*4), self.values[0x25]]
        if self.producer.ready.get('nativeIdentityFields'):
            fields += [self.read(SCENE+0x40), self.read(SCENE+0x1744)]
        # Key counters are signed in the producer protocol.
        if fields[17] >= 0x80000000:
            fields[17] -= 0x100000000
        row = self.producer.sample(fields)
        self.cpu.mem_write(self.arg(0), bytes.fromhex(row['keysHex']))
        if row['clearSpaceCounter']:
            self.write(BASE+0xf1c9c+32*4, row['spaceCounterAfter'])
        self.polls.append(dict(time=self.now, fields=fields, space=bool(
            bytes.fromhex(row['keysHex'])[32]&128), counter=fields[17]))
        return int(row['ok'])


def run_case(image, values, abi, bridge, hz, scenario, expect_perfect=False, data=None):
    require(hz in (30, 60) and scenario in ('f10', 'r3', 'held_a', 'held_x', 'f10_focus', 'r3_disconnect'), 'Unsupported chain scenario')
    producer = Producer(bridge, scenario.startswith('f10'))
    try:
        q = AssistReplay(image, values, abi, producer, hz, scenario, data)
        for frame in range(1, hz*2+1):
            q.frame(frame*1000//hz)
            if q.completed:
                break
        result = q.finish()
        result.update(scenario=scenario, production_rows=producer.rows,
                      resources=q.native_resources, producer_sha256=producer.identity,
                      producer_ready=producer.ready)
        require(q.completed and q.completion_active == 0 and q.transition_calls == 1 and q.read(SCENE+0x1dc4) == 0, 'Native timer did not settle and transition')
        result['settlement'] = q.settlement
        result['native_timer_completion'] = dict(active_at_settlement=q.completion_active, transition_calls=q.transition_calls, active_after=q.read(SCENE+0x1dc4))
        result['native_perfect_window'] = result['settlement']['perfect'] == 1
        if scenario in ('f10', 'r3'):
            require(result['native_handler_calls'] == 3 and result['count'] == 3,
                    'Production assist did not reach three native combo inputs')
            require([r['id'] for r in result['sounds'][:3]] == [0x237]*3 and
                    all(r['id'] != 0x238 for r in result['sounds']),
                    'Native combo result included failed confirmation')
            if expect_perfect:
                require(producer.ready.get('nativeIdentityFields') is True, 'Rebuild producer with native identity transport')
                require(result['native_perfect_window'] and result['settlement']['success_count'] == 3 and result['settlement']['selected_action'] == 7,
                        'Production assist misses original precise combo windows')
        else:
            require(result['native_handler_calls'] == 1 and result['settlement']['success_count'] == 1
                    and result['settlement']['perfect'] == 0
                    and result['settlement']['selected_action'] == 3,
                    'Cancelled/manual request must not receive automatic successful combo')
        result['producer_rollback'] = producer.close()
        return result
    except BaseException:
        if producer.process.poll() is None:
            producer.process.kill()
            producer.process.wait(timeout=10)
        for stream in (producer.process.stdin, producer.process.stdout, producer.process.stderr):
            stream.close()
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('sample', 'values', 'abilities', 'bridge', 'report'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--expect-perfect', action='store_true')
    p.add_argument('--include-negative', action='store_true')
    a = p.parse_args()
    require(not a.report.exists(), 'Report must be new')
    inputs = {path: sha(path.read_bytes()) for path in (a.sample, a.values, a.abilities, a.abilities.parent.parent/'Att/0000.att', a.bridge)}
    scenarios = ('f10', 'r3') + (('held_a', 'held_x', 'f10_focus', 'r3_disconnect') if a.include_negative else ())
    rows = [run_case(a.sample.read_bytes(), value_data(a.values.read_bytes()),
            a.abilities.read_bytes(), a.bridge, hz, scenario, a.expect_perfect, a.abilities.parent.parent)
            for hz in (30, 60) for scenario in scenarios]
    require(all(sha(path.read_bytes()) == value for path, value in inputs.items()), 'Source input drift')
    report = dict(schema=1, cases=rows, game_started=False, commercial_dll_loaded=False,
        boundaries=['Native normal-attack state initialization is a controlled starting condition.',
            'Actual resource predicates/getters, handler, timer and A57A0 scoring/A58BA selection execute.',
            'Settlement pre-scoring geometry/damage and energy level 3/consumed level 0 are controlled inputs; graphics/audio construction are leaves.',
            'Animation and whole-battle content are not rendered or accepted in-game.'])
    a.report.parent.mkdir(parents=True, exist_ok=True)
    with a.report.open('x', encoding='utf8') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print('COMBO_ASSIST_CHAIN PASS cases='+str(len(rows))+' production_input=true native_handler=true '
          'real_ability_predicates=true records='+str([r['recorded'] for r in rows])+
          ' perfect='+str([r['native_perfect_window'] for r in rows])+' game_started=false')


if __name__ == '__main__':
    main()
