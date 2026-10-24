"""Source battle timelines and native per-victim damage popup regressions."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from resource_effect_script import parse as effect
from resource_model_timeline import parse as model

DATA=ROOT/'runtime/data'
BRIDGE=ROOT/'build/native/Release/damage-render-fixture/damage_projection_bridge.exe'
READY=(all(importlib.util.find_spec(n) for n in ('unicorn','pefile'))
       and (DATA/'MCAlpha.dll').is_file() and BRIDGE.is_file()
       and (ROOT/'build/native/Release/combo_assist_chain_fixture.exe').is_file())


class FormatGuards(unittest.TestCase):
    def test_effect_rejects_truncation_and_excess_counts(self):
        for raw in (b'',struct.pack('<2i',-1,1),struct.pack('<2i',4097,1),struct.pack('<2i',1,1)):
            with self.subTest(raw=raw),self.assertRaises(ValueError):effect(raw)

    def test_model_rejects_unknown_kind_and_truncated_geometry(self):
        for raw in (b'',struct.pack('<i',2),struct.pack('<2i',0,1),struct.pack('<2i',1,4097)):
            with self.subTest(raw=raw),self.assertRaises((ValueError,struct.error)):model(raw)


@unittest.skipUnless(READY,'Supply supported original resources and offline dependencies')
class CombatResources(unittest.TestCase):
    def test_all_eight_battle_models_and_all_forty_source_effects(self):
        from replay_combat_damage import CombatDamageReplay
        q=CombatDamageReplay(DATA,BRIDGE)
        try:
            ids=[0,3,2,1,4,6,5,20]
            models=[321,320,32,35,165,78,124,97]
            bases=[13,14,30,22,38,54,46,62]
            abil=(DATA/'Abi/0000.abi').read_bytes()
            attack=(DATA/'Att/0000.att').read_bytes()
            abilities={struct.unpack_from('<i',abil,o)[0]:abil[o:o+344] for o in range(8,len(abil),344)}
            attacks={struct.unpack_from('<i',attack,o)[0]:attack[o:o+80] for o in range(8,len(attack),80)}
            resources=set()
            for character,expected,base in zip(ids,models,bases):
                row=q.call(0xb3854,q.manager,character)
                self.assertEqual(q.call(0xb1cb1,row,1),expected)
                self.assertEqual(q.call(0xb1b94,row,0),base)
                timeline=model((DATA/'3DOBS'/f'{expected:04d}.3do').read_bytes())
                self.assertTrue(timeline['exact_eof'])
                self.assertFalse(any(c['sample']<0 and c['kind']==9 for s in timeline['sequences'] for c in s['commands']))
                actions=[base,*struct.unpack_from('<3i',abilities[base],0x48),struct.unpack_from('<i',abilities[base],0x54)[0]]
                for action in actions:
                    att=struct.unpack_from('<i',abilities[action],0x44)[0]
                    efs=struct.unpack_from('<i',attacks[att],0x20)[0]
                    resources.add(efs)
                    self.assertTrue(effect((DATA/'EffScr'/f'{efs:04d}.efs').read_bytes())['exact_eof'])
            self.assertEqual(len(resources),40)
        finally:q.close()

    def test_normal_and_f11_model_hit_frames_are_not_efs_damage_commands(self):
        normal=effect((DATA/'EffScr/0161.efs').read_bytes())
        rage=effect((DATA/'EffScr/0255.efs').read_bytes())
        for script in (normal,rage):
            self.assertFalse(any(a['opcode']==800 for e in script['events'] for a in e['actions']))
        timelines={s['key']:s for s in model((DATA/'3DOBS/0321.3do').read_bytes())['sequences']}
        self.assertEqual([c['tick'] for c in timelines[20]['commands'] if c['kind']==9],[14])
        self.assertEqual([c['tick'] for c in timelines[28]['commands'] if c['kind']==9],[10,20,32,46,66,70,76])

    def test_f10_maps_requested_ability_instead_of_fixed_ability_three(self):
        from replay_combo_assist_chain import run_case
        from replay_combo_cue import value_data
        result=run_case((DATA/'MCAlpha.dll').read_bytes(),value_data((DATA/'ValueData/0001.val').read_bytes()),
                        (DATA/'Abi/0000.abi').read_bytes(),ROOT/'build/native/Release/combo_assist_chain_fixture.exe',
                        60,'f10',True,DATA,13)
        self.assertEqual(result['settlement']['selected_action'],132)
        self.assertEqual(result['producer_rollback']['rollback'],'both_IATs_byte_exact')

    def test_original_model_command_reaches_hidden_victim_and_digit_draw(self):
        from replay_combat_damage import replay
        case=replay(DATA,BRIDGE,0,13)
        self.assertEqual(len(case['popups']),1)
        self.assertEqual(case['model_commands'][0]['kind'],9)
        self.assertTrue(any(f['hidden'] for f in case['frames']))
        self.assertTrue(any(not f['hidden'] for f in case['frames']))
        self.assertTrue(all(p.get('ended') for p in case['popups']))
        self.assertTrue(any(f.get('draw_count') for f in case['frames']))
        self.assertFalse(case['game_started'])

    def test_native_skill_camera_hides_only_offscreen_digits_and_restores_them(self):
        from replay_combat_damage import replay
        with self.assertRaisesRegex(ValueError,'Native numeric digit count tick=11: 5'):
            replay(DATA,BRIDGE,3,14,visibility_mode='native')
        case=replay(DATA,BRIDGE,3,14)
        first=[f for f in case['frames'] if f['tick']==11]
        self.assertEqual(first[0]['screen'],[-1,-1])
        self.assertNotEqual(first[1]['screen'],[-1,-1])
        self.assertEqual(first[-1]['draw_count'],2)
        self.assertTrue(any(f.get('draw_count')==5 and f['camera_probe'] for f in case['frames']))


if __name__=='__main__':unittest.main()
