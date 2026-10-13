"""Source-locked delta packages applied only to new independent game copies."""
import argparse,hashlib,json,shutil,struct,zlib
from pathlib import Path,PurePosixPath

def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(name):
    if not isinstance(name,str) or ':' in name or '\\' in name:raise ValueError('invalid package path')
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or p.as_posix()!=name:raise ValueError('noncanonical package path')
    return p
def located(root,name):
    p=root/canonical(name)
    if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('linked or escaping package path')
    return p
def delta(before,after):
    # Matching source blocks remain COPY instructions, never bundled originals.
    ops=[]
    for off in range(0,len(after),64):
        block=after[off:off+64];kind=0 if before[off:off+len(block)]==block else 1
        if ops and ops[-1][0]==kind:
            if kind==0:ops[-1][2]+=len(block)
            else:ops[-1][1].extend(block)
        elif kind==0:ops.append([0,off,len(block)])
        else:ops.append([1,bytearray(block)])
    raw=bytearray(struct.pack('<QI',len(after),len(ops)))
    for op in ops:
        raw+=bytes([op[0]])
        if op[0]==0:raw+=struct.pack('<QQ',op[1],op[2])
        else:raw+=struct.pack('<Q',len(op[1]))+op[1]
    return b'LPD1'+zlib.compress(raw,9)
def undelta(before,patch,size):
    if type(size) is not int or not 0<=size<=512*1024*1024 or patch[:4]!=b'LPD1':raise ValueError('invalid delta identity or size')
    dec=zlib.decompressobj();raw=dec.decompress(patch[4:],size*2+1048576)
    if not dec.eof or dec.unused_data or dec.unconsumed_tail:raise ValueError('invalid delta compression')
    if len(raw)<12:raise ValueError('truncated delta')
    expected,count=struct.unpack_from('<QI',raw);pos=12;out=bytearray()
    if expected!=size or count>size//32+2:raise ValueError('invalid delta output bounds')
    for _ in range(count):
        if pos>=len(raw):raise ValueError('truncated delta operation')
        kind=raw[pos];pos+=1
        if kind==0:
            if pos+16>len(raw):raise ValueError('truncated copy')
            start,length=struct.unpack_from('<QQ',raw,pos);pos+=16
            if not length or start+length>len(before):raise ValueError('copy outside source')
            block=before[start:start+length]
        elif kind==1:
            if pos+8>len(raw):raise ValueError('truncated literal')
            length=struct.unpack_from('<Q',raw,pos)[0];pos+=8
            if not length or pos+length>len(raw):raise ValueError('literal outside delta')
            block=raw[pos:pos+length];pos+=length
        else:raise ValueError('unsupported delta operation')
        if len(out)+len(block)>size:raise ValueError('delta exceeds target')
        out+=block
    if pos!=len(raw) or len(out)!=size:raise ValueError('delta length mismatch')
    return bytes(out)
def collect(packages):
    rows={}
    for folder in packages:
        folder=Path(folder).resolve(strict=True);m=json.loads((folder/'build.json').read_text(encoding='utf8'))
        if not m.get('source_unchanged') or m.get('game_started') or m.get('deployed'):raise ValueError('unverified candidate manifest')
        if 'groups' in m:expected={t['resource']:t['modified_sha256'] for g in m['groups'] for t in g['tiles']}
        elif 'fields' in m:expected={'MCAlpha.dll':m['modified_sha256']}
        else:expected={r['resource']:r['modified_sha256'] for r in m['resources']}
        expected.update({'Font/'+n:digest for n,digest in m.get('fonts',{}).items()})
        for name,digest in expected.items():
            if name in rows:raise ValueError('overlapping candidate packages')
            path=located(folder,name)
            if sha(path.read_bytes())!=digest:raise ValueError('candidate differs from verified build manifest')
            rows[name]=path
    return rows
