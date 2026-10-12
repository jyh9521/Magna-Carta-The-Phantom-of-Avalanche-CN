"""Byte-preserving font reader and static glyph checks for the observed MCAlpha layout."""
import argparse
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import struct


@dataclass(frozen=True)
class Font:
    header: bytes
    advances: bytes
    bitmap: bytes

    @property
    def height(self): return struct.unpack_from('<H',self.header,88)[0]
    @property
    def pitch(self): return self.header[90]
    @property
    def count(self): return struct.unpack_from('<I',self.header,92)[0]
    @property
    def glyph_bytes(self): return self.height*self.pitch

    def glyph(self,index):
        if type(index)!=int or not 0<=index<self.count: raise ValueError('glyph index outside font')
        start=index*self.glyph_bytes
        return self.bitmap[start:start+self.glyph_bytes]

    def width(self,index):
        self.glyph(index)
        return self.advances[index] if self.advances else self.height

    def pixels(self,index):
        data=self.glyph(index);width=self.width(index)
        return [[(data[y*self.pitch+x//8]>>(x%8))&1 for x in range(width)] for y in range(self.height)]

    def replace_glyph(self,index,data):
        self.glyph(index)
        if len(data)!=self.glyph_bytes: raise ValueError('replacement glyph length mismatch')
        start=index*self.glyph_bytes
        return replace(self,bitmap=self.bitmap[:start]+bytes(data)+self.bitmap[start+self.glyph_bytes:])

    def to_bytes(self):
        data=self.header+self.advances+self.bitmap
        parse(data)
        return data


def parse(data):
    if len(data)<100: raise ValueError('truncated font header')
    header=bytes(data[:100]);height=struct.unpack_from('<H',header,88)[0];pitch=header[90]
    count,size=struct.unpack_from('<II',header,92)
    if not 1<=height<=pitch*8 or not 1<=count<=65536: raise ValueError('unsupported font dimensions/count')
    if count*height*pitch!=size: raise ValueError('font bitmap size mismatch')
    width_count=count if header[42] else 0
    if len(data)!=100+width_count+size: raise ValueError('font length mismatch')
    advances=bytes(data[100:100+width_count])
    if advances and max(advances)>pitch*8: raise ValueError('advance exceeds stored row')
    return Font(header,advances,bytes(data[100+width_count:]))


def native_slot(data):
    if not data or data[0]<0x20: raise ValueError('control or empty input requires separate interpretation')
    lead=data[0]
    if lead<0xa4: return 'Eng',lead-0x20,1
    if len(data)<2: raise ValueError('truncated native pair')
    code=lead*256+data[1]
    if lead<0xb0: return 'Eng',code-0xa3a0,2
    if lead<0xca: return 'Kor',code-0xb0a0,2
    return 'Chi',code-0xcaa0,2


def coverage(text,fonts):
    rows=[]
    for char in text:
        row=dict(character=char,codepoint=f'U+{ord(char):04X}')
        try: encoded=char.encode('cp949')
        except UnicodeEncodeError:
            row['status']='not_cp949';rows.append(row);continue
        row['encoded_hex']=encoded.hex()
        try:
            family,index,consumed=native_slot(encoded)
            row.update(family=family,index=index,consumed_bytes=consumed)
            if consumed!=len(encoded): row['status']='engine_byte_length_mismatch'
            else:
                font=fonts.get(family)
                if font is None: raise ValueError('font family missing')
                pixels=font.pixels(index)
                ink=sum(sum(line) for line in pixels)
                row.update(advance=font.width(index),ink_pixels=ink)
                row['status']='supported' if ink or char==' ' else 'empty_glyph'
        except ValueError as error: row.update(status='unsupported_native_slot',reason=str(error))
        rows.append(row)
    return rows


def inspect(source,text='中文测试'):
    source=Path(source)
    files=sorted(source.glob('*.dat'));rows=[];sets={0:{},1:{}}
    expected={f'{family}{i}.dat' for family in ['Eng','Kor','Chi'] for i in [0,1]}
    if {p.name for p in files}!=expected: raise ValueError('expected two observed font sets')
    for path in files:
        data=path.read_bytes();font=parse(data)
        if font.to_bytes()!=data: raise ValueError('font roundtrip mismatch')
        family,index=path.stem[:-1],int(path.stem[-1]);sets[index][family]=font
        rows.append(dict(name=path.name,size=len(data),sha256=hashlib.sha256(data).hexdigest(),
            glyph_count=font.count,height=font.height,pitch=font.pitch,
            width_table=bool(font.advances),bitmap_offset=100+len(font.advances),
            header_base_hint=hex(struct.unpack_from('<H',font.header,86)[0]),roundtrip_exact=True))
    return dict(schema=1,files=rows,text_checks={str(i):coverage(text,fonts) for i,fonts in sets.items()},
                evidence_type='static_file_and_engine_layout',game_started=False,in_game_display_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--text',default='中文测试');a=p.parse_args()
    if a.report.exists(): raise ValueError('report already exists')
    report=inspect(a.source,a.text);a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open('x',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=True,indent=2)
    print(f'FONT_ROUNDTRIP_PASS files={len(report["files"])} original_files_changed=false game_started=false')
