"""Repack an accepted overlay with compiled desktop entries and embedded configuration."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import zipfile

from build_clean_overlay import raw_sha, safe_name
from build_compiled_desktop import entries, core, icon_bytes

ROOT = Path(__file__).resolve().parents[1]
STATIC = {'config/Configure.xaml', 'config/configuration-ui.json', 'config/configuration-logo.png',
          'config/enhancements.json', 'config/encounter-ui.json', 'config/profile-base.bin'}
REMOVED = {'Start.ps1', 'Verify-Overlay.ps1', 'runtime.json', 'Overlay-Manifest.json'}
NATIVE_SUFFIXES = {'.dll', '.exe', '.m3d', '.flt', '.asi'}


def inspect_archive(source, expected):
    if raw_sha(source.read_bytes()) != expected:
        raise ValueError('Accepted ZIP hash mismatch')
    with zipfile.ZipFile(source) as z:
        names = [safe_name(n) for n in z.namelist()]
        if len(names) != len(set(n.casefold() for n in names)) or z.testzip():
            raise ValueError('Invalid accepted archive')
        payload = {n: z.read(n) for n in names}
    manifest = json.loads(payload.pop('Overlay-Manifest.json'))
    if manifest.get('schema') != 1 or manifest.get('kind') != 'clean_game_overlay' or manifest.get('layout') != 'flat':
        raise ValueError('Unsupported overlay')
    if manifest['files'] != {n: raw_sha(b) for n, b in payload.items()}:
        raise ValueError('Accepted overlay manifest mismatch')
    runtime = json.loads(payload['runtime.json'])
    for n, h in runtime['files'].items():
        if n not in payload or raw_sha(payload[n]) != h:
            raise ValueError('Accepted runtime mismatch: '+n)
    return payload, runtime, manifest


def bundle_inputs(payload, release, manifest, source_game, compatibility_plan=None):
    """Bind unchanged native inputs as payload, never as assumed installed files."""
    required = dict(release['data'])
    if compatibility_plan:
        raw = Path(compatibility_plan).read_bytes()
        plan = json.loads(raw)
        identity = raw_sha(json.dumps(manifest['source_files'], sort_keys=True,
                                      separators=(',', ':')).encode())
        if (plan.get('schema') != 1 or plan.get('kind') != 'baseline_compatibility' or
                plan.get('source_manifest_sha256') != identity):
            raise ValueError('Compatibility plan source manifest mismatch')
        compatible = {}
        for name, row in plan['files'].items():
            safe_name(name)
            expected = row['source_sha256']
            if manifest['source_files'].get(name) != expected:
                raise ValueError('Compatibility plan source mismatch: '+name)
            if name in required and required[name] != expected:
                raise ValueError('Compatibility plan conflicts with runtime input: '+name)
            required[name] = compatible[name] = expected
        release['baseline_compatibility'] = dict(schema=1, source_manifest_sha256=identity,
                                                  plan_sha256=raw_sha(raw), files=compatible)
    native = {}
    for name, baseline in manifest['source_files'].items():
        if Path(name).suffix.lower() not in NATIVE_SUFFIXES:
            continue
        safe_name(name)
        expected = required.get(name, raw_sha(payload[name]) if name in payload else baseline)
        required[name] = native[name] = expected
    source_game = Path(source_game).resolve() if source_game else None
    added = {}
    for name, expected in required.items():
        safe_name(name)
        if name in payload:
            data = payload[name]
        else:
            if source_game is None:
                raise ValueError('Source game required to bundle runtime input: '+name)
            path = source_game/name
            if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
                raise ValueError('Linked runtime input rejected: '+name)
            if not path.is_file():
                raise ValueError('Runtime input missing: '+name)
            data = path.read_bytes()
            added[name] = data
        if raw_sha(data) != expected:
            raise ValueError('Runtime input hash mismatch: '+name)
    # Commit additions only after every source and existing payload has passed.
    payload.update(added)
    release['files'].update({n: raw_sha(b) for n, b in added.items()})
    release['data'] = required
    release['complete_inputs'] = dict(schema=1, required=True, files=dict(required),
                                      native_files=native, external_inputs=0)
    return added


def build(source, source_sha256, icon, work, output, runtime=None, locale=None, source_game=None,
          compatibility_plan=None):
    locale = Path(locale).resolve() if locale else ROOT/"locales/zh-CN"
    source, icon, work, output = [Path(p).resolve() for p in (source, icon, work, output)]
    if output.exists() or work.exists() or output == source or output.suffix != '.zip':
        raise ValueError('Independent new work directory and ZIP required')
    payload, release, manifest = inspect_archive(source, source_sha256)
    protected = {row['resource']: row['target_sha256'] for row in manifest['changes']}
    for n, h in protected.items():
        if raw_sha(payload[n]) != h:
            raise ValueError('Accepted game resource drift: '+n)
    if runtime:
        runtime = Path(runtime).resolve()
        current = json.loads((runtime/'runtime.json').read_text(encoding='utf-8-sig'))
        for n, h in current['files'].items():
            if raw_sha((runtime/safe_name(n)).read_bytes()) != h:
                raise ValueError('Current runtime drift: '+n)
        for n, h in current['data'].items():
            if raw_sha((runtime/'data'/safe_name(n)).read_bytes()) != h:
                raise ValueError('Current source resource drift: '+n)
        for n, h in current['files'].items():
            if n.startswith('maps/') or n == 'modules/minimap.dll':
                payload[n] = (runtime/n).read_bytes()
                release['files'][n] = h
        for n, h in current['data'].items():
            if n in release['data'] and release['data'][n] != h:
                raise ValueError('Conflicting source dependency: '+n)
            release['data'][n] = h
        release['map_overlay'] = copy.deepcopy(current['map_overlay'])
    added_inputs = bundle_inputs(payload, release, manifest,
                                 source_game or (runtime/'data' if runtime else None), compatibility_plan)
    icon_data = icon_bytes(icon)
    work.mkdir(parents=True)
    resources = work/'resources'
    resources.mkdir()
    embedded = {}
    for n in list(payload):
        if n.startswith('config/'):
            if n in STATIC or (n.startswith('config/profiles/') and n.endswith('.ini')):
                embedded[n] = payload[n]
            elif not n.lower().endswith(('.ps1', '.psm1')):
                raise ValueError('Unclassified configuration resource: '+n)
            payload.pop(n)
            release['files'].pop(n, None)
        elif n in REMOVED or n.lower().endswith(('.cmd', '.ps1', '.psm1')):
            payload.pop(n)
            release['files'].pop(n, None)
    if not STATIC <= embedded.keys():
        raise ValueError('Missing static configuration resources')
    embedded['config/Configure.xaml'] = (ROOT/'src/configuration/Configure.xaml').read_bytes()
    ui = json.loads(embedded['config/configuration-ui.json'])
    # Locale-owned release default note; logic and labels remain separate.
    catalog = json.loads((locale/'configuration-ui.json').read_text(encoding='utf8'))
    ui['default_note'] = catalog['packaged_default_note']
    ui['pending'] = catalog['pending']
    ui['controls'] = catalog['controls']
    for key in ('failed_detail', 'file_mismatch'):
        ui[key] = catalog[key]
    embedded['config/configuration-ui.json'] = (json.dumps(ui, ensure_ascii=False)+'\n').encode()
    embedded['MC.ico'] = icon_data
    payload.update(entries(work/'entries', icon))
    for n in ('Configure.exe', 'Game.exe'):
        release['files'][n] = raw_sha(payload[n])
    release['desktop'] = dict(schema=2, implementation='compiled_managed', resources='embedded',
                              icon_sha256=raw_sha(icon_data), powershell_required=False)
    release['release'] = dict(release.get('release', {}), version='1.0', desktop_revision=3,
                              desktop_in_game_verified=False)
    if release.get('test_candidates'):
        release['test_candidates']['stable_entry'] = 'Game.exe --without-test-candidates'
    embedded['runtime.json'] = (json.dumps(release, indent=2)+'\n').encode()
    payload['README-Overlay.txt'] = (locale/'desktop-readme.txt').read_bytes()
    for n in ('licenses/LICENSE', 'licenses/LICENSE-translations.md', 'licenses/LICENSING.md'):
        if n in payload:
            payload[n] = (ROOT/Path(n).name).read_bytes()
    manifest = dict(manifest, files={n: raw_sha(b) for n, b in payload.items()},
                    desktop=release['desktop'], accepted_archive_sha256=source_sha256,
                    source_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                    desktop_in_game_verified=False, in_game_verified=False,
                    base_resource_acceptance=manifest.get('acceptance'),
                    acceptance=dict(kind='offline_desktop_regression', game_started=False))
    if runtime:
        manifest['map_revision'] = dict(marker='MAP_FRAME_PRESENT_V2', in_game_verified=False)
    embedded['Overlay-Manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode()
    for n, b in embedded.items():
        p = resources/n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    core(work/'entries/modules/DesktopRuntime.dll', resources)
    payload['modules/DesktopRuntime.dll'] = (work/'entries/modules/DesktopRuntime.dll').read_bytes()
    if any(n.startswith('config/') or n in REMOVED or n.lower().endswith(('.ps1','.psm1','.cmd','.cs','.xaml')) for n in payload):
        raise ValueError('Loose source or configuration leaked into package')
    if any(raw_sha(payload[n]) != h for n, h in protected.items()):
        raise ValueError('Accepted game resources changed')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for n, b in sorted(payload.items()):
            info=zipfile.ZipInfo(n, date_time=(2026,10,25,0,0,0));info.external_attr=0o100644<<16
            z.writestr(info, b, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(output) as z:
        if z.testzip() or {n:raw_sha(z.read(n)) for n in z.namelist()} != {n:raw_sha(b) for n,b in payload.items()}:
            raise ValueError('ZIP readback mismatch')
    if raw_sha(source.read_bytes()) != source_sha256:
        raise ValueError('Source ZIP changed')
    digest=raw_sha(output.read_bytes())
    output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n', encoding='utf8')
    report=dict(files=len(payload), resources=len(protected), sha256=digest, icon_sha256=raw_sha(icon_data),
                source_sha256=source_sha256, payload_hashes={n:raw_sha(b) for n,b in payload.items()},
                added_inputs={n: raw_sha(b) for n,b in added_inputs.items()}, external_inputs=0,
                embedded_hashes={n:raw_sha(b) for n,b in embedded.items()})
    (work/'build-report.json').write_text(json.dumps(report,indent=2)+'\n', encoding='utf8')
    print('COMPILED_RELEASE PASS version=1.0 scripts=0 config_files=0 external_manifests=0 resources='+str(len(protected))+' sha256='+digest)
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','icon','work','output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--source-sha256', required=True)
    p.add_argument('--runtime', type=Path)
    p.add_argument('--source-game', type=Path,
                   help='Matching version-locked game inputs; defaults to runtime/data')
    p.add_argument('--compatibility-plan', type=Path,
                   help='Source-manifest-bound resources needed by a supported legacy installation')
    p.add_argument('--locale', type=Path, default=ROOT/'locales/zh-CN')
    build(**vars(p.parse_args()))