def build(source,packages,runtime,scope_path,output):
    source=Path(source).resolve(strict=True);output=Path(output).resolve();runtime=Path(runtime).resolve(strict=True)
    scope_path=Path(scope_path).resolve(strict=True)
    if output.exists() or source.is_relative_to(output) or output.is_relative_to(source):raise ValueError('package output must be new and separate')
    rows=collect(packages)
    if any(p.is_relative_to(output) for p in [*rows.values(),scope_path,runtime]):raise ValueError('package output overlaps inputs')
    scope_raw=scope_path.read_bytes();scope=json.loads(scope_raw)
    if scope.get('old_save_name_adaptation',{}).get('decision')!='excluded' or not scope.get('staff_credits',{}).get('whole_resource_preserved'):
        raise ValueError('explicit scope decisions missing')
    if 'MOV/MOV.pak' in rows:raise ValueError('staff movie must remain original')
    logo=scope.get('opening_brand_logo')
    if logo:
        if logo['resource'] in rows or not logo.get('whole_resource_preserved') or sha(located(source,logo['resource']).read_bytes())!=logo['source_sha256']:
            raise ValueError('opening logo must remain original')
    art_path=located(scope_path.parent,scope['preserved_art_manifest']);art_raw=art_path.read_bytes();art=json.loads(art_raw)
    scope['preserved_art']=art['resources']
    for r in scope['preserved_art']:
        if r['resource'] in rows or sha(located(source,r['resource']).read_bytes())!=r['source_sha256']:
            raise ValueError('excluded art changed or entered patch set')
    preserved=scope['staff_credits'];original_movie=located(source,preserved['resource']).read_bytes()
    if sha(original_movie)!=preserved['source_sha256']:raise ValueError('preserved staff source mismatch')
    prepared={};records=[];snapshots={scope_path:scope_raw,art_path:art_raw}
    for i,(name,path) in enumerate(sorted(rows.items())):
        before=located(source,name).read_bytes();after=path.read_bytes();patch=delta(before,after)
        if undelta(before,patch,len(after))!=after:raise ValueError('delta readback failed')
        key=f'patches/{i:04}.lpd';prepared[key]=patch;snapshots[path]=after
        records.append(dict(resource=name,patch=key,patch_sha256=sha(patch),source_sha256=sha(before),target_sha256=sha(after),
                            source_size=len(before),target_size=len(after),changed=before!=after))
    prerequisites={n:sha(located(source,n).read_bytes()) for n in ['MagnaCarta.exe','MCAlpha.dll']}
    owned={n:(runtime/n).read_bytes() for n in ['workspace_profile.dll','workspace_launcher.exe']}
    snapshots.update({runtime/n:b for n,b in owned.items()})
    templates=Path(__file__).resolve().parents[1]/'assets/locale-package'
    for n in ['Start.ps1','QA_CHECKLIST.md','README.md']:
        p=templates/n;snapshots[p]=p.read_bytes();owned[n]=snapshots[p]
    for p,b in snapshots.items():
        if p.read_bytes()!=b:raise ValueError('package input drift')
    for r in records:
        if sha(located(source,r['resource']).read_bytes())!=r['source_sha256']:raise ValueError('original changed before package publication')
    manifest=dict(schema=1,kind='offline_locale_candidate_delta',files=records,prerequisites=prerequisites,
                  runtime={n:sha(b) for n,b in owned.items()},scope=scope,source_unchanged=True,
                  selected_builds_verified=True,all_game_text_complete=False,release_ready=False,in_game_verified=False,game_started=False)
    output.mkdir(parents=True)
    for name,raw in {**prepared,**{'runtime/'+n:b for n,b in owned.items()}}.items():
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    for n in ['README.md','QA_CHECKLIST.md']:shutil.copyfile(templates/n,output/n)
    project=Path(__file__).resolve().parents[1]
    (output/'licenses').mkdir()
    for name,relative in [('project-MIT.txt','LICENSE'),('translations.txt','LICENSE-translations.md'),('NotoSansSC-OFL.txt','assets/licenses/NotoSansSC-OFL.txt')]:
        shutil.copyfile(project/relative,output/'licenses'/name)
    shutil.copyfile(project/'LICENSING.md',output/'licenses/SOURCES.md')
    shutil.copyfile(__file__,output/'apply_locale.py');return manifest
def read_package(package):
    package=Path(package).resolve(strict=True);raw=(package/'manifest.json').read_bytes();m=json.loads(raw)
    if m.get('schema')!=1 or m.get('kind')!='offline_locale_candidate_delta' or not isinstance(m.get('files'),list):raise ValueError('unsupported locale package')
    names=[r['resource'] for r in m['files']]
    if len(names)!=len(set(names)) or not names or len(names)>10000:raise ValueError('invalid package resource identities')
    for n in names:canonical(n)
    return package,raw,m
