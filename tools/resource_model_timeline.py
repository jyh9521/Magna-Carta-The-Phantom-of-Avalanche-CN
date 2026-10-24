"""Read source 3DO geometry lengths and timed model commands without rendering."""
import hashlib
import struct


class Reader:
    def __init__(self,data):
        self.data=data
        self.pos=0
    def take(self,n):
        if n<0 or self.pos+n>len(self.data):raise ValueError('Truncated 3DO section')
        out=self.data[self.pos:self.pos+n];self.pos+=n;return out
    def integer(self):return struct.unpack('<i',self.take(4))[0]
    def count(self,maximum=1000000):
        n=self.integer()
        if not 0<=n<=maximum:raise ValueError('Invalid 3DO count')
        return n


def material(r):
    r.take(80)
    faces=r.count()
    r.take(faces*6)


def parse(data):
    r=Reader(data)
    kind=r.integer()
    if kind==0:
        vertices=r.count();r.take(8+vertices*44)
        for _ in range(r.count(10000)):material(r)
        r.take(4)
        r.take(r.count(4096)*12)
        for _ in range(r.count(4096)):
            child_type=r.integer()
            r.take(r.count()*36)
            r.take(r.count()*4)
            r.take(28 if child_type==1 else 44)
    elif kind==1:
        count=r.count(4096);r.take(count*12)
        for _ in range(count):
            materials=r.count(10000)
            if materials:
                width,height,stride=struct.unpack('<3i',r.take(12))
                if min(width,height,stride)<0:raise ValueError('Invalid 3DO image shape')
                r.take(width*stride)
                for _ in range(materials):material(r)
                r.take(4)
    else:raise ValueError('Unknown 3DO geometry kind')
    animation_offset=r.pos
    marker=r.take(16)
    sequences=[]
    for _ in range(r.count(4096)):
        key,frames,stride,samples,loop=struct.unpack('<iiiHH',r.take(16))
        if not 0<=frames<=100000 or (stride<=0 and (frames or samples)) or samples>100000:raise ValueError('Invalid 3DO sequence')
        r.take(samples*8)
        commands=[]
        for _ in range(r.count(65536)):
            offset=r.pos
            row=struct.unpack('<15i',r.take(60))
            if row[0]>samples:raise ValueError('3DO command sample out of range')
            commands.append(dict(offset=offset,sample=row[0],tick=row[0]*stride,
                                 kind=row[2],arguments=list(row[3:9]),transform=list(row[9:])))
        sequences.append(dict(key=key,frames=frames,stride=stride,samples=samples,loop=loop,commands=commands))
    box=r.integer()
    if box==1:r.take(96)
    elif box!=0:raise ValueError('Unknown 3DO bounds flag')
    if marker.split(b'\0')[0]==b'VERANIM':
        r.take(16)
        for _ in range(r.count(4096)):
            r.take(4);r.take(r.count(65536)*14)
    if r.pos!=len(data):raise ValueError('Unexpected 3DO trailing bytes')
    if len({s['key'] for s in sequences})!=len(sequences):raise ValueError('Duplicate 3DO sequence keys')
    return dict(sha256=hashlib.sha256(data).hexdigest(),animation_offset=animation_offset,
                kind=kind,sequences=sequences,exact_eof=True)
