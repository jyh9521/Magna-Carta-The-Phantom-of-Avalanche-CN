"""Prepare opt-in current-driver texture lifetime candidate, retaining accepted art."""
import argparse
from pathlib import Path
import prepare_configuration_trial as config

def write_entrypoints(output,locale):
    config.write_entrypoints(output,locale)
    runtime=output/'.advanced-runtime'
    script=(runtime/'StartEnhanced.ps1').read_text(encoding='utf-8-sig')
    script=script.replace('[switch]$Rollback)', '[switch]$Rollback,[switch]$TextureLifetime)')
    script=script.replace("if($VerifyOnly){$arguments+='--verify-only'}", "if($TextureLifetime){$arguments+='--texture-lifetime'}\n if($VerifyOnly){$arguments+='--verify-only'}")
    (runtime/'StartEngineBug.ps1').write_text(script,encoding='utf-8-sig')
    for name,args in {'Play-texture-guard.cmd':'-TextureLifetime','Play-without-texture-guard.cmd':''}.items():
        (output/name).write_bytes(('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\StartEngineBug.ps1" '+args+'\r\nif errorlevel 1 pause\r\n').encode('ascii'))

def prepare(source,native,locale,output):
    config.prepare(source,native,locale,output)
    write_entrypoints(output,locale)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','native','locale','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();prepare(*(getattr(a,n).resolve() for n in ('source','native','locale','output')))
    print('ENGINE_BUG_TRIAL PASS texture_guard=opt_in accepted_art=retained game_started=false')
