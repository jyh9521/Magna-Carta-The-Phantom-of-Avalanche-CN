"""Strict DLGTEMPLATEEX parsing and Unicode text-only rebuilding."""
import struct


def atom(data, pos):
    start=pos
    if pos+2>len(data):raise ValueError('truncated dialog atom')
    value=struct.unpack_from('<H',data,pos)[0];pos+=2
    if value==0:return '',pos
    if value==0xffff:
        if pos+2>len(data):raise ValueError('truncated dialog ordinal')
        return dict(ordinal=struct.unpack_from('<H',data,pos)[0]),pos+2
    while value:
        if pos+2>len(data):raise ValueError('unterminated dialog UTF-16 atom')
        value=struct.unpack_from('<H',data,pos)[0];pos+=2
    try:text=data[start:pos-2].decode('utf-16le')
    except UnicodeDecodeError as e:raise ValueError('invalid dialog Unicode') from e
    return text,pos


def pack_atom(value):
    if isinstance(value,str) and '\0' not in value:return value.encode('utf-16le')+b'\0\0'
    if (isinstance(value,dict) and set(value)=={'ordinal'} and type(value['ordinal']) is int
            and 0<=value['ordinal']<=65535):return struct.pack('<HH',65535,value['ordinal'])
    raise ValueError('invalid dialog atom')


def parse(data):
    if len(data)<26:raise ValueError('truncated extended dialog header')
    head=struct.unpack_from('<HHIIIHhhhh',data)
    if head[0:2]!=(1,65535):raise ValueError('unsupported dialog template')
    count=head[5];pos=26;menu,pos=atom(data,pos);klass,pos=atom(data,pos);title,pos=atom(data,pos)
    font=None
    if head[4]&0x40:
        if pos+6>len(data):raise ValueError('truncated dialog font')
        font_head=data[pos:pos+6];pos+=6;face,pos=atom(data,pos)
        if not isinstance(face,str):raise ValueError('dialog font face is an ordinal')
        font=dict(header_hex=font_head.hex(),face=face)
    rows=[]
    for ordinal in range(count):
        aligned=(pos+3)&~3
        if any(data[pos:aligned]):raise ValueError('unknown nonzero dialog alignment')
        pos=aligned
        if pos+24>len(data):raise ValueError('truncated dialog control')
        header=data[pos:pos+24];pos+=24;cl,pos=atom(data,pos);label,pos=atom(data,pos)
        if pos+2>len(data):raise ValueError('truncated dialog control creation data')
        size=struct.unpack_from('<H',data,pos)[0];pos+=2
        if pos+size>len(data):raise ValueError('truncated dialog extra payload')
        extra=data[pos:pos+size];pos+=size
        rows.append(dict(ordinal=ordinal,header_hex=header.hex(),identifier=struct.unpack_from('<I',header,20)[0],
                         klass=cl,title=label,extra_hex=extra.hex()))
    if pos!=len(data):raise ValueError('unexpected dialog trailing data')
    return dict(header_hex=data[:26].hex(),menu=menu,klass=klass,title=title,font=font,controls=rows)


def rebuild(table):
    header=bytes.fromhex(table['header_hex'])
    if len(header)!=26 or struct.unpack_from('<H',header,16)[0]!=len(table['controls']):
        raise ValueError('dialog header/control count mismatch')
    out=bytearray(header+pack_atom(table['menu'])+pack_atom(table['klass'])+pack_atom(table['title']))
    if table['font'] is not None:
        font=table['font'];meta=bytes.fromhex(font['header_hex'])
        if len(meta)!=6:raise ValueError('invalid dialog font metadata')
        out+=meta+pack_atom(font['face'])
    for ordinal,row in enumerate(table['controls']):
        if row['ordinal']!=ordinal:raise ValueError('dialog control order changed')
        out+=bytes((-len(out))%4);head=bytes.fromhex(row['header_hex']);extra=bytes.fromhex(row['extra_hex'])
        if len(head)!=24 or struct.unpack_from('<I',head,20)[0]!=row['identifier'] or len(extra)>65535:
            raise ValueError('invalid dialog control header or creation data')
        out+=head+pack_atom(row['klass'])+pack_atom(row['title'])+struct.pack('<H',len(extra))+extra
    result=bytes(out)
    if parse(result)!=table:raise ValueError('dialog structural roundtrip mismatch')
    return result


def replace_text(original, title, controls):
    if not isinstance(title,str) or not title or '\0' in title:
        raise ValueError('dialog target title must be nonempty Unicode text')
    table=parse(original)
    if rebuild(table)!=original:raise ValueError('original dialog is not byte-exact')
    table['title']=title;selected=set()
    for row in controls:
        ordinal=row.get('ordinal')
        if type(ordinal) is not int or not 0<=ordinal<len(table['controls']) or ordinal in selected:
            raise ValueError('invalid or duplicate dialog target ordinal')
        selected.add(ordinal);control=table['controls'][ordinal]
        if control['identifier']!=row['identifier'] or control['title']!=row['expected']:
            raise ValueError('dialog control ID or expected text mismatch')
        if not isinstance(control['title'],str) or not isinstance(row['target'],str) or not row['target']:
            raise ValueError('dialog ordinal/empty/internal atom is not a translatable field')
        control['title']=row['target']
    return rebuild(table)
