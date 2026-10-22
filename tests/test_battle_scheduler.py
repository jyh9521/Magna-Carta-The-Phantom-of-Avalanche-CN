"""Source/branch/budget/report guards for bounded native task-dispatch replay."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import replay_battle_scheduler as tool

ROOT=Path(__file__).resolve().parents[1]
SAMPLE=ROOT/'runtime/data/MCAlpha.dll'

class BattleScheduler(unittest.TestCase):
    def source(self):
        if not SAMPLE.exists():self.skipTest('Supported local engine not supplied')
        return SAMPLE.read_bytes()

    def test_unknown_source_rejected(self):
        with self.assertRaisesRegex(tool.ReplayError,'Unsupported complete engine SHA256'):
            tool.verify(b'owned unsupported fixture')

    def test_mutated_branch_rejected_even_with_test_digest(self):
        import pefile
        source=bytearray(self.source());pe=pefile.PE(data=source)
        source[pe.get_offset_from_rva(0xcf01)]^=1
        with patch.object(tool,'SOURCE_SHA',hashlib.sha256(source).hexdigest()):
            with self.assertRaisesRegex(tool.ReplayError,'Scheduler instruction mismatch'):
                tool.verify(bytes(source))

    def test_native_30_60_dispatch_conservation(self):
        report=tool.verify(self.source())
        for case in report['cases']:
            self.assertEqual(case['native_dispatches'],1818)
            self.assertEqual(case['remainder_ms'],6)
            self.assertTrue(case['stop_verified_every_frame'])
        self.assertFalse(report['game_started']);self.assertFalse(report['dll_loaded'])

    def test_instruction_budget_failure_rejected(self):
        with self.assertRaisesRegex(tool.ReplayError,'did not reach stop before instruction budget'):
            tool.verify(self.source(),1000,instruction_budget=1)

    def test_bad_duration_rejected(self):
        with self.assertRaisesRegex(tool.ReplayError,'complete 100 ms steps'):
            tool.verify(self.source(),duration_ms=1234)

    def test_report_cannot_replace_source_or_existing_report(self):
        self.source()
        script=ROOT/'tools/replay_battle_scheduler.py'
        before=hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
        run=subprocess.run([sys.executable,str(script),'--sample',str(SAMPLE),'--report',str(SAMPLE)],capture_output=True,text=True)
        self.assertEqual(run.returncode,2)
        self.assertEqual(hashlib.sha256(SAMPLE.read_bytes()).hexdigest(),before)
        with tempfile.TemporaryDirectory() as tmp:
            report=Path(tmp)/'report.json';report.write_text('preserve')
            run=subprocess.run([sys.executable,str(script),'--sample',str(SAMPLE),'--report',str(report)],capture_output=True,text=True)
            self.assertEqual(run.returncode,2);self.assertEqual(report.read_text(),'preserve')

if __name__=='__main__':unittest.main()
