"""Read-only full native dialogue/text/audio binding audit; no game or sound device."""
import argparse,hashlib,json,shutil,struct,subprocess,zipfile
from pathlib import Path
from resource_field_script import parse as parse_field
from resource_fpb import parse as parse_fpb
from audit_dialogue_resources import parse_sound,decoder_identity
from build_story_captions import read_catalog,validate_approved


def digest(data):return hashlib.sha256(data).hexdigest()


def bind_private_text(raw,text,mapping):
    """Independently check complete installed bytes, including every ASCII control byte."""
    pos=0
    for char in text:
        size=1 if ord(char)<128 else 2
        part=raw[pos:pos+size]
        if len(part)!=size:raise ValueError('Installed dialogue truncated')
        if size==1:
            if part!=char.encode('ascii'):raise ValueError('Installed ASCII/control mismatch')
        else:
            if char in mapping and mapping[char]!=part:raise ValueError('Installed glyph mapping conflict')
            mapping[char]=part
        pos+=size
    if pos!=len(raw):raise ValueError('Installed dialogue suffix not represented by approved text')


def decode_voice(data,executable):
    header=parse_sound(data)
    if header['storage_word']!=1:raise ValueError('Unsupported native stream storage')
    command=[executable,'-v','error','-f','mp3','-i','pipe:0','-f','s16le','-ac','1','-ar','16000','pipe:1']
    p=subprocess.run(command,input=data[header['header_bytes']:],capture_output=True,timeout=30)
    if p.returncode or not p.stdout or len(p.stdout)%2:raise ValueError('Complete voice decode failed: '+p.stderr.decode('utf8','replace'))
    return dict(source_sha256=digest(data),pcm_sha256=digest(p.stdout),samples=len(p.stdout)//2,
                duration_ms=round(len(p.stdout)/32),exit_status=0,complete_payload=True)


def write_fixtures(catalog,source,output):
    catalog,source,output=map(Path,(catalog,source,output))
    if output.resolve().is_relative_to(source.resolve()):raise ValueError('Independent fixture directory required')
    c=read_catalog(catalog);speech={r['id']:r for r in c['resources'] if r['kind']=='speech'};texts={}
    for path in (catalog.parent/'text').glob('*.json'):
        for r in json.loads(path.read_text('utf8')):
            if isinstance(r,dict) and r.get('target') and r.get('id','').startswith('Fpb/'):
                a=r['id'].split(':');texts[(int(a[0][4:8]),int(a[-1]))]=r['target'].replace('$n','\n')
    ordinary=[];voices=[]
    for path in sorted((source/'Field').glob('*.fld')):
        try:field=parse_field(path.read_bytes())
        except ValueError:continue
        for event in field['events']:
            for action in event['actions']:
                op=action['opcode'];v=action['parameters'];prefix=struct.pack('<16i',int(path.stem),op,*v)
                if op in (700,704) and v[7]>=0:
                    text=texts[(field['playbook_id'],v[6])].encode('utf-16le')
                    ordinary.append(prefix+struct.pack('<I',len(text))+text)
                elif op==603 and v[0] in speech:
                    cues=speech[v[0]]['cues'];data=prefix+struct.pack('<I',len(cues))
                    for q in cues:
                        text=q['target'].encode('utf-16le');data+=struct.pack('<III',q['start_ms'],q['end_ms'],len(text))+text
                    voices.append(data)
    output.mkdir(parents=True,exist_ok=True)
    (output/'ordinary.bin').write_bytes(b'SCM1'+struct.pack('<I',len(ordinary))+b''.join(ordinary))
    (output/'standalone.bin').write_bytes(b'SCV1'+struct.pack('<I',len(voices))+b''.join(voices))
    print(f'STORY_FIXTURES PASS ordinary={len(ordinary)} standalone={len(voices)} game_started=false')


