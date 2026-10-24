"""Compile locale-owned captions and audit every Field resource without rewriting it."""
import argparse,hashlib,json,struct
from pathlib import Path
from resource_field_script import parse

def fnv(data):
 h=2166136261
 for b in data:h=((h^b)*16777619)&0xffffffff
 return h

def read_catalog(path):
 c=json.loads(path.read_text('utf8'))
 if c.get('schema')!=1:raise ValueError('Unknown caption schema')
 ids=set()
 for r in c['resources']:
  if r['id'] in ids:raise ValueError('Duplicate audio identity')
  ids.add(r['id']);last=0
  if r['kind'] not in ('speech','non_lexical_audio') or (r['kind']!='speech' and r['cues']):raise ValueError('Unknown audio classification')
  if r['kind']=='speech' and not r['cues']:raise ValueError('Missing speech translation')
  for q in r['cues']:
   if not last<=q['start_ms']<q['end_ms']<=r['duration_ms'] or not q['target'].strip() or not q['source_ko'].strip() or q.get('state')!='translated' or '\0' in q['target']:raise ValueError('Invalid or missing caption cue')
   last=q['end_ms']
 return c

def compile(catalog,source,output,report):
 catalog,source,output=map(lambda p:Path(p).resolve(),(catalog,source,output))
 if output==catalog or output.is_relative_to(source) or output.suffix!='.h':raise ValueError('Independent generated header required')
 if report:
  report=Path(report).resolve()
  if report==output or report.is_relative_to(source) or report.is_relative_to(catalog.parent):raise ValueError('Independent audit report required')
 c=read_catalog(catalog);by_id={r['id']:r for r in c['resources']}
 texts={}
 for p in (catalog.parent/'text').glob('*.json'):
  rows=json.loads(p.read_text('utf8'))
  if not isinstance(rows,list):continue
  for r in rows:
   if isinstance(r,dict) and r.get('target') and r.get('id','').startswith('Fpb/'):
    a=r['id'].split(':');texts[(int(a[0][4:8]),int(a[-1]))]=r['target']
 cues=[];bindings=[];rejected=[];accepted=0;raw603=[];seen=set()
 for p in sorted((source/'Field').glob('*.fld')):
  d=p.read_bytes();fid=int(p.stem)
  try:s=parse(d)
  except ValueError as e:
   hits=[i for i in range(0,len(d)-59,4) if struct.unpack_from('<i',d,i)[0] in (603,604)]
   if hits:raise ValueError('Unparsed Field contains potential voice-only command: '+p.name)
   rejected.append(dict(field=fid,sha256=hashlib.sha256(d).hexdigest(),reason=str(e),potential_voice_only_commands=0));continue
  accepted+=1
  for event in s['events']:
   for a in event['actions']:
    op=a['opcode'];v=a['parameters'];h=fnv(struct.pack('<14i',*v))
    if op==603:
     if v[0] not in by_id:raise ValueError('Unclassified standalone sound '+str(v[0]))
     row=by_id[v[0]]
     if row['kind']=='speech' and v[1]!=1:raise ValueError('Unsupported standalone speech loop policy')
     seen.add(v[0]);bindings.append((fid,op,h,v[0],''))
     raw603.append(dict(field=fid,event=event['index'],offset=a['offset'],resource=v[0],parameters_fnv=h))
    elif op in (700,704) and v[7]>=0:
     text=texts.get((s['playbook_id'],v[6]))
     if text:text=text.replace('$n','\n')
     if not text:raise ValueError('Missing approved dialogue '+str((fid,v[6])))
     bindings.append((fid,op,h,v[7],text))
 if seen!=set(by_id):raise ValueError('Caption catalog coverage differs from all Field sound references')
 for r in c['resources']:
  data=(source/'SED'/f"{r['id']:04d}.SED").read_bytes()
  if hashlib.sha256(data).hexdigest()!=r['audio_sha256']:raise ValueError('Audio source changed')
  for q in r['cues']:cues.append((r['id'],q['start_ms'],q['end_ms'],q['target']))
 def wide(t):return 'L'+json.dumps(t,ensure_ascii=True)
 lines=['// Generated from locale data; rebuild with tools/build_story_captions.py.','#pragma once','struct StoryCue {unsigned resource,start,end;const wchar_t* text;};','struct StoryBinding {unsigned field,opcode,parameters,resource;const wchar_t* text;};','static const StoryCue storyCues[]={']
 lines.insert(2,'static const wchar_t storyCaptionFont[]='+wide(c.get('font_family','Segoe UI'))+';')
 lines += ['{%du,%du,%du,%s},'%(n,a,b,wide(t)) for n,a,b,t in cues];lines+=['};','static const StoryBinding storyBindings[]={']
 lines+=['{%du,%du,%du,%du,%s},'%(f,o,h,n,wide(t)) for f,o,h,n,t in bindings];lines+=['};']
 output.parent.mkdir(parents=True,exist_ok=True);content=('\n'.join(lines)+'\n').encode()
 if not output.exists() or output.read_bytes()!=content:output.write_bytes(content)
 result=dict(schema=1,fields_scanned=accepted+len(rejected),parsed_fields=accepted,rejected_fields=rejected,voice_only_commands=raw603,resources=len(seen),speech_resources=sum(r['kind']=='speech' for r in c['resources']),cues=len(cues),normal_dialogue_bindings=len(bindings)-len(raw603),missing_translations=[],audio_hashes_verified=True,original_curtain_modified=False,game_started=False)
 if report:report.parent.mkdir(parents=True,exist_ok=True);report.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
 print('STORY_CAPTIONS_BUILD PASS fields='+str(result['fields_scanned'])+' voice_only_commands='+str(len(raw603))+' resources='+str(len(seen))+' cues='+str(len(cues))+' missing=0 game_started=false')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path);compile(**vars(p.parse_args()))
