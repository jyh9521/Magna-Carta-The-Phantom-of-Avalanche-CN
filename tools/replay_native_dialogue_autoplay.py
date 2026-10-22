"""Bounded no-input dialogue instruction replay; no DLL load or game process."""
from pathlib import Path
import argparse
import hashlib
import json
from replay_native_dialogue import LongDialogue, admit, MARKER
from replay_native_title import NativeTitle
from resource_fpb import parse

def glyphs(text):
    count=0;offset=0
    while offset<len(text):
        count+=1;offset+=2 if text[offset]>=128 else 1
    return count

class Scroll(LongDialogue):
 def __init__(self,img,text):
  super().__init__(img,text,True);self.modified=False;self.cpu.mem_write(BASE+0x1f000,b'\x00')
  self.cpu.mem_write(BUTTON+0x1e8,b'\0'*16);self.write(BUTTON+0x1b8,44)
  self.write(BASE+0xbd24c,MARKER+0x160);self.write(BASE+0xbd344,MARKER+0x180)
  self.write(MARKER+0x200,MARKER+0x190)
 def _instruction(self,cpu,address,size,user):
  ecx,esp,eip,eax=self.regs;sp=cpu.reg_read(esp)
  def ret(v=0,pop=0):cpu.reg_write(eax,v);cpu.reg_write(eip,self.read(sp));cpu.reg_write(esp,sp+4+pop)
  if address==BASE+0x1af3:return NativeTitle._instruction(self,cpu,address,size,user)
  if address==MARKER+0x160:
   v=self.heap;self.heap+=32;ret(v);return
  if address==MARKER+0x180:ret();return
  if address==MARKER+0x190:ret(0,4);return
  if address==BASE+0x4d480:
   obj=cpu.reg_read(ecx);cpu.mem_write(obj+0x24,bytes(cpu.mem_read(sp+4,12)));ret(0,12);return
  if address==BASE+0x1ee51:
   result=self.read(sp+4);text=self.string(self.read(sp+8));self.write(result,glyphs(text)*14);self.write(result+4,22);ret(result,8);return
  if address==BASE+0x45040:
   obj=cpu.reg_read(ecx);text=self.string(self.read(sp+4));self.labels.append(text.decode('latin1'));font=self.heap;self.heap+=64
   self.write(obj,MARKER+0x200);self.write(obj+0x120,font);self.write(font+0x18,22);self.write(font+0x1c,glyphs(text)*14);self.write(font+0x20,22);ret(obj,12);return
  super()._instruction(cpu,address,size,user)


from replay_native_title import BASE, BUTTON, STOP, _require


def scroll_case(image, text, resource):
    n=Scroll(image,text)
    phases=[]
    for tick in range(20000):
        ecx,esp,eip,_=n.regs;stack=0x3001f000
        n.write(stack,STOP);n.cpu.reg_write(esp,stack);n.cpu.reg_write(ecx,BUTTON)
        n.cpu.emu_start(BASE+0x5b1ef,STOP,count=100000)
        _require(n.cpu.reg_read(eip)==STOP and n.cpu.reg_read(esp)==stack+4,'Scroll ABI or instruction budget')
        phase=n.read(BUTTON+0x190)
        if not phases or phases[-1]['phase']!=phase:phases.append({'tick':tick,'phase':phase})
        if phase==6:break
    _require(phase==6,'Scroll never completed')
    labels=''.join(n.labels).encode('latin1')
    _require(labels==text.replace(b'$n',b''),'Scrolling omitted source text')
    _require(not n.seen,'Unexpected autonomous input')
    return {'resource':resource,'source_sha256':hashlib.sha256(text).hexdigest(),
            'source_length':len(text),'label_count':len(n.labels),
            'reconstructed_label_sha256':hashlib.sha256(labels).hexdigest(),
            'phase_transitions':phases,'native_instructions':n.instructions,
            'inputs':0,'labels_complete':True,'runtime_native_text_step':True}


def voice_tail_case(image, modified, manual=False):
    """Execute the real native completion handler against an owned 400-tick voice boundary."""
    n=LongDialogue(image,b'AB',False)
    n.modified=False
    n.write(BUTTON+0x190,3);n.write(BUTTON+0x194,1);n.write(BUTTON+0x1d0,0)
    held=0
    for tick in range(500):
        if manual and tick==10:
            n.input('space',-1)
        if n.read(BUTTON+0x190)==6:break
        ecx,esp,eip,_=n.regs;stack=0x3001f000
        n.write(stack,STOP);n.cpu.reg_write(esp,stack);n.cpu.reg_write(ecx,BUTTON)
        hold=modified and tick<400
        if hold:n.write(BUTTON+0x1d0,0xffffffff);held+=1
        n.cpu.emu_start(BASE+0x5c13e,STOP,count=100000)
        if hold:n.write(BUTTON+0x1d0,0)
        _require(n.cpu.reg_read(eip)==STOP and n.cpu.reg_read(esp)==stack+4,'Voice-tail native ABI')
        if n.read(BUTTON+0x190)==6:break
    expected=10 if manual else (400 if modified else 0)
    _require(tick==expected and n.read(BUTTON+0x190)==6,'Voice-tail end timing')
    return {'modified_adapter':modified,'manual_confirmation':manual,'voice_finishes_tick':400,
            'dialogue_ends_tick':tick,'held_ticks':held,'native_instructions':n.instructions,
            'voice_boundary':'owned playback status, not captured original audio'}