def audit(catalog,source,baseline,report,decode=False):
    catalog,source,baseline,report=map(Path,(catalog,source,baseline,report))
    if report.resolve().is_relative_to(source.resolve()):raise ValueError('Report must be outside source')
    c=read_catalog(catalog);targets={};decoder=decoder_identity('ffmpeg') if decode else None
    for p in sorted((catalog.parent/'text').glob('*.json')):
        for row in json.loads(p.read_text('utf8')):
            if not isinstance(row,dict) or not row.get('target') or not row.get('id','').startswith('Fpb/'):continue
            if row['id'] in targets and targets[row['id']]!=row:raise ValueError('Conflicting approved translation')
            targets[row['id']]=row
    approved=validate_approved(c,{key:r['target'] for key,r in targets.items()})
    with zipfile.ZipFile(baseline) as z:
        manifest=json.loads(z.read('Overlay-Manifest.json'))
    installed=dict(manifest['source_files']);installed.update(manifest['files'])
    bindings=[];fpbs={};voices={};mapping={};rejected=[];counts={str(n):0 for n in range(700,706)};coexisting=[]
    paths=sorted((source/'Field').glob('*.fld'))
    if not paths:raise ValueError('No Field resources')
    for path in paths:
        data=path.read_bytes()
        if installed.get('Field/'+path.name)!=digest(data):raise ValueError('Field baseline drift')
        try:field=parse_field(data)
        except ValueError as e:
            markers=[i for i in range(0,len(data)-3,4) if 700<=struct.unpack_from('<i',data,i)[0]<=705]
            rejected.append(dict(field=path.name,reason=str(e),sha256=digest(data),potential_native_dialogue_markers=markers));continue
        ops={a['opcode'] for e in field['events'] for a in e['actions']}
        if 603 in ops and any(op in ops for op in range(700,706)):coexisting.append(int(path.stem))
        for event in field['events']:
            for action in event['actions']:
                if 700<=action['opcode']<=705:counts[str(action['opcode'])]+=1
        if not any(a['opcode'] in (700,704) and a['parameters'][7]>=0 for e in field['events'] for a in e['actions']):continue
        book=field['playbook_id'];name=f'Fpb/{book:04d}.fpb'
        if book not in fpbs:
            raw=(source/name).read_bytes()
            if installed.get(name)!=digest(raw):raise ValueError('FPB baseline drift')
            fpbs[book]=parse_fpb(raw)
        for event in field['events']:
            for action in event['actions']:
                op=action['opcode'];v=action['parameters']
                if op not in (700,704) or v[7]<0:continue
                entries=[(i,raw) for i,(tag,raw) in enumerate(fpbs[book]) if tag==v[6]]
                if len(entries)!=1:raise ValueError('Ambiguous native text tag')
                ordinal,raw=entries[0];key=f'{name}:text:{ordinal}:{v[6]}'
                if key not in targets:raise ValueError('Untranslated bound native dialogue')
                target=targets[key]
                if target['state']=='translated':bind_private_text(raw,target['target'],mapping)
                elif target['state']=='preserved':
                    if digest(raw)!=target['source_sha256']:raise ValueError('Preserved native text drift')
                else:raise ValueError('Unreviewed bound native text')
                voice=v[7];voice_path=f'SVD/{voice:04d}.SVD'
                if voice not in voices:
                    audio=(source/voice_path).read_bytes()
                    if installed.get(voice_path)!=digest(audio):raise ValueError('Voice baseline drift')
                    voices[voice]=decode_voice(audio,decoder['path']) if decode else dict(source_sha256=digest(audio),header=parse_sound(audio))
                bindings.append(dict(field=int(path.stem),opcode=op,event=event['index'],offset=action['offset'],
                                     reference=key,target_sha256=digest(target['target'].encode('utf8')),
                                     installed_text_sha256=digest(raw),voice=voice,whole_text=True,fixed_caption_end=False))
    if len(set(mapping.values()))!=len(mapping):raise ValueError('Installed glyph mapping is not one-to-one')
    result=dict(schema=1,fields_scanned=len(paths),parsed_fields=len(paths)-len(rejected),rejected_fields=rejected,
                opcode_counts=counts,normal_dialogue_bindings=len(bindings),bindings=bindings,
                unique_native_voices=len(voices),voices=voices,approved_caption_references=approved,
                speech_reviews=sum(r['kind']=='speech' for r in c['resources']),resources=len(c['resources']),
                coexisting_voice_and_native_fields=coexisting,glyphs_consistent=len(mapping),
                original_audio_unchanged=True,installed_text_complete=True,all_native_voices_decoded=decode,decoder=decoder,
                game_started=False,audio_played=False,
                limitations=['PCM activity is not proof of spoken words; review text and source audio together.',
                             'Native whole-text bindings are not a human listening audit of every ordinary voiced line.',
                             'Unsupported Field variants remain explicitly rejected.'])
    report.parent.mkdir(parents=True,exist_ok=True);report.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(f"STORY_COVERAGE PASS fields={len(paths)} bindings={len(bindings)} unique_voices={len(voices)} complete_text=true decoded={decode} approved_references={approved} game_started=false")
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--decode',action='store_true')
    p.add_argument('--fixtures',type=Path)
    args=vars(p.parse_args());fixtures=args.pop('fixtures');audit(**args)
    if fixtures:write_fixtures(args['catalog'],args['source'],fixtures)
