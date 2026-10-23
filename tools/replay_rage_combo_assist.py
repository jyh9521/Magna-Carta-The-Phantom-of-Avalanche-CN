"""Compiled F11 input -> original Apocalypse/rage handler, timer and grading.

An original Apocalypse-capable ability and energy level 3 are starting inputs.
No game/DLL entry, renderer or system key injection executes.
"""
import argparse
import json
from pathlib import Path
import struct

from replay_combo_assist_chain import AssistReplay, Producer, sha
from replay_combo_cue import value_data
from replay_battle_message_queue import BASE, SCENE, ACTOR, require
from replay_native_combo_scoring import setupCombatResources, native_call
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_EIP, UC_X86_REG_ECX


class RageReplay(AssistReplay):
    def __init__(self,image,values,abi,producer,hz,scenario,data,action=13):
        super().__init__(image,values,abi,producer,hz,scenario,data)
        resources=setupCombatResources(self,data,action=action)
        self.resource_config=resources['config']
        rows=self.hooks.allocate(8*len(values))
        self.cpu.mem_write(rows,b''.join(struct.pack('<ii',k,v) for k,v in values.items()))
        self.write(self.resource_config+0x1088,rows);self.write(self.resource_config+0x108c,len(values))
        self.write(ACTOR+0x22c,values[0x38])
        self.rage_records=self.hooks.allocate(4*values[0x3a])
        self.write(SCENE+0x1dec,self.rage_records)
        self.ability_row=native_call(self,0xb5967,self.resource_config,action)
        self.apocalypse_action=self.read(self.ability_row+0x54)
        require(self.apocalypse_action!=0xffffffff,'Original ability has no Apocalypse target')
        require(native_call(self,0xa412d,SCENE)==1,'Actual ability/energy predicate must select rage')
        self.stub(0xab511,'rage_result_render_constructor',20,lambda:self.cpu.reg_read(UC_X86_REG_ECX))
        self.native_resources.update(action=action,ability_id=action,apocalypse_action=self.apocalypse_action,energy=values[0x38],
            duration=values[0x39],limit=values[0x3a],margin=values[0x3b])

    def finish_settlement(self):
        self.settlement['selected_action']=self.read(SCENE+0x1744)
        sp,bp=self.completion_context
        self.cpu.reg_write(UC_X86_REG_ESP,sp);self.cpu.reg_write(UC_X86_REG_EBP,bp)
        self.ret(0,1);self.completed=True;self.scoring_phase='done'

    def _instruction(self,cpu,address,size,data):
        if hasattr(self,'ability_row'):
            fp=0x30018000
            if address==BASE+0xa4ecd:
                self.completion_context=(cpu.reg_read(UC_X86_REG_ESP),cpu.reg_read(UC_X86_REG_EBP))
                self.completion_active=self.read(SCENE+0x1dc4)
                cpu.reg_write(UC_X86_REG_EBP,fp);cpu.reg_write(UC_X86_REG_ESP,fp-0x500)
                self.write(fp-0x390,SCENE);self.write(fp-0x30,self.ability_row)
                self.scoring_phase='rage_score';cpu.reg_write(UC_X86_REG_EIP,BASE+0xa519d);return
            if address==BASE+0xa5296 and self.scoring_phase=='rage_score':
                self.settlement=dict(success=self.read(fp-0x274),grade=self.read(fp-0x27c))
                self.scoring_phase='rage_selection'
                if self.settlement['success']!=1:
                    # Failed grading is observed; energy/UI failure effects are leaves.
                    self.finish_settlement();return
            if address==BASE+0xa55e1 and self.scoring_phase=='rage_selection':
                self.finish_settlement();return
        super()._instruction(cpu,address,size,data)

    def keyboard(self):
        seq=self.sequence;self.sequence+=1
        f10=self.scenario=='f10' and seq==0
        trigger_at=1 if self.scenario=='manual_takeover' else 4 if self.scenario=='late_takeover' else 0
        f11=self.scenario!='f10' and (seq==trigger_at or self.scenario=='held_f11')
        manual=(self.scenario in ('manual_takeover','late_takeover') and seq==0) or (self.scenario=='manual_hold' and seq>=1)
        counter=self.read(BASE+0xf1c9c+32*4)
        if counter>=0x80000000:counter-=0x100000000
        fields=[seq,1,1,self.read(SCENE+0x1dc4),self.read(SCENE+0x1dcc),
            self.read(SCENE+0x1de0),self.read(SCENE+0x1ddc),self.values[0x23],self.values[0x24],
            int(not(self.scenario=='focus_loss' and seq>=1)),1,0,int(f10)+2*int(f11),0,int(manual),1,0,counter,
            self.values[0x25],self.read(SCENE+0x40),self.read(SCENE+0x1744),
            self.read(SCENE+0x1de8),self.read(SCENE+0x1df4),self.read(SCENE+0x1df0),
            self.values[0x39],self.values[0x3a],self.values[0x3b]]
        row=self.producer.sample(fields)
        self.cpu.mem_write(self.arg(0),bytes.fromhex(row['keysHex']))
        if row['clearSpaceCounter']:self.write(BASE+0xf1c9c+32*4,row['spaceCounterAfter'])
        self.polls.append(dict(time=self.now,fields=fields,space=bool(bytes.fromhex(row['keysHex'])[32]&128)))
        return int(row['ok'])


