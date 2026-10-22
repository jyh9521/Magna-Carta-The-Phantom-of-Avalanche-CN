"""Actual-PE query/consumer replay plus production CALL-site hooks, no game launch."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
import os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import replay_damage_projection as tool

ENGINE=ROOT/'runtime/data/MCAlpha.dll'
DRIVER=ROOT/'runtime/data/Drv/AsrD3DDrv.dll'

class DamageProjection(unittest.TestCase):
    def test_report_cannot_overwrite_input_or_hardlink_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.dll';source.write_bytes(b'owned immutable input')
            alias=Path(tmp)/'report.json';os.link(source,alias)
            for report in (source,alias):
                result=subprocess.run([sys.executable,'-O',str(ROOT/'tools/replay_damage_projection.py'),
                    '--engine',str(source),'--driver',str(source),'--report',str(report)],
                    capture_output=True,text=True)
                self.assertEqual(result.returncode,2,result.stderr)
                self.assertIn('Report must differ',result.stderr)
                self.assertEqual(source.read_bytes(),b'owned immutable input')

    def test_unknown_engine_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'unknown.dll';path.write_bytes(b'owned unsupported sample')
            with self.assertRaisesRegex(ValueError,'Unsupported complete engine'):
                tool.verify(path,DRIVER)

    def test_unknown_driver_rejected(self):
        if not ENGINE.exists(): self.skipTest('Supported engine not supplied')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'unknown.dll';path.write_bytes(b'owned unsupported sample')
            with self.assertRaisesRegex(ValueError,'Unsupported complete D3D driver'):
                tool.verify(ENGINE,path)

    def test_native_queries_projection_and_consumer(self):
        if not ENGINE.exists() or not DRIVER.exists(): self.skipTest('Supported local PE inputs not supplied')
        result=tool.verify(ENGINE,DRIVER)
        self.assertTrue(result['native_float_query']['untouched'])
        self.assertTrue(result['native_bool_query']['untouched'])
        self.assertEqual(result['native_coordinate_consumer']['modified'],[600,150])
        self.assertEqual(result['native_perspective']['z_range'],'0 <= clip_z <= clip_w')
        self.assertFalse(result['game_started']);self.assertFalse(result['dll_loaded'])

    def test_owned_production_hooks_and_rollback(self):
        exe=ROOT/'build/native/Release/damage_projection_fixture.exe'
        if not exe.exists(): exe=ROOT/'build/damage-projection-evidence/damage_projection_fixture.exe'
        if not exe.exists(): self.skipTest('Build damage_projection_fixture first')
        baseline=subprocess.run([str(exe),'--baseline'],capture_output=True,text=True)
        self.assertEqual(baseline.returncode,1,baseline.stdout+baseline.stderr)
        modified=subprocess.run([str(exe)],capture_output=True,text=True)
        self.assertEqual(modified.returncode,0,modified.stdout+modified.stderr)
        self.assertIn('unknown_driver=passthrough',modified.stdout)
        self.assertIn('rollback=exact',modified.stdout)

if __name__=='__main__':unittest.main()
