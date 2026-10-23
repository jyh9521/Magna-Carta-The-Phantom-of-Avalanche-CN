"""Package one game-data root with small independent runtime modules/recipes.

Never copies or deletes game data. Move the verified source to output/data separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
from build_configuration_profiles import build as build_display_profiles

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def settings(profile='wide4k', motion=False, pad=False):
    return dict(schema=1, display_profile=profile, motion60=motion, native_gamepad=pad)


def check_capture_helper(data):
    """Check the PE32 x86 executable type without loading or executing it."""
    if len(data) < 256 or data[:2] != b'MZ':
        raise ValueError('Expected Win32 capture helper executable')
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    if offset < 64 or offset + 26 > len(data):
        raise ValueError('Invalid capture helper PE header')
    machine, sections = struct.unpack_from('<HH', data, offset+4)
    optional_size, flags = struct.unpack_from('<HH', data, offset+20)
    if (data[offset:offset+4] != b'PE\0\0' or machine != 0x14c
            or flags & 0x2000 or not flags & 0x0002
            or struct.unpack_from('<H', data, offset+24)[0] != 0x10b
            or optional_size < 96 or not 1 <= sections <= 96
            or offset+24+optional_size+40*sections > len(data)):
        raise ValueError('Expected PE32 x86 capture helper executable, not DLL')


def prepare(source, modules, atlas, output, scaled_font_cache=None, capture_helper=None):
    if capture_helper is not None:
        capture_helper = Path(capture_helper).resolve(strict=True)
        check_capture_helper(capture_helper.read_bytes())
    font_files={}
    if 'scaled-font' in modules:
        if 'native-loading' not in modules or scaled_font_cache is None:
            raise ValueError('Scaled font requires the retained native-loading module and coverage cache')
        from integrate_scaled_font import payload
        font_files=payload(scaled_font_cache)
        if ('launcher_output_snapshot'.encode('utf-16le') in modules['scaled-font'].read_bytes()
                and b'SCALED_FONT_OUTPUT' not in modules['launcher'].read_bytes()):raise ValueError('Matching snapshot-capable launcher required')
    elif scaled_font_cache is not None:
        raise ValueError('Coverage cache requires the scaled font module')
    if 'native-loading' in modules:
        if 'scene-loading' in modules:
            raise ValueError('Native loading excludes withdrawn custom prelude')
        if 'gui-parent-guard' not in modules or 'field-return-height' not in modules:
            raise ValueError('Native loading requires retained GUI and field return guards')
    source=source.resolve(strict=True); output=output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError('New runtime folder required; never copy game data')
    prior=source/'.advanced-runtime'
    original=json.loads((prior/'manifest.json').read_text(encoding='utf-8-sig'))
    if original['schema'] != 1 or str(source) != original['workspace']:
        raise ValueError('Source runtime identity mismatch')
    data={}
    for name, digest in original['source_hashes'].items():
        if name == original['config']:
            continue
        if sha(source/name) != digest:
            raise ValueError('Unsupported game input: '+name)
        data[name]=digest
    title=json.loads((prior/'title-background.json').read_text(encoding='utf8'))
    if not title['active']:
        raise ValueError('Accepted title assets must be active')
    for name, pair in title['tiles'].items():
        if sha(source/name) != pair['after']:
            raise ValueError('Title input drift')
        data[name]=pair['after']
    for module in modules.values():
        if not module.is_file():
            raise ValueError('Missing native module')
    if 'configuration' not in modules:
        raise ValueError('Current configuration module is required')
    if 'gui-parent-guard' in modules and 'field-return-height' not in modules:
        raise ValueError('GUI integration requires retained field return baseline')
    output.mkdir(parents=True)
    files={}
    def copy(path, name):
        destination=output/name; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination); files[name]=sha(destination)
    copy(ROOT/'src/configuration/StartShared.ps1','Start.ps1')
    if capture_helper is not None:
        copy(capture_helper,'modules/capture_helper.exe')
        copy(ROOT/'assets/shared-runtime/Play-diagnostic.cmd','Play-diagnostic.cmd')
    for name in ['Configure.ps1','Configure.xaml','EnhancementSettings.psm1']:
        copy(ROOT/'src/configuration'/name,'config/'+name)
    copy(ROOT/'locales/zh-CN/configuration-ui.json','config/configuration-ui.json')
    copy(ROOT/'locales/zh-CN/art/title-wordmark.png','config/configuration-logo.png')
    copy(source/'.locale-runtime/PrepareProfile.ps1','config/PrepareProfile.ps1')
    profile_candidates=sorted((source/'.locale-runtime').glob('session-*/profile.bin'),key=lambda p:p.stat().st_mtime,reverse=True)
    profile=next((p for p in profile_candidates if p.stat().st_size==52),None)
    if profile is None:
        raise ValueError('Verified 52-byte prepared profile required')
    copy(profile,'config/profile-base.bin')
    for name in original['profiles']:
        if sha(prior/(name+'.ini')) != original['profiles'][name]:
            raise ValueError('Display profile drift')
        copy(prior/(name+'.ini'),'config/profiles/'+name+'.ini')
    build_display_profiles(output/'config/profiles')
    for path in sorted((output/'config/profiles').glob('md3-*.ini')):
        files['config/profiles/'+path.name]=sha(path)
    for name, path in modules.items():
        copy(path,'modules/'+('workspace_launcher.exe' if name=='launcher' else name+'.dll'))
    for name,data in font_files.items():
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);files[name]=sha(target)
    # The accepted settings are mutable; do not lock their hash into the package.
    shutil.copy2(prior/'enhancements.json',output/'config/enhancements.json')
    recipes={'configured':dict(module='configured',settings=None)}
    for profile in original['profiles']:
        recipes[profile]=dict(module='display',settings=settings(profile))
    motion='motion-space' if 'motion-space' in modules else 'modern'
    gamepad='input-diagnostics' if 'input-diagnostics' in modules else 'modern'
    recipes['motion']=dict(module=motion,settings=settings('combined',True))
    recipes['gamepad']=dict(module=gamepad,settings=settings(pad=True))
    recipes['motion-gamepad']=dict(module=gamepad,settings=settings('combined',True,True))
    recipes['texture']=dict(module='texture',settings=settings(),texture=True)
    recipes['camera']=dict(module='camera',settings=settings('combined',True),camera=True)
    # Current profile shim includes the optional camera/map observers. Keep all
    # controller recipes on that same input revision, not historical role DLLs.
    # Older packages without an explicit input candidate retain their role DLLs.
    recipes['camera-gamepad']=dict(module=gamepad if 'input-diagnostics' in modules else 'camera',settings=settings('combined',True,True),camera=True)
    recipes['maps']=dict(module='maps',settings=settings(),maps=True)
    recipes['maps-gamepad']=dict(module=gamepad if 'input-diagnostics' in modules else 'maps',settings=settings(pad=True),maps=True)
    atlas_manifest=json.loads((atlas/'manifest.json').read_text(encoding='utf8'))
    if atlas_manifest.get('schema')!=1 or atlas_manifest.get('navigation_verified') is not False:
        raise ValueError('Unsupported map atlas')
    for row in atlas_manifest['accepted']:
        for extension,key in [('png','png_sha256'),('map','metadata_sha256')]:
            name=f"{row['id']:04d}.{extension}"
            if sha(atlas/name)!=row[key]:
                raise ValueError('Map asset drift')
            files['maps/'+name]=row[key]
    for name in ['manifest.json','label.txt']:
        files['maps/'+name]=sha(atlas/name)
    if (atlas/'legend.txt').is_file():
        files['maps/legend.txt']=sha(atlas/'legend.txt')
    title_original=b'@echo off\r\nsetlocal\r\nset MC_TITLE_STYLE=0\r\ncall "%~dp0Play.cmd"\r\n'
    (output/'Play-title-original.cmd').write_bytes(title_original)
    files['Play-title-original.cmd']=sha(output/'Play-title-original.cmd')
    manifest=dict(schema=1,data_root='data',data=data,files=files,profiles={**original['profiles'],**{p.stem:sha(p) for p in (output/'config/profiles').glob('md3-*.ini')}},recipes=recipes,
                  configured_modules=dict(display='display',motion=motion,gamepad=gamepad,combined=gamepad))
    if 'field-return-height' in modules:
        manifest['field_return_height']=dict(schema=1,enabled=True,module='field-return-height')
    if 'gui-parent-guard' in modules:
        manifest['gui_parent_guard']=dict(schema=1,enabled=True,module='gui-parent-guard')
    if 'scene-loading' in modules:
        manifest['scene_loading']=dict(schema=1,enabled=True,module='scene-loading')
    if 'native-loading' in modules:
        manifest['native_scene_loading']=dict(schema=1,enabled=True,module='native-loading')
    if 'scaled-font' in modules:
        manifest['scaled_font']=dict(schema=1,enabled=True,module='scaled-font',scale=4)
        if 'launcher_output_snapshot'.encode('utf-16le') in modules['scaled-font'].read_bytes():
            manifest['scaled_font_output']=dict(schema=1,source='launcher_display_snapshot')
    (output/'runtime.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf8'))
    for recipe in recipes:
        entry='Play.cmd' if recipe=='configured' else 'Play-'+recipe+'.cmd'
        cmd=f'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start.ps1" -Recipe {recipe}\r\nif errorlevel 1 pause\r\n'
        (output/entry).write_bytes(cmd.encode('ascii'))
    (output/'Configure.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0config\\Configure.ps1"\r\nif errorlevel 1 pause\r\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['source','display','modern','texture','camera','maps','launcher','atlas','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--configuration',type=Path,required=True)
    parser.add_argument('--motion',type=Path)
    parser.add_argument('--gamepad',type=Path)
    parser.add_argument('--field-return-height',type=Path)
    parser.add_argument('--gui-parent-guard',type=Path)
    parser.add_argument('--scene-loading',type=Path)
    parser.add_argument('--native-loading',type=Path)
    parser.add_argument('--scaled-font',type=Path)
    parser.add_argument('--scaled-font-cache',type=Path)
    parser.add_argument('--capture-helper',type=Path)
    a=parser.parse_args()
    modules={name:getattr(a,name) for name in ['display','modern','texture','camera','maps','launcher']}
    modules['configuration']=a.configuration
    if a.motion: modules['motion-space']=a.motion
    if a.gamepad: modules['input-diagnostics']=a.gamepad
    if a.field_return_height: modules['field-return-height']=a.field_return_height
    if a.gui_parent_guard: modules['gui-parent-guard']=a.gui_parent_guard
    if a.scene_loading: modules['scene-loading']=a.scene_loading
    if a.native_loading: modules['native-loading']=a.native_loading
    if a.scaled_font: modules['scaled-font']=a.scaled_font
    prepare(a.source,modules,a.atlas,a.output,a.scaled_font_cache,a.capture_helper)
    print('SHARED_PACKAGE PASS copied_game_data=false data_move_pending=true')