def run(data,bridge,hz=60,scenario='f11',expect_success=False,action=13):
    require(hz in (30,60) and scenario in ('f10','f11','held_f11','focus_loss','manual_takeover','late_takeover','manual_hold'),'Unsupported rage case')
    data=Path(data);image=(data/'MCAlpha.dll').read_bytes()
    values=value_data((data/'ValueData/0001.val').read_bytes());abi=(data/'Abi/0000.abi').read_bytes()
    producer=Producer(bridge,True)
    try:
        require(producer.ready.get('rageStateFields'),'Build the extended owned input bridge')
        q=RageReplay(image,values,abi,producer,hz,scenario,data,action)
        for frame in range(1,hz*2+1):
            q.frame(frame*1000//hz)
            if q.completed:break
        report=q.finish()
        report.update(scenario=scenario,rage_count=q.read(SCENE+0x1df0),rage_tick=q.read(SCENE+0x1df4),
            rage_recorded=[q.read(q.rage_records+4*i) for i in range(values[0x3a])],
            settlement=q.settlement,completed=q.completed,transition_calls=q.transition_calls,
            resources=q.native_resources,producer_sha256=producer.identity,production_rows=producer.rows)
        report['native_timer_completion']=dict(active_after=q.read(SCENE+0x1dc4),transition_calls=q.transition_calls)
        report['boundaries']=['Ability ID, energy level3, selected target and active battle are controlled starting inputs.',
            'Original ability/energy predicates, 33ms scheduler, keyboard counters, GUI listener, rage handler/timer, grade loop and ApocalypseAbility selection execute.',
            'Pre-grading geometry/damage preparation and post-selection animation are leaves; failure energy/UI effects are leaves.',
            'Grade-result visual constructor and graphics/audio objects are leaves; no whole battle or rendered acceptance.']
        report['producer_rollback']=producer.close()
        if expect_success:
            require(q.completed and q.settlement['success']==1 and q.settlement['grade']==3
                    and q.settlement['selected_action']==q.apocalypse_action and q.transition_calls==1 and q.read(SCENE+0x1dc4)==0,
                    'F11 did not complete the original best-grade rage selection')
            require(report['rage_recorded']==[0,3,6],'Unexpected native rage cadence')
        return report
    finally:
        if producer.process.poll() is None:
            producer.process.kill();producer.process.wait(timeout=10)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--bridge',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--scenario',default='f11')
    p.add_argument('--hz',type=int,default=60);p.add_argument('--expect-success',action='store_true')
    p.add_argument('--action',type=int,default=13)
    a=p.parse_args()
    require(not a.report.exists(),'New report required')
    r=run(a.data,a.bridge,a.hz,a.scenario,a.expect_success,a.action)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,indent=2)+'\n')
    print(f'RAGE_COMBO scenario={a.scenario} count={r["rage_count"]} ticks={r["rage_recorded"]} settlement={r["settlement"]} game_started=false')
