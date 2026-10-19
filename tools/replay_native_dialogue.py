"""Source-locked offline dialogue input and pixel-reveal replay; no DLL load/game launch."""
from pathlib import Path
import argparse, hashlib, json, struct
from replay_native_title import NativeTitle, BASE, BUTTON, STOP, SHIM, SUPPORTED_SHA, _require
from replay_native_keyboard import NativeKeyboard

LOCALIZED_SHA='7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e'
TEXT_SHA='1902718249d9783d5035c6640c101916030029cdd62930f03be5261fdaa07928'
def admit(image):
    digest=hashlib.sha256(image).hexdigest()
    _require(digest in (SUPPORTED_SHA,LOCALIZED_SHA),'Unsupported full sample digest')
    pe=struct.unpack_from('<I',image,60)[0];opt=pe+24
    sections=opt+struct.unpack_from('<H',image,pe+20)[0]
    executable=[]
    for i in range(struct.unpack_from('<H',image,pe+6)[0]):
        pos=sections+i*40
        if struct.unpack_from('<I',image,pos+36)[0]&0x20000000:
            virtual,rva,size,offset=struct.unpack_from('<IIII',image,pos+8)
            executable.append((rva,size,hashlib.sha256(image[offset:offset+size]).hexdigest()))
    _require(executable==[(0x1000,770048,TEXT_SHA)],'Executable section differs')
    return digest

MARKER=SHIM+0x100
LABEL=0x20007000
FONT=0x20008000
NODE=0x20009000

class Dialogue(NativeKeyboard):
    def __init__(self,image,modified=False,full=False):
        digest=admit(image)
        super().__init__(image)
        self.modified=modified; self.active=False; self.calls=0; self.seen=[];self.full=full
        self.write(BUTTON,BASE+0xbfcec);self.write(BUTTON+0x17c,BUTTON)
        self.write(BUTTON+0x190,2);self.write(BUTTON+0x194,1)
        self.write(BUTTON+0x1bc,1);self.write(BUTTON+0x1cc,5);self.write(BUTTON+0x19c,0)
        self.write(BUTTON+0x1ec,1);self.write(BUTTON+0x1f4,NODE);self.write(NODE,LABEL)
        self.write(LABEL+0x120,FONT);self.write(LABEL+0x12c,5);self.write(LABEL+0x130,22)
        self.write(FONT+0x1c,640)
        self.cpu.mem_write(MARKER,b'\x90')
    def _instruction(self,cpu,address,size,user):
        ecx,esp,eip,eax=self.regs
        if address==BASE+0x5c277:
            sp=cpu.reg_read(esp);sender=self.read(sp+4);event=self.read(sp+8)
            self.seen.append(event)
            if self.modified and sender==BUTTON and event in (20,59) and self.read(BUTTON+0x190)==2:
                self.active=True;self.saved_sp=sp;self.saved_speed=self.read(BUTTON+0x1cc)
                self.write(BUTTON+0x1cc,32767)
                self._next();return
        if address==MARKER:
            if self.read(BUTTON+0x190)==2 or (self.read(BUTTON+0x190)==4 and self.read(BUTTON+0x1bc)):
                self._next();return
            self.write(BUTTON+0x1cc,self.saved_speed)
            cpu.reg_write(eip,self.read(self.saved_sp));cpu.reg_write(esp,self.saved_sp+20);cpu.reg_write(eax,1);self.active=False;return
        if address==BASE+0xb7ceb:
            raise AssertionError('Unexpected old title listener')
        NativeTitle._instruction(self,cpu,address,size,user)
    def _next(self):
        ecx,esp,eip,eax=self.regs
        self.calls+=1;_require(self.calls<=4096,'Reveal budget')
        self.write(self.saved_sp-4,MARKER);self.cpu.reg_write(esp,self.saved_sp-4)
        self.cpu.reg_write(ecx,BUTTON);self.cpu.reg_write(eip,BASE+0x5b9af)
    def input(self,kind,counter):
        if kind=='space':return self.keyboard(0,32,counter)
        return self.dispatch(counter)

