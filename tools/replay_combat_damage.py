"""Original skill event execution to per-victim numeric popup draws, offline."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess

from replay_damage_render_chain import DamageReplay, BASE, STOP, fbits
from replay_native_combo_scoring import setupCombatResources
from replay_combo_cue import value_data
from replay_battle_message_queue import require
from resource_effect_script import parse
from resource_model_timeline import parse as parse_model
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EIP


class CombatDamageReplay(DamageReplay):
    def __init__(self, data, bridge, anchor_mode='modified',visibility_mode='modified'):
        self.action_events = []
        self.effects = []
        self.tick = 0
        self.leaf_opcodes = {}
        self.prepared = set()
        self.animations = {}
        self.model_commands = []
        self.popups = []
        self.frames = []
        self.camera_frames = []
        super().__init__(data)
        self.cpu.mem_map(0x22100000,0x700000)
        self.setup_driver()
        self.projection_bridge(bridge)
        require(anchor_mode in ('modified','native','rollback'),'Supported anchor differential')
        self.anchor_mode=anchor_mode
        require(visibility_mode in ('modified','native','rollback'),'Supported visibility differential')
        self.visibility_mode=visibility_mode
        self.anchor_control=None
        self.bridge_process=subprocess.Popen([str(self.bridge_path),str(self.bridge_dll)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        control_mode=anchor_mode if anchor_mode!='modified' else visibility_mode
        if control_mode!='modified':
            self.anchor_control=subprocess.Popen([str(self.bridge_path),str(self.bridge_dll),'--'+control_mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        self.use_fresh_anchor = True
        for i,(slot,code) in enumerate([(0xbd2e4,'dd442404d9e1c3'),(0xbd2e0,'dd442404d9ffc3'),(0xbd2d8,'dd442404d9fec3'),(0xbd318,'dd442404d9c0d8c8d9e8dee1d9fad9c9d9f3c3')]):
            ptr=STOP+0x600+i*32;self.cpu.mem_write(ptr,bytes.fromhex(code));self.write(BASE+slot,ptr)
            self.executable.append((ptr,ptr+32))
        self.write(0x100661ec,STOP+0x600)
        self.import_stub(0xbd2f8,'controlled CRT random boundary',0,lambda:99)
        self.manager = self.hooks.allocate(0x40)
        self.call(0x1aa0, self.manager+4)
        self.call(0xb216c, self.manager, 0)
        self.stub(0x3ddf8, 'mesh resource allocation boundary', 8, lambda:self.cpu.reg_read(UC_X86_REG_ECX))
        self.stub(0x3f00d, 'mesh triangle draw boundary', 0)
        self.stub(0x27162, 'light registration boundary', 0)
        self.scene = self.hooks.allocate(0x3000)
        self.call(0x2590, self.scene, 0, 152)
        self.level = self.hooks.allocate(0x2000)
        self.call(0x2590, self.level, 0, 152)
        self.write(self.scene+0x15d4, self.level)
        self.ui = self.hooks.allocate(0x60)
        self.call(0x8990, self.ui)
        self.gui = self.hooks.allocate(0x300)
        self.call(0x54fce, self.gui, 99, 0, 0, 0, self.ui, 1)
        self.write(self.scene+0x10fc, self.gui)
        self.write(BASE+0xf1a20,1)
        self.camera_manager = self.hooks.allocate(0x100)
        self.call(0x1aa0,self.camera_manager+0x68)
        self.call(0x1aa0,self.camera_manager+0x7c)
        self.write(self.scene+0x44,self.camera_manager)
        self.stub(0x92e50,'mesh preload readiness boundary; CAM resources loaded natively',0,lambda:1)
        self.stub(0x493e0,'sound device constructor boundary',20,lambda:self.cpu.reg_read(UC_X86_REG_ECX))
        self.stub(0xa6e23,'non-numeric impact decoration boundary',44)
        self.stub(0x286b7,'owned BGR resource slot release boundary',4)
        self.lens = self.hooks.allocate(0xb0)
        self.call(0x1d050, self.lens)
        self.cpu.mem_write(self.lens+0xa4,struct.pack('<3f',1,1,1))
        self.camera = self.hooks.allocate(0x200)
        self.write(self.camera+4, self.lens)
        self.write(BASE+0xf228c, self.lens)
        self.write(BASE+0xf2290, self.camera)
        self.cpu.mem_write(self.camera+8,struct.pack('<3f',0,300,100))
        self.cpu.mem_write(self.camera+0x5c,struct.pack('<3f',0,0,1))
        mover=self.hooks.allocate(0x150)
        self.call(0x4f502,mover,0,0,0,0,0,4)
        self.write(self.camera_manager+0x64,mover)
        self.cpu.mem_write(self.camera+0x80, struct.pack('<16f',1,0,0,0,0,0,-1,0,0,1,0,0,0,0,-300,1))
        self.call(0x1d440, self.lens)
        self.call(0x300032c6-BASE, self.driver, 0x1700)
        self.call(self.read(0x3001a5a8+0x288)-BASE, self.driver)

    def actor(self, char_id, serial, x):
        actor = self.hooks.allocate(0x800)
        self.call(0x59bd2, actor, self.scene, 0, 152)
        self.write(actor, BASE+0xc1644)
        self.write(actor+0x20, self.scene)
        self.write(actor+0x424, serial)
        self.write(actor+0x32c,char_id)
        self.call(0x1aa0,actor+0x67c)
        row = self.call(0xb3854, self.manager, char_id)
        require(row, 'Actual character row')
        self.cpu.mem_write(actor+0x1b0, bytes(self.cpu.mem_read(row,300)))
        model = self.hooks.allocate(0x144)
        model_id = self.call(0xb1cb1, row, 1)
        self.call(0x471f0, model, model_id, 0xffffffff, 0, 152)
        self.write(actor+0x2dc, model)
        mesh=self.hooks.allocate(0x80)
        self.write(model+0x140,mesh)
        self.write(mesh+0x2c,100)
        self.write(model+0x20,actor)
        self.write(actor+0x330,1)
        path=self.data/f'3DOBS/{model_id:04}.3do'
        raw=path.read_bytes();timeline=parse_model(raw)
        self.resource_hashes[str(path.resolve())]=timeline['sha256']
        self.animations[mesh]=dict(model=model,sequences={s['key']:s for s in timeline['sequences']})
        self.write(mesh+0x54,model+0x120)
        pose=self.hooks.allocate(0xb0)
        self.write(pose,self.hooks.leaf_table)
        self.write(mesh+0x5c,pose)
        vec = self.hooks.allocate(12)
        self.call(0x65ca6, actor, vec)
        self.call(0x65e80, model, *struct.unpack('<3I',self.cpu.mem_read(vec,12)))
        self.cpu.mem_write(model+0x24, struct.pack('<3f',x,-20,0))
        self.call(0x38c61,model)
        self.cpu.mem_write(actor+0x24,struct.pack('<3f',x,-20,0))
        self.cpu.mem_write(actor+0x48,struct.pack('<3f',x,-20,0))
        self.cpu.mem_write(actor+0xf0,struct.pack('<3f',0,-1,0))
        self.call(0x59e29,actor)
        self.write(self.scene+0x15d8+serial*4, actor)
        self.write(self.scene+0x16d8,serial+1)
        return actor

    def select_animation(self,mesh,key):
        require(mesh in self.animations,'Actual actor animation binding')
        source=self.animations[mesh]['sequences']
        require(key in source,f'Actual model animation key {key}')
        sequence=source[key]
        native=self.hooks.allocate(0x28)
        for offset,value in [(0,key),(4,sequence['frames']),(8,sequence['stride']),(12,sequence['samples'])]:self.write(native+offset,value)
        table=self.hooks.allocate((sequence['samples']+1)*4)
        self.write(native+0x20,table)
        tails={}
        for row in sequence['commands']:
            cmd=self.hooks.allocate(0x7c)
            self.write(cmd,row['kind']);self.write(cmd+4,row['tick'])
            for i,v in enumerate(row['arguments']):self.write(cmd+8+i*4,v)
            slot=native+0x24 if row['sample']<0 else table+row['sample']*4
            if slot in tails:self.write(tails[slot]+0x78,cmd)
            else:self.write(slot,cmd)
            tails[slot]=cmd
        self.write(mesh+0x38,native);self.write(mesh+0x34,key)
        self.write(mesh+0x40,0);self.write(mesh+0x50,0)
        self.animations[mesh]['active']=sequence
        self.animations[mesh]['bound_at']=self.tick

    def bridge_request(self,line,options=()):
        require(not options,'Persistent candidate bridge options')
        mode=self.anchor_mode if str(line[0]).startswith('anchor') else self.visibility_mode if line[0]=='visibility' else 'modified'
        process=self.anchor_control if mode!='modified' else self.bridge_process
        process.stdin.write(' '.join(map(str,line))+'\n');process.stdin.flush()
        raw=process.stdout.readline()
        require(raw,'Projection bridge ended unexpectedly')
        result=json.loads(raw)
        if process is self.anchor_control:
            require(not result['hook_enabled'],'Native control still patched')
            require(result['rollback_exact']==(mode=='rollback'),'Exact rollback control')
        return result

    def close(self):
        for process in (self.bridge_process,self.anchor_control):
            if process is None:continue
            process.stdin.close()
            process.wait(timeout=10)
            require(process.returncode==0,'Projection bridge exact rollback on exit')
            process.stdout.close();process.stderr.close()

    def native_screen(self,victim):
        model=self.read(victim+0x2dc)
        hidden=self.read(model+0x114)
        cached=bytes(self.cpu.mem_read(model+0x138,8))
        # Independent source-driver/mesh traversal oracle. Temporarily expose
        # only this fixture model; neither this pass nor its cache feeds popup.
        self.write(model+0x114,0)
        self.call(0x1d604,self.lens)
        self.call(0x47416,model)
        screen=list(struct.unpack('<2i',self.cpu.mem_read(model+0x138,8)))
        self.cpu.mem_write(model+0x138,cached);self.write(model+0x114,hidden)
        return screen

    def frame(self,tick,hidden):
        self.tick=tick
        for effect in list(self.effects):
            if self.call(0x8f392,self.attacker,effect):continue
            self.prepare(effect)
            self.call(0x4bdea,effect);self.call(0x4b4c8,effect)
        self.call(0x53fde,self.camera_manager)
        if self.read(self.camera_manager+4)==1:self.call(0x547d3,self.camera_manager)
        for mesh,row in list(self.animations.items()):
            if 'active' in row:self.call(0x3ea50,mesh)
        for victim in self.victims:
            if self.read(victim+0x350):
                self.call(0x64df4,victim,victim+0x350)
                self.call(0x8d769,0,victim+0x350)
                self.call(0x8c1eb,victim)
        screens={}
        visible=[]
        camera=list(struct.unpack('<16f',self.cpu.mem_read(self.camera+0x80,64)))
        require(all(math.isfinite(v) for v in camera),'Non-finite native skill camera; fixture is not valid coverage')
        if not self.camera_frames or self.camera_frames[-1]['matrix']!=camera:
            self.camera_frames.append(dict(tick=tick,matrix=camera))
        camera_probe=tick%5==0
        if camera_probe:
            self.cpu.mem_write(self.camera+0x80,struct.pack('<16f',1,0,0,0,0,0,-1,0,0,1,0,0,0,0,-300,1))
        for p in self.popups:
            if 'ended' in p:continue
            address=p['address'];mover=self.read(address+0xf8)
            alive=self.call(0x54ea0,mover)
            screen=None
            if alive:
                victim=p['victim'];model=self.read(victim+0x2dc)
                hide_now=hidden and tick%4!=0
                self.write(model+0x114,0xffffffff if hide_now else 0)
                if hide_now:
                    self.write(model+0x138,123);self.write(model+0x13c,45)
                if victim not in screens:screens[victim]=self.native_screen(victim)
                screen=screens[victim]
                vec=self.hooks.allocate(12);self.call(0x4edd1,mover,vec)
                offset=list(struct.unpack('<3f',self.cpu.mem_read(vec,12)))
            self.call(0xaa2d1,address)
            if not alive:p['ended']=tick;continue
            number=self.read(address+0xf4)
            actual=list(struct.unpack('<3f',self.cpu.mem_read(number+0x24,12)))
            if screen!=[-1,-1]:
                expected=[screen[0]+offset[0],screen[1]+offset[1]]
                require(all(abs(actual[i]-expected[i])<=1.01 for i in (0,1)),
                    f'Victim anchor mismatch tick={tick} popup={address:x}: {actual} != {expected}')
                visible.append(p)
            self.frames.append(dict(tick=tick,popup=address,victim=p['victim'],screen=screen,position=actual,hidden=hide_now,camera_probe=camera_probe))
        if screens:
            self.calls=[];self.call(0x8b34,self.ui)
            require(len(self.calls)==sum(len(str(p['damage'])) for p in visible),
                f'Native numeric digit count tick={tick}: {len(self.calls)}')
            self.frames[-1]['draw_count']=len(self.calls)
        self.cpu.mem_write(self.camera+0x80,struct.pack('<16f',*camera))
        return not self.call(0x1ff2,self.attacker+0x67c) and all('ended' in p for p in self.popups)

    def effect(self, resource):
        effect = self.hooks.allocate(0xc4)
        self.call(0x91750,effect,self.scene,0,8)
        self.call(0x92248,effect,resource)
        self.call(0x91910,effect,self.attacker,self.level)
        self.call(0x8f2e3,self.attacker,effect)
        return effect

    def prepare(self,effect):
        if effect in self.prepared or not self.read(effect+0x2c):
            return
        self.prepared.add(effect)
        for index in range(self.read(effect+0xb8)):
            entry=self.read(effect+0xb4)+index*20
            camera=self.call(0x9d071,0,self.read(entry+4))
            self.write(entry+8,camera)
        # Model resources are not rendered by this harness. Real actor head
        # records and real numeric BGR resources execute independently.

    def start(self, char_id=0, action=13):
        self.attacker = self.actor(char_id,1,-60)
        self.victims = [self.actor(7,2,30),self.actor(72,3,-40)]
        # Keep long multi-hit display cases on living, durable fixture targets.
        for victim in self.victims:self.call(0x8e20d,victim,1000000)
        self.write(self.scene+0x40,self.attacker)
        resources=setupCombatResources(self,self.data,scene=self.scene,actor=self.attacker,action=action)
        self.config=resources['config']
        values=value_data((self.data/'ValueData/0001.val').read_bytes())
        memory=self.hooks.allocate(len(values)*8)
        self.cpu.mem_write(memory,b''.join(struct.pack('<ii',k,v) for k,v in values.items()))
        self.write(self.config+0x1088,memory);self.write(self.config+0x108c,len(values))
        self.write(self.attacker+0x42c,action)
        self.write(self.attacker+0x43c,2)
        self.write(self.attacker+0x440,3)
        self.write(self.attacker+0x53c,2)
        self.write(self.scene+0x1754,2)
        self.call(0x8ebb1,self.attacker,action,self.attacker+0x6c4)
        row=self.call(0xb5967,self.config,action)
        target=self.call(0xb59f6,self.config,self.read(row+0x44))
        resource=self.read(target+0x20)
        self.effect(resource)
        return resource

    def _instruction(self,cpu,address,size,data):
        if STOP+0x400<=address<STOP+0x410:return
        if address==BASE+0xa9ef0 and hasattr(self,'popups'):
            self.popups.append(dict(address=cpu.reg_read(UC_X86_REG_ECX),damage=self.arg(0),victim=self.arg(1),tick=self.tick))
        if address==BASE+0x4c893 and any(p['address']==cpu.reg_read(UC_X86_REG_ECX) for p in self.popups):
            popup=cpu.reg_read(UC_X86_REG_ECX);number=self.read(popup+0xf4)
            if number:
                children=[];child=self.read(number+0x18)
                while child:
                    require(len(children)<16 and child not in children,'Bounded numeric digit children')
                    children.append(child);child=self.read(child+0x10)
                signed=lambda value:value if value<0x80000000 else value-0x100000000
                result=self.bridge_request(['visibility',signed(self.arg(0)),signed(self.read(popup+0xd0)),signed(self.read(number+0xd0)),len(children),*[signed(self.read(c+0xd0)) for c in children]])
                require(result['abi_error_bits']==0,'Compiled visibility hook ABI')
                self.write(number+0xd0,result['number'])
                for child,flag in zip(children,result['digits']):self.write(child+0xd0,flag)
        if address in (BASE+0x3ed6b,BASE+0x3ebbf) and hasattr(self,'animations'):
            self.select_animation(cpu.reg_read(UC_X86_REG_ECX),self.arg(0));self.ret(4);return
        if address==BASE+0x476a8 and hasattr(self,'animations'):
            cmd=self.arg(0);kind=self.read(cmd)
            if kind not in (9,11):self.ret(8,1);return
            self.model_commands.append(dict(tick=self.tick,kind=kind,method=self.read(cmd+8)))
        if address==BASE+0x91750 and hasattr(self,'effects'):
            obj=cpu.reg_read(UC_X86_REG_ECX)
            if obj not in self.effects:self.effects.append(obj)
        if address==BASE+0x91abf and hasattr(self,'effects'):
            effect=cpu.reg_read(UC_X86_REG_ECX)
            slot=self.arg(0)
            obj=self.read(effect+0x34)+slot*0x28
            op=self.read(obj)
            self.action_events.append(dict(tick=self.tick,effect=effect,slot=slot,opcode=op))
            # Execute native target/state/visibility/camera and damage actions.
            if op in (4,8,100,101,102,103,104,200,201,204,205,206,213,214,215,216,500,501,800):
                pass
            elif op in (208,209,300,301,302,303,304,305,306,307,308,309,310,502,503,504,507,600,601,602,700,701,702):
                self.leaf_opcodes[op]=self.leaf_opcodes.get(op,0)+1
                cpu.reg_write(UC_X86_REG_EIP,BASE+0x4b6ef)
                return
            else:
                raise ValueError(f'Unbound effect opcode {op} at tick {self.tick}')
        super()._instruction(cpu,address,size,data)


def replay(data,bridge,character,action,hidden=True,anchor_mode='modified',visibility_mode='modified'):
    q=CombatDamageReplay(data,bridge,anchor_mode,visibility_mode)
    try:
        resource=q.start(character,action)
        for tick in range(1000):
            if q.frame(tick,hidden):break
        else:raise ValueError(f'Incomplete native skill character={character} action={action}; events={q.action_events[-8:]}')
        require(q.popups,'Original attack produced no numeric damage')
        require(all(q.call(0x8e28c,v)>0 for v in q.victims),'Damage display target died before the script completed')
        require(all(p['victim'] in q.victims for p in q.popups),'Numeric popup bound to attacker or foreign actor')
        for path,digest in q.resource_hashes.items():
            require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,'Source resource drift')
        return dict(character=character,action=action,efs=resource,ticks=tick+1,
                    popups=q.popups,model_commands=q.model_commands,events=q.action_events,
                    camera_frames=q.camera_frames,frames=q.frames,resources=q.resource_hashes,
                    visual_audio_leaves=q.leaf_opcodes,native_steps=q.steps,
                    victim_serials=[q.read(v+0x424) for v in q.victims],victim_initial_hp=1000000,
                    victim_final_hp=[q.call(0x8e28c,v) for v in q.victims],game_started=False)
    finally:q.close()


def suite(data,bridge,input_bridge,report):
    from audit_damage_roster import audit
    from replay_combo_assist_chain import run_case
    from replay_rage_combo_assist import run as rage
    roster=audit(data)['roster']
    data=Path(data)
    values=value_data((data/'ValueData/0001.val').read_bytes())
    image=(data/'MCAlpha.dll').read_bytes();abi=(data/'Abi/0000.abi').read_bytes()
    rows={struct.unpack_from('<i',abi,o)[0]:abi[o:o+344] for o in range(8,len(abi),344)}
    result=dict(schema=1,cases=[],inputs=[],game_started=False,commercial_dll_loaded=False,
                boundaries=['Original ABI/ATT, battle-model command timelines, EFS control/target/damage actions, receive arithmetic, native cameras and numeric popup update/draw execute.',
                    'Source model timeline binding excludes geometry/bone deformation; only sound, mesh decorations, fades/curtains and texture upload are resource/device leaves.',
                    'Actor positions, two durable living enemies (HP1000000), controlled CRT random value, lens identity transform, and alternating hidden/stale model cache are fixture inputs.',
                    'Native camera resources advance every tick; every fifth tick adds a controlled camera cut for visible/offscreen recovery, then restores the source camera without changing its progression.',
                    'Native receive entry/state commit and complete numeric popup lifetime execute; complete hurt-animation/death and encounter AI state machines are not claimed.',
                    'Input grading and subsequent source-selected animation replay join at the unchanged ability ID; pre-grading whole-battle preparation remains an explicit input-fixture boundary.',
                    'Source-derived camera movement is executed; world scenery/skill particles, final GPU pixels and full battle acceptance are not claimed.'])
    for actor in roster:
        character=actor['char_id'];base=actor['abilities'][0]['action']
        links=struct.unpack_from('<3i',rows[base],0x48)
        inputs=[('F10',run_case(image,values,abi,input_bridge,60,'f10',True,data,base)),
                ('F11',rage(data,input_bridge,60,'f11',True,base))]
        selected={label:r['settlement']['selected_action'] for label,r in inputs}
        result['inputs'].extend(dict(character=character,route=label,report=r) for label,r in inputs)
        for label,action in [('normal',base),('F10',selected['F10']),('F11',selected['F11']),('linked-1',links[0]),('linked-2',links[1])]:
            case=replay(data,bridge,character,action)
            case['route']=label;result['cases'].append(case)
            report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
            print(f"COMBAT_CASE PASS character={character} route={label} action={action} hits={len(case['popups'])} frames={len(case['frames'])} cameras={len(case['camera_frames'])}",flush=True)
    require(len(result['cases'])==40 and len(result['inputs'])==16,'Complete eight-character route matrix')
    verify_report(result,report)
    print('COMBAT_DAMAGE PASS characters=8 main_routes=24 linked_routes=16 native_input_routes=16 game_started=false',flush=True)
    return result


def verify_report(result,report):
    require(json.loads(report.read_text(encoding='utf8'))==json.loads(json.dumps(result)),'Reopen combat report')
    roster={0,3,2,1,4,6,5,20}
    require(len(result['cases'])==40 and len(result['inputs'])==16,'Complete combat report')
    require({(c['character'],c['route']) for c in result['cases']}==
            {(c,r) for c in roster for r in ('normal','F10','F11','linked-1','linked-2')},'Unique route matrix')
    require({(c['character'],c['route']) for c in result['inputs']}==
            {(c,r) for c in roster for r in ('F10','F11')},'Unique native input matrix')
    for case in result['cases']:
        require(case['popups'] and all('ended' in p for p in case['popups']),'Unfinished popup lifetime')
        require(case['frames'] and any(f.get('draw_count') for f in case['frames']),'Missing numeric draws')
        require(any(f['hidden'] for f in case['frames']) and any(not f['hidden'] for f in case['frames']),'Missing hidden/visible cases')
        for path,digest in case['resources'].items():
            require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,'Combat report source drift')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--bridge',type=Path,required=True)
    p.add_argument('--action',type=int,default=13)
    p.add_argument('--character',type=int,default=0)
    p.add_argument('--report',type=Path)
    p.add_argument('--input-bridge',type=Path)
    p.add_argument('--suite',action='store_true')
    p.add_argument('--anchor-mode',choices=['modified','native','rollback'],default='modified')
    p.add_argument('--visibility-mode',choices=['modified','native','rollback'],default='modified')
    a=p.parse_args()
    if a.report:require(not a.report.exists() and not a.report.resolve().is_relative_to(a.data.resolve()),'New external report')
    if a.suite:
        require(a.report and a.input_bridge,'Suite report and owned input bridge required')
        suite(a.data,a.bridge,a.input_bridge,a.report)
    else:
        result=replay(a.data,a.bridge,a.character,a.action,anchor_mode=a.anchor_mode,visibility_mode=a.visibility_mode)
        if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
        print(f"COMBAT_CASE PASS character={a.character} action={a.action} hits={len(result['popups'])} frames={len(result['frames'])}")


if __name__=='__main__':
    main()
