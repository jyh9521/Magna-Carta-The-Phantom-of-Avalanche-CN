"""Audit ZIP bytes, compiled resources, native icon frames and accepted dependencies without launching the game."""
import argparse
import ctypes
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from build_compiled_desktop import ROOT, compiler, icon_bytes
from build_clean_overlay import safe_name
from build_compiled_release import TITLE_MARKER, PROFILE_MODULES


def sha(b):return hashlib.sha256(b).hexdigest()


def exe_execution_level(path):
    """Inspect the embedded manifest, without launching the executable."""
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.LoadLibraryExW.argtypes=[w.LPCWSTR,w.HANDLE,w.DWORD];k.LoadLibraryExW.restype=w.HMODULE
    k.FreeLibrary.argtypes=[w.HMODULE]
    k.FindResourceW.argtypes=[w.HMODULE,ctypes.c_void_p,ctypes.c_void_p];k.FindResourceW.restype=w.HRSRC
    k.SizeofResource.argtypes=[w.HMODULE,w.HRSRC];k.SizeofResource.restype=w.DWORD
    k.LoadResource.argtypes=[w.HMODULE,w.HRSRC];k.LoadResource.restype=w.HGLOBAL
    k.LockResource.argtypes=[w.HGLOBAL];k.LockResource.restype=ctypes.c_void_p
    module=k.LoadLibraryExW(str(path),None,2)
    if not module:raise OSError('PE resource load failed')
    try:
        item=k.FindResourceW(module,1,24)
        if not item:raise ValueError('Missing embedded execution manifest')
        data=ctypes.string_at(k.LockResource(k.LoadResource(module,item)),k.SizeofResource(module,item))
        tree=ET.fromstring(data)
        node=tree.find('.//{urn:schemas-microsoft-com:asm.v3}requestedExecutionLevel')
        if node is None or node.get('uiAccess')!='false':raise ValueError('Invalid execution manifest')
        return node.get('level')
    finally:k.FreeLibrary(module)


def exe_icon_frames(path):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.LoadLibraryExW.argtypes=[w.LPCWSTR,w.HANDLE,w.DWORD];k.LoadLibraryExW.restype=w.HMODULE
    k.FreeLibrary.argtypes=[w.HMODULE]
    k.FindResourceW.argtypes=[w.HMODULE,ctypes.c_void_p,ctypes.c_void_p];k.FindResourceW.restype=w.HRSRC
    k.SizeofResource.argtypes=[w.HMODULE,w.HRSRC];k.SizeofResource.restype=w.DWORD
    k.LoadResource.argtypes=[w.HMODULE,w.HRSRC];k.LoadResource.restype=w.HGLOBAL
    k.LockResource.argtypes=[w.HGLOBAL];k.LockResource.restype=ctypes.c_void_p
    callback=ctypes.WINFUNCTYPE(w.BOOL,w.HMODULE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ssize_t)
    k.EnumResourceNamesW.argtypes=[w.HMODULE,ctypes.c_void_p,callback,ctypes.c_ssize_t]
    module=k.LoadLibraryExW(str(path),None,2)
    if not module:raise OSError('PE resource load failed')
    def resource(name,kind):
        item=k.FindResourceW(module,name,kind)
        if not item:raise ValueError('Missing native icon resource')
        return ctypes.string_at(k.LockResource(k.LoadResource(module,item)),k.SizeofResource(module,item))
    groups=[]
    @callback
    def collect(h,t,name,unused):
        groups.append(resource(name,14));return True
    try:
        if not k.EnumResourceNamesW(module,14,collect,0) or not groups:raise ValueError('No native icon groups')
        frames=[]
        for group in groups:
            count=struct.unpack_from('<H',group,4)[0]
            for i in range(count):
                length,index=struct.unpack_from('<IH',group,6+14*i+8)
                data=resource(index,3)
                if len(data)!=length:raise ValueError('Icon resource length mismatch')
                frames.append(sha(data))
        return sorted(frames)
    finally:k.FreeLibrary(module)


def read_embedded(core_path):
    """Read metadata without loading or executing the audited runtime."""
    with tempfile.TemporaryDirectory(prefix='desktop metadata audit ') as folder:
        reader=Path(folder)/'inspect.exe'
        subprocess.run([str(compiler()),'/nologo','/target:exe','/r:System.Web.Extensions.dll',
                        '/out:'+str(reader),str(ROOT/'tools/inspect_desktop_resources.cs')],
                       check=True,capture_output=True)
        inspected=subprocess.run([str(reader),str(Path(core_path).resolve())],check=True,
                                 capture_output=True,encoding='utf8')
        return json.loads(inspected.stdout)


