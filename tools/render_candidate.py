"""Offline, source-locked DDrawCompat configuration experiments.

No process is launched and no desktop setting is changed. The wide profile is
an integration draft, not an installable substitute for a projection patch.
"""
import argparse
import json
from pathlib import Path

import graphics_compat as graphics

CONFIG_NAME = graphics.CONFIG_NAME
STATE_NAME = '.render-candidate.json'
BASELINE = graphics.PROFILES['render1080']
PROFILES = {
    'baseline': BASELINE,
    'render4k': BASELINE.replace(b'1920x1080(-1)', b'3840x2160(-1)'),
    'fps60': BASELINE + b'FpsLimiter = flipend(60)\n',
}
PROFILES['wide4k'] = PROFILES['render4k'].replace(
    b'DisplayAspectRatio = app\n', b'DisplayAspectRatio = 16:9\n')
PROFILES['combined'] = PROFILES['wide4k'] + b'FpsLimiter = flipend(60)\n'
GRAPHICS_INPUTS = graphics.VERSION_INPUTS['unpatched']
# Supported installed localization + no-disc candidate, observed 2026-10-13.
SOURCE_INPUTS = {**GRAPHICS_INPUTS,
    'MagnaCarta.exe': '6046b29600b5e009903b3495bd11df0b4d89fc3545adde028193ea9fbff8d4de',
    'MCAlpha.dll': '5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427'}
SOURCE_HASHES = {**SOURCE_INPUTS, 'ddraw.dll': graphics.DLL_SHA256,
                 CONFIG_NAME: graphics.sha(BASELINE)}
NOTES = {
    'baseline': 'Existing 1080-line 4:3 control; no new override.',
    'render4k': '2160-line 4:3 prediction: 2880x2160; runtime dimensions unverified.',
    'wide4k': 'Gated: 16:9 display only after separate projection integration; not true wide by itself.',
    'fps60': '60 FPS presentation cap only; cannot unlock engine or decouple simulation.',
    'combined': 'Gated: projection and engine timing integration required; not an accepted all-in-one mod.',
}


def plain_path(path, strict=True):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Linked path rejected: ' + str(part))
    return path.resolve(strict=strict)


def checked_source(source):
    source = plain_path(source)
    for name, digest in SOURCE_HASHES.items():
        path = plain_path(source / name)
        if not path.is_file() or graphics.sha(path.read_bytes()) != digest:
            raise ValueError('Unsupported source: ' + name)
    state = json.loads(plain_path(source / graphics.STATE_NAME).read_text(encoding='utf-8'))
    if (state.get('schema') != 1 or state.get('layer') != 'DDrawCompat'
            or state.get('version') != graphics.VERSION or state.get('profile') != 'render1080'
            or state.get('inputs') != GRAPHICS_INPUTS
            or state.get('outputs') != {'ddraw.dll': graphics.DLL_SHA256,
                                       CONFIG_NAME: graphics.sha(BASELINE)}):
        raise ValueError('Unsupported graphics manifest')
    for folder in (source, source / 'Drv'):
        for path in folder.iterdir():
            if path.name.lower() in graphics.LAYER_NAMES - {
                    'ddraw.dll', CONFIG_NAME.lower(), graphics.STATE_NAME}:
                raise ValueError('Competing configuration: ' + str(path))
            if folder != source and path.name.lower() == 'ddraw.dll':
                raise ValueError('Competing graphics DLL')
    return source


def generate(source, output):
    source = checked_source(source)
    output = plain_path(output, strict=False)
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Output must be separate from source')
    if output.exists():
        raise ValueError('Output exists; choose a new directory')
    # This bundle intentionally contains no game resources, saves or DLLs.
    output.mkdir(parents=True)
    for name, data in PROFILES.items():
        (output / (name + '.ini')).write_bytes(data)
    manifest = {'schema': 1, 'source': str(source), 'source_hashes': SOURCE_HASHES,
                'source_state_sha256': graphics.sha((source / graphics.STATE_NAME).read_bytes()),
                'profiles': {name: {'sha256': graphics.sha(data), 'note': NOTES[name],
                                    'installable': name not in ('wide4k', 'combined')}
                             for name, data in PROFILES.items()},
                'game_started': False, 'source_unchanged': True}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    checked_source(source)
    return manifest


