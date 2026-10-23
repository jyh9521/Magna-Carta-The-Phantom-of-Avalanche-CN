"""Source-locked real ABI predicates and native combo settlement, without DLL load."""
from pathlib import Path
import argparse, hashlib, json, struct
from replay_combo_cue import ComboCueReplay, value_data, BASE, SCENE, ACTOR
from replay_native_title import STOP
from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_ECX, UC_X86_REG_EAX
ABI_SHA='4ec8bf4949f3a2cc62a15e0a7b0b57ab34fd641e05c60999c131703303fd0a85'
ATT_SHA='557dece3f750327e4826064e435951994241d87980a3a8ee5ed82f4b233f7916'

def native_call(replay, rva, this, *args):
    """Explicit x86 thiscall independent of replay.call's Python signature.

    This owns a separate stack from the settlement frame. Invoke between
    emulation slices, not recursively from an active Unicorn instruction hook.
    """
    sp=0x30010000
    replay.cpu.mem_write(sp,struct.pack('<'+'I'*(1+len(args)),STOP,*args))
    replay.cpu.reg_write(UC_X86_REG_ESP,sp)
    replay.cpu.reg_write(UC_X86_REG_ECX,this)
    replay.cpu.emu_start(BASE+rva,STOP,count=100000)
    if replay.cpu.reg_read(UC_X86_REG_EIP)!=STOP:
        raise ValueError('Native thiscall budget exhausted')
    return replay.cpu.reg_read(UC_X86_REG_EAX)

def resource_rows(data, expected_sha, count, version, stride):
    if hashlib.sha256(data).hexdigest()!=expected_sha:
        raise ValueError('Unsupported combat resource SHA256')
    if struct.unpack_from('<II',data)!=(count,version) or len(data)!=8+count*stride:
        raise ValueError('Unsupported combat resource layout')
    return data[8:]

def setupCombatResources(replay, data, scene=SCENE, actor=ACTOR, action=3):
    """Map source rows; native B5967/B59F6 and A40DF/A412D execute unchanged.

    Resource loading is a bounded setup boundary. The actor action slots are
    explicit input, while their getters and readiness predicates remain native.
    Compatible with ComboCueReplay and QueueReplay subclasses.
    """
    data=Path(data)
    abi=resource_rows((data/'Abi/0000.abi').read_bytes(),ABI_SHA,205,7,0x158)
    att=resource_rows((data/'Att/0000.att').read_bytes(),ATT_SHA,203,19,0x50)
    config=replay.hooks.allocate(0x1200)
    for field,count,raw in [(0x1078,205,abi),(0x1070,203,att)]:
        rows=replay.hooks.allocate(len(raw));replay.cpu.mem_write(rows,raw)
        replay.write(config+field,rows);replay.write(config+field+4,count)
    replay.write(BASE+0xf2428,config)
    for i in range(10):replay.write(actor+0x298+4*i,0xffffffff)
    replay.write(actor+0x298,action);replay.write(scene+0x1744,action)
    replay.write(actor+0x22c,0)
    original=replay.hooks.handle
    replay.hooks.handle=lambda address: False if address-BASE in (0xa40df,0xa412d) else original(address)
    # Remove older fixture resource boundaries when adapting a GUI fixture.
    if hasattr(replay,'stubs'):
        for r in (0xa40df,0xa412d,0xb5967,0xb59f6):replay.stubs.pop(BASE+r,None)
    return dict(config=config,abi=ABI_SHA,att=ATT_SHA,action=action)

def settle(replay, scene=SCENE, action=3, choose_action=False):
    """Execute original A4ECD scoring block against its original frame layout.

    Geometry, pre-scoring damage preparation and actor energy arithmetic precede
    this block; energy level 3 / consumed level 0 are explicit test inputs.
    """
    fp=0x3001e000;replay.cpu.reg_write(UC_X86_REG_EBP,fp);replay.cpu.reg_write(UC_X86_REG_ESP,fp-0x500)
    replay.write(fp-0x390,scene)
    replay.cpu.emu_start(BASE+0xa57a0,BASE+0xa58ba,count=100000)
    if replay.cpu.reg_read(UC_X86_REG_EIP)!=BASE+0xa58ba:raise ValueError('Native scoring budget exhausted')
    result=dict(perfect=replay.read(fp-0x298),success_count=replay.read(fp-0x2b4))
    if choose_action:
        # Native resource getter, with native thiscall ABI; call uses a different stack.
        row=native_call(replay,0xb5967,replay.read(BASE+0xf2428),action)
        replay.cpu.reg_write(UC_X86_REG_EBP,fp);replay.cpu.reg_write(UC_X86_REG_ESP,fp-0x500)
        replay.write(fp-0x30,row);replay.write(fp-0x44,3);replay.write(fp-0x158,0)
        replay.cpu.emu_start(BASE+0xa58ba,BASE+0xa5ef1,count=100000)
        if replay.cpu.reg_read(UC_X86_REG_EIP)!=BASE+0xa5ef1:raise ValueError('Native selection budget exhausted')
        result['selected_action']=replay.read(scene+0x1744)
        result['popup_kinds']=[p['kind'] for p in replay.hooks.popups]
    return result

def compare(data):
    data=Path(data);image=(data/'MCAlpha.dll').read_bytes();values=value_data((data/'ValueData/0001.val').read_bytes())
    runs=[]
    for ticks in [(12,22),(10,20),(11,21),(16,22)]:
        q=ComboCueReplay(image,values);setupCombatResources(q,data)
        presses=[q.press(0)]
        for tick in ticks:q.write(SCENE+0x1de0,tick);presses.append(q.press(tick*33))
        result=settle(q,choose_action=True)
        runs.append(dict(ticks=ticks,presses=presses,settlement=result,sounds=q.hooks.sounds))
    return dict(runs=runs,abi_sha256=ABI_SHA,att_sha256=ATT_SHA,predicate_stubs=False,game_started=False,dll_loaded=False,
                limits=['Native scoring/selection starts at A57A0, not complete A4ECD geometry/damage preparation.','Allocation, popup construction and GPU/audio resource leaves use owned shims.'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('Report must be a new path')
    r=compare(a.data);a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
    print('NATIVE_COMBO_SCORING PASS baseline=nonperfect modified=perfect predicates=native game_started=false dll_loaded=false')