def verify(archive,icon,report=None):
    archive,icon=Path(archive).resolve(),Path(icon).resolve()
    original=icon_bytes(icon);count=struct.unpack_from('<H',original,4)[0]
    frames=[]
    for i in range(count):
        size,offset=struct.unpack_from('<II',original,6+16*i+8);frames.append(sha(original[offset:offset+size]))
    with zipfile.ZipFile(archive) as z:
        names=[safe_name(n) for n in z.namelist()]
        if len(names)!=len(set(n.casefold() for n in names)) or z.testzip():raise ValueError('ZIP paths or CRC failed')
        scripts=sum(n.lower().endswith(('.ps1','.psm1','.cs','.cmd','.bat')) for n in names)
        configs=sum(n.startswith('config/') for n in names)
        manifests=sum(n in ('runtime.json','Overlay-Manifest.json') for n in names)
        if scripts or configs or manifests:
            raise ValueError(f'COMPILED_PACKAGE FAIL scripts={scripts} config_files={configs} external_manifests={manifests}')
        hashes={n:sha(z.read(n)) for n in names}
        with tempfile.TemporaryDirectory(prefix='desktop package audit ') as temp:
            temp=Path(temp)
            for name in ('Game.exe','Configure.exe','modules/DesktopRuntime.dll'):
                p=temp/Path(name).name;p.write_bytes(z.read(name))
            for name in ('Game.exe','Configure.exe'):
                if exe_icon_frames(temp/name)!=sorted(frames):raise ValueError('EXE icon differs from supplied ICO: '+name)
                if exe_execution_level(temp/name)!='asInvoker':raise ValueError('Expected explicit asInvoker manifest: '+name)
            info=read_embedded(temp/'DesktopRuntime.dll')
    assets=info['resources'];runtime=info['runtime.json'];overlay=info['Overlay-Manifest.json']
    if 'enhancements.json' in names:raise ValueError('Player settings must not be shipped or overwritten')
    if runtime.get('release',{}).get('desktop_revision',0)>=4 and (
            runtime.get('desktop',{}).get('settings_location')!='installation_root' or
            runtime.get('desktop',{}).get('elevation')!='on_write_denied'):
        raise ValueError('Desktop settings/elevation contract mismatch')
    if assets.get('mc/MC.ico')!=sha(original):raise ValueError('Window icon resource mismatch')
    if any(n.lower().endswith(('.ps1','.psm1','.cs','.cmd','.bat','.py')) for n in assets):raise ValueError('Embedded executable source')
    if overlay['files']!={n:h for n,h in hashes.items() if n!='modules/DesktopRuntime.dll'}:raise ValueError('Embedded overlay manifest mismatch')
    for n,h in runtime['files'].items():
        if hashes.get(n)!=h:raise ValueError('Embedded runtime checksum mismatch: '+n)
    for n,h in runtime['data'].items():
        if n not in hashes:raise ValueError('Missing bundled runtime input: '+n)
        if hashes[n]!=h:raise ValueError('Effective game input mismatch: '+n)
    native={}
    for n in overlay['source_files']:
        if Path(n).suffix.lower() in {'.dll','.exe','.m3d','.flt','.asi'}:
            if n not in hashes:raise ValueError('Missing bundled native input: '+n)
            native[n]=hashes[n]
    complete=runtime.get('complete_inputs')
    if complete and (complete.get('schema')!=1 or complete.get('required') is not True or
                     complete.get('external_inputs')!=0 or complete.get('files')!=runtime['data'] or
                     complete.get('native_files')!=native or
                     any(runtime['data'].get(n)!=h for n,h in native.items())):
        raise ValueError('Complete input manifest mismatch')
    compatible=runtime.get('baseline_compatibility')
    if compatible:
        identity=sha(json.dumps(overlay['source_files'],sort_keys=True,separators=(',',':')).encode())
        if (compatible.get('schema')!=1 or compatible.get('source_manifest_sha256')!=identity or
            any(overlay['source_files'].get(n)!=h or runtime['data'].get(n)!=h or hashes.get(n)!=h
                for n,h in compatible.get('files',{}).items())):
            raise ValueError('Baseline compatibility manifest mismatch')
    for row in overlay['changes']:
        if hashes.get(row['resource'])!=row['target_sha256']:raise ValueError('Accepted changed resource drift')
    title=runtime.get('title_version')
    if title:
        modules=title.get('modules', {})
        if (title.get('schema')!=1 or title.get('font')!='native' or title.get('background')!='none' or
                title.get('alignment')!='right' or title.get('native_abi')!='preserve-ebx-esi-edi' or
                set(modules)!=set((*PROFILE_MODULES, 'modules/minimap.dll'))):
            raise ValueError('Title-version metadata mismatch')
        with zipfile.ZipFile(archive) as z:
            for name, expected in modules.items():
                data=z.read(name)
                if (hashes.get(name)!=expected or runtime['files'].get(name)!=expected or TITLE_MARKER not in data or
                        title['original_prefix'].encode('ascii')+b'\0' not in data or
                        title['patch_line'].encode('ascii')+b'\0' not in data):
                    raise ValueError('Title-version payload mismatch: '+name)
    result=dict(sha256=sha(archive.read_bytes()),bytes=archive.stat().st_size,files=len(names),scripts=0,
                config_files=0,external_manifests=0,icon_sha256=sha(original),native_icon_frames=count,
                embedded_resources=len(assets),game_resources=len(overlay['changes']),game_started=False)
    result.update(bundled_inputs=len(runtime['data']),external_inputs=0,execution_level='asInvoker',
                  settings_location=runtime.get('desktop',{}).get('settings_location','legacy_user'))
    if title:result['title_version']=title
    if report:Path(report).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print('COMPILED_PACKAGE PASS scripts=0 config_files=0 external_manifests=0 native_icons=exact window_icon=exact game_resources='+str(result['game_resources'])+' bundled_inputs='+str(result['bundled_inputs'])+' external_inputs=0 game_started=false')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--icon',type=Path,required=True);p.add_argument('--report',type=Path)
    try:verify(**vars(p.parse_args()))
    except (ValueError,OSError,KeyError) as e:print(str(e));raise SystemExit(1)
