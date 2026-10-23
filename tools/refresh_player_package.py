"""Refresh an existing verified delta-only player bundle without copying a game tree."""
import argparse,json,zipfile,hashlib,subprocess
from pathlib import Path
from build_player_test_bundle import ROOT,sha,validate_engine_fixes
ARCHIVED=('gamepad','motion-gamepad','camera','camera-gamepad','maps-gamepad')

def refresh(previous,previous_sha256,runtime,output):
    previous,runtime,output=map(lambda p:Path(p).resolve(),(previous,runtime,output))
    if output.exists() or output.suffix!='.zip' or output.is_relative_to(runtime) or output==previous:raise ValueError('New independent archive required')
    if sha(previous)!=previous_sha256:raise ValueError('Previous archive drift')
    current=json.loads((runtime/'runtime.json').read_text())
    for collection,root in [('files',runtime),('data',runtime/'data')]:
        for n,d in current[collection].items():
            if sha(root/n)!=d:raise ValueError('Runtime drift: '+n)
    with zipfile.ZipFile(previous) as old:
        if old.testzip():raise ValueError('Previous CRC failure')
        m=json.loads(old.read('package.json'))
        if m.get('schema')!=1 or not m.get('changes') or not m.get('source_files'):raise ValueError('Unsupported player bundle')
        for r in m['changes']:
            if sha(runtime/'data'/r['resource'])!=r['target_sha256'] or hashlib.sha256(old.read(r['patch'])).hexdigest()!=r['patch_sha256']:
                raise ValueError('Changed game resource requires rebuild from original: '+r['resource'])
        release=json.loads(json.dumps(current))
        archived_entries={'Play-'+n+'.cmd' for n in ARCHIVED}
        for name in ARCHIVED:release['recipes'].pop(name,None)
        for name in archived_entries:release['files'].pop(name,None)
        release['archived_features']=['native_gamepad','free_view']
        payload={n:(runtime/n).read_bytes() for n in current['files'] if n not in archived_entries}
        for n in ('runtime.json','Configure.cmd','config/enhancements.json'):
            payload[n]=(runtime/n).read_bytes()
        for p in runtime.glob('Play*.cmd'):
            if p.name not in {'Play-'+n+'.cmd' for n in ARCHIVED}:payload[p.name]=p.read_bytes()
        payload['runtime.json']=(json.dumps(release,indent=2)+'\n').encode()
        settings=json.loads(payload['config/enhancements.json'].decode('utf-8-sig'))
        settings.update(schema=2,resolution='1080p',window_mode='borderless',frame_rate=30,native_gamepad=False,free_view=False,window_resolution='1280x720')
        payload['config/enhancements.json']=(json.dumps(settings,indent=2)+'\n').encode()
        # The compatibility DLL and baseline INI remain owned-package inputs.
        for n in ('data/ddraw.dll','data/DDrawCompat-MagnaCarta.ini'):payload[n]=old.read('payload/'+n)
        m['payload']={n:hashlib.sha256(b).hexdigest() for n,b in payload.items()}
        m['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        m['in_game_verified']=False
        m['engine_fixes']=validate_engine_fixes(runtime,current)
        m['release_controls']=dict(archived_features=['native_gamepad','free_view'],actor_renderers=4,encounter_key='F5',encounter_default='on',scripted_battles='unchanged',in_game_verified=False)
        output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for n in old.namelist():
                if n.startswith('payload/') or n in ('package.json','README.txt'):continue
                z.writestr(n,old.read(n))
            for n,b in sorted(payload.items()):z.writestr('payload/'+n,b)
            z.writestr('README.txt',(ROOT/'assets/player-test-package/README.txt').read_bytes())
            z.writestr('package.json',(json.dumps(m,ensure_ascii=False,indent=2)+'\n').encode())
    with zipfile.ZipFile(output) as z:
        if z.testzip():raise ValueError('Output CRC failure')
        check=json.loads(z.read('package.json'))
        for n,d in check['payload'].items():
            if hashlib.sha256(z.read('payload/'+n)).hexdigest()!=d:raise ValueError('Output payload drift')
        if any('payload/Play-'+n+'.cmd' in z.namelist() for n in ARCHIVED):raise ValueError('Archived entry leaked')
    if sha(previous)!=previous_sha256:raise ValueError('Previous archive modified')
    output.with_suffix('.zip.sha256').write_text(sha(output)+'  '+output.name+'\n')
    print(f'PLAYER_PACKAGE_REFRESH PASS deltas={len(m["changes"])} payload={len(payload)} archived_entries=absent sha256={sha(output)} full_game_copy=false game_started=false')
    return m
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('previous','runtime','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--previous-sha256',required=True)
    refresh(**vars(p.parse_args()))
