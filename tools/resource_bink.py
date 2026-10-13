"""Observed BIKi container rebuilding with byte-exact audio packet retention."""
import hashlib
import struct


def parse(data):
    if len(data)<48 or data[:4]!=b'BIKi':raise ValueError('unsupported Bink revision')
    values=struct.unpack_from('<10I',data,4)
    size,count,largest,repeated,width,height,num,den,flags,tracks=values
    if (size+8!=len(data) or not 1<=count<=1000000 or repeated!=count
            or not 1<=width<=4096 or not 1<=height<=4096 or not num or not den or tracks>256):
        raise ValueError('invalid BIKi header')
    index=44+12*tracks;table_end=index+4*(count+1)
    if table_end>len(data):raise ValueError('truncated BIKi frame index')
    entries=struct.unpack_from('<'+str(count+1)+'I',data,index)
    offsets=[x&~1 for x in entries[:-1]]+[entries[-1]]
    if offsets[0]!=table_end or offsets[-1]!=len(data) or any(a>=b for a,b in zip(offsets,offsets[1:])):
        raise ValueError('invalid or noncontiguous BIKi frame offsets')
    frames=[]
    for i,(start,end) in enumerate(zip(offsets,offsets[1:])):
        pos=start;audio=[]
        for _ in range(tracks):
            if pos+4>end:raise ValueError('truncated BIKi audio length')
            length=struct.unpack_from('<I',data,pos)[0]
            if pos+4+length>end:raise ValueError('BIKi audio exceeds frame packet')
            audio.append(data[pos:pos+4+length]);pos+=4+length
        if pos==end:raise ValueError('BIKi frame has no video packet')
        frames.append(dict(audio=audio,video=data[pos:end],key=entries[i]&1))
    if largest<max(b-a for a,b in zip(offsets,offsets[1:])):
        raise ValueError('BIKi largest packet header too small')
    return dict(header=data[:index],frames=frames,width=width,height=height,fps=[num,den],flags=flags,
                tracks=tracks,original_size=len(data))


def rebuild(table,allocated_size=None):
    header=bytearray(table['header']);frames=table['frames'];count=len(frames)
    if struct.unpack_from('<I',header,8)[0]!=count:raise ValueError('BIKi frame count changed')
    packets=[b''.join(f['audio'])+f['video'] for f in frames]
    if any(len(p)%2 for p in packets):raise ValueError('BIKi frame packet is not even aligned')
    start=len(header)+4*(count+1);size=start+sum(map(len,packets))
    if allocated_size is not None:
        if type(allocated_size) is not int or allocated_size<size or (allocated_size-size)%2:
            raise ValueError('BIKi does not fit preserved member allocation')
        units=(allocated_size-size)//2;q,r=divmod(units,count)
        packets=[p+bytes(2*(q+(i<r))) for i,p in enumerate(packets)];size=allocated_size
    offsets=[];pos=start
    for packet,frame in zip(packets,frames):offsets.append(pos|frame['key']);pos+=len(packet)
    offsets.append(pos)
    struct.pack_into('<I',header,4,size-8);struct.pack_into('<I',header,12,max(map(len,packets)))
    out=bytes(header)+struct.pack('<'+'I'*(count+1),*offsets)+b''.join(packets)
    checked=parse(out)
    if checked['header'][40:]!=table['header'][40:]:raise ValueError('BIKi audio metadata changed')
    return out


def replace_video(original,video_only,allocated_size=None):
    old,new=parse(original),parse(video_only)
    if new['tracks'] or any(old[k]!=new[k] for k in ('width','height','fps','flags')) or len(old['frames'])!=len(new['frames']):
        raise ValueError('video replacement changes frame count, dimensions, flags, rate or carries audio')
    frames=[dict(audio=a['audio'],video=b['video'],key=b['key']) for a,b in zip(old['frames'],new['frames'])]
    result=rebuild({**old,'frames':frames},allocated_size)
    checked=parse(result)
    if any(a['audio']!=b['audio'] for a,b in zip(old['frames'],checked['frames'])):
        raise ValueError('original BIKi audio packet changed')
    return result


def members(data):
    result=[];pos=0
    while pos<len(data):
        if pos+8>len(data):raise ValueError('truncated concatenated Bink header')
        length=struct.unpack_from('<I',data,pos+4)[0]+8
        if length<48 or pos+length>len(data):raise ValueError('invalid concatenated Bink member size')
        raw=data[pos:pos+length];parse(raw);result.append((pos,raw));pos+=length
    return result


def audio_digest(data):
    return hashlib.sha256(b''.join(p for f in parse(data)['frames'] for p in f['audio'])).hexdigest()