def target_path(workspace, allowed_root, source):
    root = plain_path(allowed_root)
    target = plain_path(workspace)
    source = plain_path(source)
    if (target == root or not target.is_relative_to(root) or target == source
            or target.is_relative_to(source) or source.is_relative_to(target)):
        raise ValueError('Target must be an independent copy below build root')
    return target


def apply(source, workspace, allowed_root, profile):
    if profile not in PROFILES:
        raise ValueError('Unknown profile')
    if profile in ('wide4k', 'combined'):
        raise ValueError('Projection integration required before installing wide4k')
    source = checked_source(source)
    target = target_path(workspace, allowed_root, source)
    checked_source(target)
    if (target / STATE_NAME).exists():
        raise ValueError('Candidate already installed; rollback first')
    state = {'schema': 1, 'profile': profile, 'source': str(source),
             'source_hashes': SOURCE_HASHES, 'config_sha256': graphics.sha(PROFILES[profile]),
             'graphics_state_sha256': graphics.sha((target / graphics.STATE_NAME).read_bytes())}
    # Candidate overrides are tracked separately. Do not update the original
    # graphics manifest: original layer removal requires candidate rollback.
    with (target / STATE_NAME).open('x', encoding='utf-8') as stream:
        json.dump(state, stream, indent=2)
    try:
        graphics.replace_bytes(target / CONFIG_NAME, PROFILES[profile])
        if (target / CONFIG_NAME).read_bytes() != PROFILES[profile]:
            raise ValueError('Candidate write mismatch')
        checked_source(source)
    except Exception:
        graphics.replace_bytes(target / CONFIG_NAME, BASELINE)
        (target / STATE_NAME).unlink()
        raise
    return state


def rollback(workspace, allowed_root):
    target = plain_path(workspace)
    state_path = plain_path(target / STATE_NAME)
    state = json.loads(state_path.read_text(encoding='utf-8'))
    profile = state.get('profile')
    if (state.get('schema') != 1 or profile not in PROFILES or profile in ('wide4k', 'combined')
            or state.get('source_hashes') != SOURCE_HASHES
            or state.get('config_sha256') != graphics.sha(PROFILES[profile])):
        raise ValueError('Unsupported candidate manifest')
    target = target_path(target, allowed_root, state['source'])
    for name, digest in SOURCE_HASHES.items():
        wanted = state['config_sha256'] if name == CONFIG_NAME else digest
        if graphics.sha(plain_path(target / name).read_bytes()) != wanted:
            raise ValueError('Changed candidate; rollback stopped: ' + name)
    if graphics.sha(plain_path(target / graphics.STATE_NAME).read_bytes()) != state['graphics_state_sha256']:
        raise ValueError('Changed graphics manifest; rollback stopped')
    graphics.replace_bytes(target / CONFIG_NAME, BASELINE)
    checked_source(target)
    state_path.unlink()
    return graphics.sha(BASELINE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'generate', 'apply', 'rollback'])
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--profile', choices=PROFILES, default='render4k')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'build'
    if args.action in ('apply', 'rollback'):
        graphics.ensure_idle()
    if args.action == 'preflight':
        if not args.source: parser.error('--source required')
        checked_source(args.source)
        print('RENDER_PREFLIGHT PASS source_locked=true game_started=false')
    elif args.action == 'generate':
        if not args.source or not args.output: parser.error('--source and --output required')
        generate(args.source, args.output)
        print('RENDER_GENERATE PASS profiles=5 source_unchanged=true game_started=false')
    elif args.action == 'apply':
        if not args.source or not args.workspace: parser.error('--source and --workspace required')
        apply(args.source, args.workspace, root, args.profile)
        print(f'RENDER_APPLY PASS profile={args.profile} source_unchanged=true game_started=false')
    else:
        if not args.workspace: parser.error('--workspace required')
        digest = rollback(args.workspace, root)
        print(f'RENDER_ROLLBACK PASS baseline_sha256={digest} game_started=false')


if __name__ == '__main__':
    main()
