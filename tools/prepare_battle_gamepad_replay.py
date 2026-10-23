"""Build three owned controller replay stages; never copy or start a game."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/runtime'
BASELINE = 'dc742e8bf21e7ec953d1d816a9502794d445dc67'
CORE = ('modern_gamepad.cpp', 'gamepad_ui.cpp')
COMMON = ('modern_input.cpp', 'world_gamepad.cpp', 'camera_relative_input.cpp',
          'gamepad_cursor.cpp', 'ui_focus.cpp')
ADAPTERS = ('battle_gamepad_chain_fixture.cpp', 'battle_gamepad_focus_fixture.cpp')
MODES = (1, 4, 5, 6, 7, 99)
CMAKE = r'''cmake_minimum_required(VERSION 3.20)
project(BattlePadStage LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_compile_definitions(UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX _WIN32_WINNT=0x0601 MODERN_INPUT_TEST)
add_executable(battle_gamepad_chain_fixture battle_gamepad_chain_fixture.cpp modern_gamepad.cpp modern_input.cpp world_gamepad.cpp camera_relative_input.cpp gamepad_cursor.cpp gamepad_ui.cpp ui_focus.cpp)
add_executable(battle_gamepad_focus_fixture battle_gamepad_focus_fixture.cpp modern_gamepad.cpp modern_input.cpp world_gamepad.cpp camera_relative_input.cpp gamepad_cursor.cpp ui_focus.cpp)
foreach(target battle_gamepad_chain_fixture battle_gamepad_focus_fixture)
  target_link_libraries(${target} PRIVATE user32)
  target_compile_options(${target} PRIVATE /W4 /utf-8)
  set_property(TARGET ${target} PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endforeach()
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(output, cmake):
    output = Path(output).resolve()
    if (output.exists() or output.is_relative_to(ROOT/'runtime')
            or output.is_relative_to(SOURCE) or SOURCE.is_relative_to(output)):
        raise ValueError('A new, independent owned-fixture output directory is required')
    original = {name: subprocess.check_output(
        ['git', 'show', BASELINE+':src/runtime/'+name], cwd=ROOT) for name in CORE}
    # Only the two changed production implementations differ between stages.
    # Dependencies must still match the audited baseline, rather than silently
    # rebuilding a historical implementation against changed common code.
    for name in COMMON:
        baseline = subprocess.check_output(['git', 'show', BASELINE+':src/runtime/'+name], cwd=ROOT)
        if (SOURCE/name).read_bytes().replace(b'\r\n', b'\n') != baseline.replace(b'\r\n', b'\n'):
            raise ValueError('Replay common-source drift: '+name)
    headers = list(SOURCE.glob('*.h'))
    for path in headers:
        if path.name == 'battle_pad_context.h':
            continue  # New modified-only route helper; historical code never includes it.
        baseline = subprocess.check_output(['git', 'show', BASELINE+':src/runtime/'+path.name], cwd=ROOT)
        if path.read_bytes().replace(b'\r\n', b'\n') != baseline.replace(b'\r\n', b'\n'):
            raise ValueError('Replay shared-header drift: '+path.name)
    output.mkdir(parents=True)
    commands = []

    def run(args, label):
        result = subprocess.run([str(a) for a in args], cwd=ROOT, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=300)
        log = output/(label+'.log')
        log.write_text(result.stdout+result.stderr, encoding='utf-8', newline='\n')
        commands.append(dict(command=[str(a) for a in args], exit_status=result.returncode,
                             log=str(log), log_sha256=digest(log.read_bytes())))
        if result.returncode:
            raise RuntimeError('Owned replay build failed: '+str(log))
        return result.stdout

    sources = {}
    for stage in ('baseline', 'modified', 'rollback'):
        src = output/('stage-'+stage+'-src'); src.mkdir()
        build = output/('stage-'+stage+'-native')
        for path in headers:
            (src/path.name).write_bytes(path.read_bytes())
        for name in (*COMMON, *CORE, *ADAPTERS):
            data = original[name] if stage != 'modified' and name in CORE else (SOURCE/name).read_bytes()
            (src/name).write_bytes(data)
        (src/'CMakeLists.txt').write_text(CMAKE, encoding='utf-8', newline='\n')
        run([cmake, '-S', src, '-B', build, '-A', 'Win32'], stage+'-configure')
        run([cmake, '--build', build, '--config', 'Release', '--parallel', '2'], stage+'-build')
        for mode in MODES:
            text = run([build/'Release/battle_gamepad_chain_fixture.exe', str(mode)], stage+'-mode'+str(mode))
            rows = [json.loads(line) for line in text.splitlines()]
            if not rows or rows[0].get('kind') != 'metadata' or rows[0].get('game_started') is not False:
                raise ValueError('Owned production trace metadata mismatch')
            (output/(stage+'-mode'+str(mode)+'.jsonl')).write_text(text, encoding='utf-8', newline='\n')
        sources[stage] = {name: digest((src/name).read_bytes()) for name in (*COMMON, *CORE, *ADAPTERS)}
    if sources['baseline'] != sources['rollback']:
        raise ValueError('Rollback source identity mismatch')
    report = dict(schema=1, baseline_commit=BASELINE, sources=sources, commands=commands,
                  game_started=False, game_data_copied=False)
    (output/'prepared.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('BATTLE_GAMEPAD_PREPARE PASS stages=3 modes=6 rollback_sources=exact game_data_copied=false game_started=false')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cmake', default=shutil.which('cmake'))
    args = parser.parse_args()
    if not args.cmake:
        parser.error('Pass --cmake with the installed CMake executable path')
    prepare(args.output, args.cmake)


if __name__ == '__main__':
    main()
