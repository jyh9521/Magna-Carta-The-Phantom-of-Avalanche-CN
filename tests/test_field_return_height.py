from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import replay_native_field_return as replay


class FieldReturnHeightTests(unittest.TestCase):
    def test_unknown_resource_rejected_before_instruction_execution(self):
        with self.assertRaisesRegex(RuntimeError,'Unsupported full Field0757'):
            replay.run(b'owned unknown PE',b'owned unknown FLD')

    def test_cli_preserves_existing_report_and_source_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);sample=root/'source';sample.write_bytes(b'owned PE')
            field=root/'field';field.write_bytes(b'owned FLD');existing=root/'report';existing.write_bytes(b'keep')
            alias=root/'alias';os.link(sample,alias)
            for out in [existing,alias,sample]:
                result=subprocess.run([sys.executable,'-O',str(ROOT/'tools/replay_native_field_return.py'),
                                       '--sample',str(sample),'--field',str(field),'--report',str(out)],capture_output=True,text=True)
                self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(existing.read_bytes(),b'keep');self.assertEqual(sample.read_bytes(),b'owned PE')

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and (ROOT/'runtime/data/MCAlpha.dll').exists(),
                         'Optional original image and Unicorn')
    def test_actual_opcode_chain_exposes_stale_z_not_fake_unlock_failure(self):
        engine=ROOT/'runtime/data/MCAlpha.dll';field=ROOT/'runtime/data/Field/0757.fld'
        image,raw=engine.read_bytes(),field.read_bytes()
        baseline=replay.run(image,raw);candidate=replay.run(image,raw,True);rollback=replay.run(image,raw)
        self.assertEqual(baseline,rollback)
        self.assertFalse(baseline['softlock_reproduced'])
        self.assertFalse(candidate['collision_executed']);self.assertFalse(candidate['dialogue_rendered'])
        for old,new in zip(baseline['cases'],candidate['cases']):
            self.assertEqual(old['native_lock'],0);self.assertEqual(new['native_lock'],0)
            self.assertEqual(old['end'][2],old['start'][2]);self.assertEqual(new['end'][2],-96.)
            self.assertEqual(old['end'][:2],new['end'][:2]);self.assertEqual(old['ticks'],new['ticks'])
            self.assertGreater(new['candidate_z_writes'],0)
        self.assertEqual(engine.read_bytes(),image);self.assertEqual(field.read_bytes(),raw)

    @unittest.skipUnless(os.name=='nt' and (ROOT/'build/native/Release/field_return_height_fixture.exe').exists(),
                         'Optional Win32 native build')
    def test_compiled_production_call_abi_guards_and_exact_rollback(self):
        exe=ROOT/'build/native/Release/field_return_height_fixture.exe'
        old=subprocess.run([str(exe),'--baseline'],capture_output=True,text=True)
        new=subprocess.run([str(exe)],capture_output=True,text=True)
        self.assertEqual(old.returncode,1,old.stdout+old.stderr)
        self.assertIn('FAIL XYZ return must write interpolator Z',old.stdout)
        self.assertEqual(new.returncode,0,new.stdout+new.stderr)
        self.assertIn('call_site_abi=executed',new.stdout)
        self.assertIn('lock_counter=unchanged rollback=exact',new.stdout)

    @unittest.skipUnless(os.name=='nt' and (ROOT/'build/native/Release/field_return_height_fixture.exe').exists()
                         and (ROOT/'runtime/data/MCAlpha.dll').exists(),'Optional real image mapping')
    def test_real_pe_regions_install_and_remove_without_commercial_entry(self):
        result=subprocess.run([str(ROOT/'build/native/Release/field_return_height_fixture.exe'),
                               '--image',str(ROOT/'runtime/data/MCAlpha.dll')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('commercial_entry_executed=false exact_restore=true',result.stdout)


if __name__=='__main__':unittest.main()
