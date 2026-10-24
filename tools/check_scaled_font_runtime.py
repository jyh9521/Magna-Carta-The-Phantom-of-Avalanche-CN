"""Offline, source-locked D3D7 font-bridge check. Never starts the game or changes display mode."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def check(mode,cache=None,presentation=False):
    # Reuse the protected shared cache, not a disposable historical build copy.
    cache=(cache or ROOT/'runtime/fonts').resolve(strict=True)
    driver=ROOT/'runtime/data/Drv/AsrD3DDrv.dll';ddraw=ROOT/'runtime/data/ddraw.dll'
    c=json.loads((ROOT/'assets/runtime/scaled-font-contract.json').read_bytes())
    if hashlib.sha256(driver.read_bytes()).hexdigest()!=c['driver_sha256']:
        raise ValueError('Unsupported driver')
    # DDrawCompat is loaded by the owned fixture, never through a game entry.
    if hashlib.sha256(ddraw.read_bytes()).hexdigest()!='f75f0ac48d2782f225c483dc2f1142303a513e8dd8a60793891ade89f64755ea':
        raise ValueError('Unsupported DDrawCompat')
    command=[str(ROOT/'build/native/Release/scaled_font_runtime_fixture.exe'),mode,str(driver),str(ddraw),str(cache)]
    if presentation:command.append('--presentation')
    p=subprocess.run(command,capture_output=True,text=True,timeout=90)
    n=40 if mode=='modified' else 0
    if p.returncode or f'SCALED_RUNTIME {mode.upper()} PASS cases=24 hd_textures={n}' not in p.stdout:
        raise ValueError(f'Owned native check failed exit={p.returncode}\n{p.stdout}\n{p.stderr}')
    return dict(command=command,input=mode,stdout=p.stdout,stderr=p.stderr,exit_status=p.returncode,
                result=f'{mode.upper()} PASS hd_textures={n} game_started=false'+(' output=2880x1800 logical=800x600' if presentation else ''))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('baseline','modified','rollback'))
    p.add_argument('--presentation',action='store_true');p.add_argument('--cache',type=Path);p.add_argument('--record',type=Path);a=p.parse_args()
    try:
        r=check(a.mode,a.cache,a.presentation)
        if a.record:
            if a.record.exists():raise ValueError('New evidence file required')
            a.record.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
        print(r['result'])
    except (ValueError,OSError,subprocess.SubprocessError) as e:p.error(str(e))


if __name__=='__main__':main()
