"""Execute the owned x86 hook against the captured post-callback condition."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'build/native/Release/dialogue_post_tick_fixture.exe'


class DialoguePostTickTests(unittest.TestCase):
    def test_dump_tail_report_cannot_replace_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'sample'
            source.write_bytes(b'owned unsupported sample')
            alias = Path(folder) / 'alias'
            os.link(source, alias)
            for report in (source, alias):
                result = subprocess.run([sys.executable, '-O', str(ROOT/'tools/replay_captured_dialogue_tail.py'),
                    '--dump', str(source), '--old', str(source), '--new', str(source),
                    '--analysis', str(source), '--report', str(report)], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Report must differ', result.stderr)
                self.assertEqual(source.read_bytes(), b'owned unsupported sample')

    @unittest.skipUnless(os.name == 'nt' and FIXTURE.is_file(), 'Build owned x86 fixture first')
    def test_post_callback_phase_is_recomputed(self):
        result = subprocess.run([str(FIXTURE)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for phase in (2, 3, 6):
            self.assertRegex(result.stdout, rf'POST_TICK phase={phase} .*callback_esi=0 result=PASS')
        self.assertIn('POST_TICK_VOICE waiting_begin=1 confirmed_end=1 timer=0 result=PASS', result.stdout)
        self.assertIn('checks=4 failures=0 rollback=exact game_started=false', result.stdout)
