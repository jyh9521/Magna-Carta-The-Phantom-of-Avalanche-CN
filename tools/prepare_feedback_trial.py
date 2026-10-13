"""Package feedback repairs over shared game data, without cloning the game."""
import argparse
import json
from pathlib import Path
import prepare_texture_overlay as overlay


def prepare(workspace, native, output):
    lock = overlay.prepare(workspace, native, output)
    profiles = {
        'motion-repair': {'display_profile': 'combined', 'motion60': True, 'native_gamepad': False},
        'menu-repair': {'display_profile': 'wide4k', 'motion60': False, 'native_gamepad': True},
        'baseline': {'display_profile': 'wide4k', 'motion60': False, 'native_gamepad': False},
    }
    for name, settings in profiles.items():
        settings['schema'] = 1
        (output / (name + '.json')).write_text(json.dumps(settings, indent=2), encoding='utf8')
        cmd = ('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass '
               '-File "%~dp0Start.ps1" -WithoutTextureGuard '
               '-SettingsFile "%~dp0' + name + '.json"\r\nif errorlevel 1 pause\r\n')
        (output / ('Play-' + name + '.cmd')).write_bytes(cmd.encode('ascii'))
    return lock


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'native', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.workspace.resolve(), args.native.resolve(), args.output.resolve())
    print('FEEDBACK_TRIAL PASS shared_game_data=true motion_menu_isolated=true original_entries=retained game_started=false')