def preflight(package,source):
    package,raw,m=read_package(package);source=Path(source).resolve(strict=True)
    for name,digest in m['prerequisites'].items():
        if sha(located(source,name).read_bytes())!=digest:raise ValueError('unsupported original version')
    p=m['scope']['staff_credits']
    if sha(located(source,p['resource']).read_bytes())!=p['source_sha256']:raise ValueError('staff source drift')
    logo=m['scope'].get('opening_brand_logo')
    if logo and sha(located(source,logo['resource']).read_bytes())!=logo['source_sha256']:raise ValueError('opening logo source drift')
    for r in m['scope'].get('preserved_art',[]):
        if sha(located(source,r['resource']).read_bytes())!=r['source_sha256']:raise ValueError('excluded art drift')
    for r in m['files']:
        before=located(source,r['resource']).read_bytes();patch=located(package,r['patch']).read_bytes()
        if len(before)!=r['source_size'] or sha(before)!=r['source_sha256'] or sha(patch)!=r['patch_sha256']:raise ValueError('original or delta digest mismatch')
        if sha(undelta(before,patch,r['target_size']))!=r['target_sha256']:raise ValueError('target digest mismatch')
    for n,digest in m['runtime'].items():
        if sha(located(package,'runtime/'+n).read_bytes())!=digest:raise ValueError('owned runtime digest mismatch')
    return package,raw,m,source
def apply(package,source,output):
    package,raw,m,source=preflight(package,source);output=Path(output).resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):raise ValueError('apply only to a new independent copy')
    for p in source.rglob('*'):
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('source contains links')
    if (source/'.locale-runtime').exists() or (source/'.locale-install.json').exists():raise ValueError('source is already a locale copy')
    stage=output.with_name(output.name+'.assembling')
    if stage.exists() or stage.is_relative_to(source):raise ValueError('assembly stage already exists or overlaps source')
    shutil.copytree(source,stage)
    for r in m['files']:
        p=located(stage,r['resource']);before=p.read_bytes()
        if sha(before)!=r['source_sha256']:raise ValueError('copy changed before patch')
        after=undelta(before,located(package,r['patch']).read_bytes(),r['target_size']);p.chmod(p.stat().st_mode|0o200);p.write_bytes(after)
        if sha(p.read_bytes())!=r['target_sha256']:raise ValueError('installed target readback mismatch')
    (stage/'.locale-runtime').mkdir()
    for n in m['runtime']:shutil.copyfile(located(package,'runtime/'+n),stage/'.locale-runtime'/n)
    (stage/'.locale-install.json').write_text(json.dumps(dict(package_sha256=sha(raw),state='candidate',game_started=False))+'\n',encoding='utf8')
    if (package/'manifest.json').read_bytes()!=raw:raise ValueError('package drift before publication')
    stage.rename(output);return m
def rollback(package,source,target):
    package,raw,m,source=preflight(package,source);target=Path(target).resolve(strict=True)
    if target==source or target.is_relative_to(source) or source.is_relative_to(target):raise ValueError('rollback only an independent locale copy')
    marker=located(target,'.locale-install.json');state=json.loads(marker.read_text(encoding='utf8'))
    if state.get('package_sha256')!=sha(raw) or state.get('state')!='candidate':raise ValueError('rollback marker mismatch')
    for r in m['files']:
        if sha(located(target,r['resource']).read_bytes())!=r['target_sha256']:raise ValueError('modified copy drift; no rollback writes')
    for r in m['files']:
        p=located(target,r['resource']);p.write_bytes(located(source,r['resource']).read_bytes())
        if sha(p.read_bytes())!=r['source_sha256']:raise ValueError('rollback readback mismatch')
    state['state']='rolled_back';marker.write_text(json.dumps(state)+'\n',encoding='utf8');return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','verify','apply','rollback']);p.add_argument('--source',type=Path,required=True)
    for arg in ['package','runtime','scope','output','target']:p.add_argument('--'+arg,type=Path)
    p.add_argument('--candidates',type=Path,nargs='+');a=p.parse_args()
    if a.action=='build':m=build(a.source,a.candidates,a.runtime,a.scope,a.output)
    elif a.action=='apply':m=apply(a.package,a.source,a.output)
    elif a.action=='rollback':m=rollback(a.package,a.source,a.target)
    else:_,_,m,_=preflight(a.package,a.source)
    print(f'LOCALE_PACKAGE_{a.action.upper()} PASS files={len(m["files"])} game_started=false')
