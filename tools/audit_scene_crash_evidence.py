"""Attribute a retained GUI exception offline; no process creation, attach, or DLL loading."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from inspect_minidump import Dump
from replay_native_gui_parent import SOURCE_SHA

STARTUP_CHAIN=(0x38b6c,0x38c38,0x38595,0x482a1,0x5ffbe,0x5fbcc,0x101f,0x10ee)
FAULT_PREFIX=bytes.fromhex('558bec51894dfc8b45fc8b4d08d900d801')


def is_startup_chain(context):
    rvas=[]
    for frame in context.get('frame_chain',[]):
        site=frame.get('return_site',{})
        if site.get('module','').lower()=='mcalpha.dll':
            try:rvas.append(int(site['rva'],16))
            except (KeyError,ValueError,TypeError):return False
    return tuple(rvas[:len(STARTUP_CHAIN)])==STARTUP_CHAIN


def audit(dump_bytes,engine_bytes):
    if hashlib.sha256(engine_bytes).hexdigest()!=SOURCE_SHA:raise ValueError('Unsupported full engine SHA256')
    d=Dump(dump_bytes);matches=[m for m in d.modules if m['name'].lower()=='mcalpha.dll']
    if len(matches)!=1:raise ValueError('Expected exactly one engine module in dump')
    m=matches[0];base=m['base']
    if m['size']!=0x10b000 or m['timestamp']!=0x3ed73966:raise ValueError('Dump engine layout mismatch')
    if d.read(base+0x1e940,len(FAULT_PREFIX))!=FAULT_PREFIX:raise ValueError('Snapshot fault instructions do not match source')
    result=d.inspect();contexts=result['earlier_contexts']
    selected=[c for c in contexts if c.get('fault_location',{}).get('module','').lower()=='mcalpha.dll' and c['fault_location'].get('rva')=='0x1e94f' and is_startup_chain(c)]
    r=dict(schema=1,dump_sha256=hashlib.sha256(dump_bytes).hexdigest(),engine_sha256=SOURCE_SHA,
           execution='offline_file_analysis_only',game_started_this_analysis=False,
           scene_transition_verified=False,scene_root_cause_confirmed=False,
           recorded_exception_stream_present=6 in d.streams,
           classification='unclassified',root_parent_bounds_fault_confirmed=False,
           limits=['Recovered exception registers and later heap snapshot have different timing.',
                   'No scene transition is inferred from a real crash or a successful process exit alone.',
                   'No production patch is installed by this analysis.'])
    if len(selected)!=1:
        r['reason']='No unique source-locked startup cursor exception chain';return r
    c=selected[0];root=struct.unpack('<I',d.read(base+0xf220c,4))[0]
    vt,node_type,parent=struct.unpack('<III',d.read(root,12))
    ecx=int(c['registers']['ecx'],16);access=int(c['access_address'],16)
    if vt!=base+0xbd604 or node_type!=2 or parent!=0 or ecx!=root+0xf4 or access!=ecx:
        r['reason']='Recovered context does not bind to the exact generic UI root';return r
    r.update(classification='startup_cursor_initialization_gui_parent_bounds_fault',
             root_parent_bounds_fault_confirmed=True,
             exception=dict(code=c['exception'],instruction=c['fault_location'],access=c['access'],address=c['access_address'],source='recovered_exception_record_not_first_chance_capture'),
             generic_root=dict(address=hex(root),vtable_rva='0xbd604',node_type=2,parent='0x0',
                               source_requested_allocation_bytes=0x54,source_constructor_rva='0x8990'),
             invalid_transform_read=dict(offset='0xf4',read_bytes=4,outside_source_root_allocation=True,
                                         snapshot_memory_region=d.memory_region(access),state_at_fault='not_independently_observed'),
             startup_return_chain=[hex(x) for x in STARTUP_CHAIN])
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('dump','engine','report'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists() or not a.report.parent.is_dir():p.error('New report in existing directory required')
    r=audit(a.dump.read_bytes(),a.engine.read_bytes())
    with a.report.open('x',encoding='utf8') as f:json.dump(r,f,indent=2);f.write('\n')
    print('SCENE_EVIDENCE_AUDIT classification='+r['classification']+' scene_transition_verified=false game_started_this_analysis=false deployed=false')