class LongDialogue(Dialogue):
    """Actual native wrap/control-code code; explicit synthetic graphics/CRT boundaries."""
    def __init__(self,image,text=b'ABCDEFGHIJKL',full=True):
        super().__init__(image,True)
        self.heap=0x2000a000;self.labels=[]
        self.write(BASE+0xbd330,MARKER+0x140)
        self.cpu.mem_map(0x21000000,0x100000)
        self.heap=0x21000000
        self.cpu.mem_write(0x20004000,text+b'\0')
        self.write(BUTTON+0x1e0,0x20004000);self.write(BUTTON+0x1e4,len(text));self.write(BUTTON+0x19c,0x20004000)
        self.write(BUTTON+0x1bc,0);self.write(BUTTON+0x1a4,0);self.write(BUTTON+0x1a8,0)
        self.write(BUTTON+0x1b4,56);self.write(BUTTON+0x1b8,22 if full else 1000)
        self.write(BUTTON+0x1d4,0x20005000);self.write(0x20005000,0x20005100);self.write(0x20005118,MARKER+0x100)
        self.write(BASE+0xf22a8,0x20005200);self.write(0x2000522c,0x20005300)
        self.cpu.mem_write(MARKER+0x120,bytes.fromhex('d9eec20400')) # fldz; ret 4 (owned depth boundary)
    def string(self,p):
        result=bytearray()
        while self.cpu.mem_read(p+len(result),1)!=b'\0':
            result+=self.cpu.mem_read(p+len(result),1)
            _require(len(result)<4096,'String bound')
        return bytes(result)
    def _instruction(self,cpu,address,size,user):
        ecx,esp,eip,eax=self.regs;sp=cpu.reg_read(esp)
        def ret(value=0,pop=0):
            cpu.reg_write(eax,value);cpu.reg_write(eip,self.read(sp));cpu.reg_write(esp,sp+4+pop)
        if address==MARKER+0x140:ret(int(self.string(self.read(sp+4))));return
        if address==BASE+0xb8b5a:
            n=self.read(sp+4);value=self.heap;self.heap+=(n+15)&~15;_require(self.heap<0x21100000,'Allocation budget');ret(value);return
        if address==BASE+0xb8b66:ret(len(self.string(self.read(sp+4))));return
        if address==BASE+0xb8b4e:
            dest,val,count=[self.read(sp+k) for k in [4,8,12]];cpu.mem_write(dest,bytes([val&255])*count);ret(dest);return
        if address==BASE+0xb8b54:
            dest,src,count=[self.read(sp+k) for k in [4,8,12]];cpu.mem_write(dest,bytes(cpu.mem_read(src,count)));ret(dest);return
        if address in [BASE+0xb8a86]:ret();return
        if address==BASE+0x1ee51:
            result=self.read(sp+4);text=self.string(self.read(sp+8));self.write(result,len(text)*14);self.write(result+4,22);ret(result,8);return
        if address==BASE+0x45040:
            obj=cpu.reg_read(ecx);text=self.string(self.read(sp+4));self.labels.append(text.decode('ascii'));self.write(obj+0x120,FONT);self.write(FONT+0x1c,len(text)*14);self.write(FONT+0x20,22);ret(obj,12);return
        if address==BASE+0x4e7a0:cpu.reg_write(eip,MARKER+0x120);return
        if address==MARKER+0x120 or address==MARKER+0x122:return
        if address==BASE+0x4d480:ret(0,12);return
        if address==BASE+0x1af3:
            self.write(NODE,self.read(sp+4));self.write(BUTTON+0x1f4,NODE);self.write(BUTTON+0x1ec,1);ret(NODE,4);return
        if address==MARKER+0x100:ret();return
        super()._instruction(cpu,address,size,user)

def run(image):
    cases=[]
    for kind in ['mouse','space']:
        for modified in [False,True]:
            n=Dialogue(image,modified)
            for c in [1,2,-1]:n.input(kind,c)
            expected=3 if modified else 2
            _require(n.read(BUTTON+0x190)==expected,'Input/reveal phase')
            _require(n.read(LABEL+0x12c)==(639 if modified else 5),'Native pixel prefix')
            _require(n.read(BUTTON+0x1cc)==5,'Speed restoration')
            record={'input':kind,'modified_adapter':modified,'phase':expected,'visible_pixel_prefix':n.read(LABEL+0x12c),'events':n.seen,'native_reveal_calls':n.calls,'native_instructions':n.instructions}
            if modified:
                for c in [1,2,-1]:n.input(kind,c)
                _require(n.read(BUTTON+0x190)==6,'Separate second input must use native advance')
                record['second_input_phase']=6
            cases.append(record)
    for text,full in [(b'ABCDEFGHIJKL',True),(b'AB$nCD$d12EF',False)]:
        n=LongDialogue(image,text,full)
        for c in [1,2,-1]:n.input('space',c)
        _require(n.read(BUTTON+0x190)==(4 if full else 3),'Native long/control phase')
        _require(n.labels==(['ABCD'] if full else ['AB','CD','EF']),'Native wrapping/control labels')
        _require(n.read(BUTTON+0x198)==(4 if full else len(text)),'Native source cursor')
        cases.append({'input':'space','case':'native_long_boundary' if full else 'native_control_codes','phase':n.read(BUTTON+0x190),'labels':n.labels,'source_cursor':n.read(BUTTON+0x198),'source_length':len(text),'native_reveal_calls':n.calls,'native_instructions':n.instructions,'boundary_services':'synthetic font metrics, labels, allocation, CRT and transform'})
    return {'schema':1,'sample_sha256':admit(image),'executable_section_sha256':TEXT_SHA,'cases':cases,'game_started':False,'modified_adapter':'owned Python boundary trampoline; compiled hook is separately covered by dialogue_reveal_fixture','not_proven':['game renderer pixels','actual game-resource layout','physical input hardware']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--sample',type=Path,required=True);p.add_argument('--report',type=Path);a=p.parse_args()
    if a.report and (a.report.resolve()==a.sample.resolve() or (a.report.exists() and a.report.samefile(a.sample))):
        p.error('Report must differ from the sample path')
    image=a.sample.read_bytes();report=run(image)
    _require(hashlib.sha256(a.sample.read_bytes()).hexdigest()==report['sample_sha256'],'Source changed')
    if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('NATIVE_DIALOGUE_REPLAY PASS cases=6 mouse_space=original_dispatch baseline_phase=2 modified_phase=3 prefix=5_to_639 second_input=phase6 source_unchanged=true game_started=false')
if __name__=='__main__':main()
