"""Exercise the production exception hook in an owned shared-layout fixture.

No game assets, game entry point, visible dialog or system input is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

from inspect_minidump import Dump


def verify(binary_dir, helper, output, expect_capture=True):
    binary_dir = Path(binary_dir).resolve(strict=True)
    helper = Path(helper).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime = output/'shared'
    modules = runtime/'modules'
    cache = runtime/'cache'
    modules.mkdir(parents=True)
    cache.mkdir()
    for name in ('workspace_profile.dll', 'Core.dll', 'capture_dialog_sink.dll'):
        shutil.copyfile(binary_dir/name, modules/name)
    shutil.copyfile(helper, modules/'capture_helper.exe')
    (runtime/'runtime.json').write_text(json.dumps(dict(schema=1, owned_capture_fixture=True)), encoding='utf8')
    log = cache/'profile.log'
    env = dict(os.environ, MC_WORKSPACE_SESSION=r'Software\MagnaCartaWorkspace\Sessions\SHARED-CAPTURE-TEST',
               MC_WORKSPACE_LOG=str(log), MC_CAPTURE_HELPER=str(modules/'capture_helper.exe'))
    command = [str(modules/'capture_helper.exe'), '--fixture-hook']
    result = subprocess.run(command, env=env, capture_output=True, text=True,
                            encoding='utf8', errors='replace', timeout=45)
    assert result.returncode == 0, result.stderr
    assert 'FIXTURE_DIALOG_RESULT value=42' in result.stdout, result.stdout
    dumps = list(cache.glob('engine-*.dmp'))
    trace = log.read_text(encoding='utf8')
    report = dict(command=command, stdout=result.stdout, stderr=result.stderr,
                  fixture_exit=result.returncode, helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),
                  expected_capture=expect_capture, dump_count=len(dumps), trace=trace,
                  original_dialog_result=42, game_started=False, visible_windows=0)
    if expect_capture:
        assert len(dumps)==1 and 'ENGINE_FULL_CAPTURE_PASS' in trace, trace
        dump = Dump(dumps[0].read_bytes())
        analysis = dump.inspect()
        assert any(v['access_address']=='0x78' for v in analysis['earlier_contexts'])
        heap = int(re.search(r'FIXTURE_HEAP address=(0x[0-9a-fA-F]+)', result.stdout)[1],16)
        assert struct.unpack('<4I',dump.read(heap,16)) == (0x54455854,0x13572468,0,0)
        report.update(full_memory_heap=True, original_exception=True)
        (output/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n',encoding='utf8')
    else:
        assert not dumps and 'ENGINE_FULL_CAPTURE_FAILED' in trace, trace
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('bin','helper','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expect-rejected',action='store_true')
    args=parser.parse_args()
    report=verify(args.bin,args.helper,args.output,not args.expect_rejected)
    print('SHARED_CAPTURE '+('REJECTED' if args.expect_rejected else 'PASS')+
          ' dump_count='+str(report['dump_count'])+' dialog_return=42 game_started=false visible_windows=0')


if __name__=='__main__':
    main()
