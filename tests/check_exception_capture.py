"""Exercise full-memory capture with owned fixtures only; never run the game."""
import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspect_minidump import Dump

parser = argparse.ArgumentParser()
parser.add_argument('--bin', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
helper = (args.bin / 'capture_helper.exe').resolve()
output = args.output.resolve()
env = dict(os.environ, MC_WORKSPACE_SESSION=r'Software\MagnaCartaWorkspace\Sessions\TEST-123',
           MC_WORKSPACE_LOG=str(output / 'profile.log'), MC_CAPTURE_HELPER=str(helper))
command = [str(helper), '--fixture-hook']
proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=45)
assert proc.returncode == 0, proc.stderr
assert 'FIXTURE_DIALOG_RESULT value=42' in proc.stdout
assert 'ENGINE_FULL_CAPTURE_PASS' in (output / 'profile.log').read_text(encoding='utf-8')
dumps = list(output.glob('engine-*.dmp'))
assert len(dumps) == 1
dump = Dump(dumps[0].read_bytes())
assert 9 in dump.streams
analysis = dump.inspect()
assert any(v['access_address'] == '0x78' for v in analysis['earlier_contexts'])
heap = int(re.search(r'FIXTURE_HEAP address=(0x[0-9a-fA-F]+)', proc.stdout)[1], 16)
assert struct.unpack('<4I', dump.read(heap, 16)) == (0x54455854, 0x13572468, 0, 0)
assert all(v['fault_location']['module'] == 'capture_helper.exe' for v in analysis['earlier_contexts'])

rejected = []
for name, path in [('unrelated-target', output / 'rejected.dmp'),
                   ('outside-build', output.parents[1].parent / 'rejected.dmp')]:
    result = subprocess.run([str(helper), '--pid', str(os.getpid()), '--output', str(path)], capture_output=True, text=True)
    assert result.returncode == 1 and not path.exists()
    rejected.append({'case': name, 'command': result.args, 'stdout': result.stdout,
                     'stderr': result.stderr, 'exit_status': result.returncode})
kept = output / 'kept.bin'
kept.write_bytes(b'preserved')
result = subprocess.run([str(helper), '--pid', str(os.getpid()), '--output', str(kept)], capture_output=True, text=True)
assert result.returncode == 1 and kept.read_bytes() == b'preserved'
rejected.append({'case': 'existing-output', 'command': result.args, 'stdout': result.stdout,
                 'stderr': result.stderr, 'exit_status': result.returncode})
report = {'fixture': {'command': command, 'stdout': proc.stdout, 'stderr': proc.stderr, 'exit_status': proc.returncode},
          'full_memory_heap_readback': True, 'preserved_exception': True, 'dialog_return_preserved': True,
          'rejected': rejected, 'game_started': False, 'visible_windows': 0}
(output / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(output / 'analysis.json').write_text(json.dumps(analysis, indent=2), encoding='utf-8')
print('EXCEPTION_CAPTURE_PASS full_heap=true original_exception=true dialog_return=42 guards=3 game_started=false visible_windows=0')