def run(image, resources=None):
    digest = admit(image)
    cases = []
    for text, delay in [(b'ABCDEFGHIJKLMNOP', 0), (b'ABCDEFGHIJKLMNOP' * 20, 0),
                        (b'AB$nCD$d12EF', 3), (b'AB$nCD', -1)]:
        n = LongDialogue(image, text, False)
        n.modified = False
        n.write(BUTTON + 0x1b8, 1000000)  # Unbounded owned viewport; scrolling is tested separately.
        n.write(BUTTON + 0x1d0, delay)
        phase3 = None
        end = None
        phases = []
        for tick in range(10000):
            ecx, esp, eip, _ = n.regs
            stack = 0x3001f000
            n.write(stack, STOP)
            n.cpu.reg_write(esp, stack)
            n.cpu.reg_write(ecx, BUTTON)
            # Actual native state dispatcher, reveal/layout and completion timer.
            # Generic UI traversal is outside this test and is not simulated.
            n.cpu.emu_start(BASE + 0x5b1ef, STOP, count=100000)
            _require(n.cpu.reg_read(eip) == STOP and n.cpu.reg_read(esp) == stack + 4,
                     'Native instruction budget or ABI restoration failed')
            phase = n.read(BUTTON + 0x190)
            if not phases or phases[-1]['phase'] != phase:
                phases.append({'tick': tick, 'phase': phase})
            if phase == 3 and phase3 is None:
                phase3 = tick
                _require(n.read(BUTTON + 0x198) == len(text), 'Premature native source completion')
                _require(n.read(BUTTON + 0x1bc) == 0, 'Premature native pixel completion')
            if phase == 6:
                end = tick
                break
            if delay == -1 and phase3 is not None and tick >= phase3 + 30:
                break
        expected = text.replace(b'$n', b'').replace(b'$d12', b'').decode('ascii')
        _require(''.join(n.labels) == expected, 'Missing text in native labels')
        _require(not n.seen and n.calls == 0, 'Input/instant-reveal path unexpectedly entered')
        _require(phase3 is not None, 'Native text never completed')
        _require((end is None and delay == -1) or end == phase3 + delay + 1,
                 'Native automatic-end countdown changed')
        cases.append({'source_length': len(text), 'label_text': ''.join(n.labels),
                      'phase_transitions': phases, 'automatic_delay': delay,
                      'completed_tick': phase3, 'ended_tick': end,
                      'input_events': n.seen, 'instant_reveal_calls': n.calls,
                      'native_instructions': n.instructions})
    scrolling=[scroll_case(image,b'ABCDEFGHIJKLMNOPQRSTUVWX','owned_ascii')]
    if resources:
        rows=[]
        for path in sorted(resources.glob('*.fpb')):
            for ordinal,(tag,raw) in enumerate(parse(path.read_bytes())):
                if raw and b'$' not in raw.replace(b'$n',b''):
                    rows.append((len(raw),path.name,ordinal,tag,raw))
        for _,name,ordinal,tag,raw in sorted(rows,reverse=True)[:5]:
            scrolling.append(scroll_case(image,raw,f'{name}:{ordinal}:{tag}'))
    return {'voice_tail':[voice_tail_case(image,False),voice_tail_case(image,True),voice_tail_case(image,True,True)],'scrolling':scrolling,'schema': 1, 'sample_sha256': digest, 'cases': cases,
            'game_started': False, 'source_unchanged': True,
            'not_proven': ['original scene/voice timing', 'full UI update traversal',
                           'player-reported missing scene line']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sample', type=Path, required=True)
    p.add_argument('--report', type=Path)
    p.add_argument('--resources', type=Path)
    a = p.parse_args()
    if a.report and (a.report.resolve() == a.sample.resolve() or
                     (a.report.exists() and a.report.samefile(a.sample))):
        p.error('Report must differ from sample')
    report = run(a.sample.read_bytes(),a.resources)
    _require(hashlib.sha256(a.sample.read_bytes()).hexdigest() == report['sample_sha256'], 'Source changed')
    if a.report:
        a.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(f'NATIVE_DIALOGUE_AUTOPLAY PASS cases=4 scrolling={len(report["scrolling"])} voice_tail=baseline0_modified400_manual10 inputs=0 labels=complete terminal_pixels=complete delay=0_3_manual source_unchanged=true game_started=false')


if __name__ == '__main__':
    main()
