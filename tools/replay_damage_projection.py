"""Source-bound offline replay of unsupported D3D raster queries; no DLL is loaded."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

DRIVER_SHA = '00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29'

def require(value, message):
    if not value:
        raise ValueError(message)

def verify(engine_path, driver_path):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EBP
    engine = engine_path.read_bytes()
    if hashlib.sha256(engine).hexdigest() != '7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e':
        raise ValueError('Unsupported complete engine SHA256')
    source = driver_path.read_bytes()
    if hashlib.sha256(source).hexdigest() != DRIVER_SHA:
        raise ValueError('Unsupported complete D3D driver SHA256')
    p = pefile.PE(data=source)
    data = p.get_memory_mapped_image()
    ep = pefile.PE(data=engine).get_memory_mapped_image()
    sites = {0x474cf: 'ff9294030000', 0x474ec: 'ff92b4010000', 0x47509: 'ff92a4010000'}
    for rva, code in sites.items():
        if ep[rva:rva+6].hex() != code:
            raise ValueError('Unsupported engine projection call')
    base = p.OPTIONAL_HEADER.ImageBase
    table = 0x1a5a8
    pointers = {slot:struct.unpack_from('<I', data, table+slot)[0] for slot in [0x1a4,0x1b4,0x394]}
    if pointers != {0x1a4:base+0x9b8c, 0x1b4:base+0x80a4, 0x394:base+0x1897c}:
        raise ValueError('Unsupported driver raster vtable')
    cpu=Uc(UC_ARCH_X86,UC_MODE_32)
    cpu.mem_map(base, 0x2c000);cpu.mem_write(base,data)
    cpu.mem_map(0x20000000,0x2000);cpu.mem_map(0x40000000,0x10000);cpu.mem_map(0x60000000,0x1000)
    object=0x20000000;output=0x20001000;stack=0x4000f000;stop=0x60000000
    def run(slot,name,raw):
        cpu.mem_write(output,raw)
        cpu.mem_write(stack,struct.pack('<III',stop,name,output))
        cpu.reg_write(UC_X86_REG_ECX,object);cpu.reg_write(UC_X86_REG_ESP,stack)
        cpu.emu_start(pointers[slot],stop,count=100)
        return bytes(cpu.mem_read(output,len(raw)))
    float_seed=struct.pack('<4f',123,456,789,12)
    float_result=run(0x1b4,0xb07,float_seed)
    bool_result=run(0x1a4,0xb08,b'\x7f')
    require(float_result==float_seed and bool_result==b'\x7f', 'Unsupported native query behavior')
    # Execute the actual built-in RH perspective generator, including native x87 FSINCOS.
    import math
    cpu.mem_write(stack,struct.pack('<II4f',stop,output,math.pi/4,.75,1,1000))
    cpu.reg_write(UC_X86_REG_ESP,stack)
    cpu.emu_start(base+0xc765,stop,count=150)
    matrix=struct.unpack('<16f',cpu.mem_read(output,64))
    def project_z(z):
        return matrix[10]*z+matrix[14], matrix[11]*z+matrix[15]
    near_z,near_w=project_z(-1);far_z,far_w=project_z(-1000)
    require(abs(near_z)<1e-5 and abs(far_z-far_w)<.001, 'Native projection depth mismatch')
    # Native LoadMatrix identifies the two source locations before SetTransform.
    require(bytes.fromhex('83c05c50') in data[0x359c:0x35cc], 'Native modelview source mismatch')
    require(bytes.fromhex('059c00000050') in data[0x35ce:0x3605], 'Native projection source mismatch')
    # Replay the actual consumer's FTOL, success branch, Y inversion and object writes.
    from replay_native_title import FTOL_SHIM
    cpu.mem_map(0x52000000,0x10b000);cpu.mem_write(0x52000000,ep)
    cpu.mem_write(stop+0x100,FTOL_SHIM)
    cpu.mem_write(0x520bd31c,struct.pack('<I',stop+0x100))
    cpu.mem_write(0x520f1b4c,struct.pack('<I',600))
    consumer=[]
    for x,y in [(0,0),(600,450)]:
        frame=stack-0x100
        cpu.mem_write(frame-0x58,struct.pack('<I',object))
        cpu.mem_write(frame-0x54,struct.pack('<4f',x,y,0,1))
        cpu.mem_write(frame-0x44,struct.pack('<I',1))
        cpu.reg_write(UC_X86_REG_EBP,frame);cpu.reg_write(UC_X86_REG_ESP,frame-0x100)
        cpu.emu_start(0x5204750f,0x52047572,count=150)
        consumer.append(list(struct.unpack('<2i',cpu.mem_read(object+0x138,8))))
    require(consumer==[[0,600],[600,150]], 'Native coordinate consumer mismatch')
    return dict(native_coordinate_consumer=dict(rva='0x4750f',baseline=consumer[0],modified=consumer[1]),engine_sha256=hashlib.sha256(engine).hexdigest(), driver_sha256=DRIVER_SHA,
        call_sites={hex(k):v for k,v in sites.items()}, driver_vtable={hex(k):hex(v-base) for k,v in pointers.items()},
        native_float_query=dict(name='0xb07',input=[123,456,789,12],output=list(struct.unpack('<4f',float_result)),untouched=True),
        native_bool_query=dict(name='0xb08',input=127,output=bool_result[0],untouched=True),
        native_perspective=dict(generator_rva='0xc765',matrix=matrix,near_clip=[near_z,near_w],far_clip=[far_z,far_w],z_range='0 <= clip_z <= clip_w'),
        matrix_sources=dict(modelview='driver+0x5c',projection='driver+0x9c',native_load_rva='0x356a'),
        root_cause='D3D raster position and raster-valid queries leave native caller outputs uninitialized.',
        game_started=False, dll_loaded=False, evidence='Actual PE instructions executed only in Unicorn; not game-render acceptance.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine',type=Path,required=True);p.add_argument('--driver',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    for source in (a.engine,a.driver):
        if a.report.resolve()==source.resolve() or (a.report.exists() and a.report.samefile(source)):
            p.error('Report must differ from source inputs')
    result=verify(a.engine,a.driver)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print('DAMAGE_NATIVE_REPLAY PASS actual_pe=true raster_float_0xb07=untouched raster_valid_0xb08=untouched game_started=false dll_loaded=false')
