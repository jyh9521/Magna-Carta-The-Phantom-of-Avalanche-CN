import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('runtime_failure_report', Path(__file__).resolve().parents[1] / 'tools/runtime_failure_report.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FailureReportTests(unittest.TestCase):
    def parse(self, code):
        return module.parse_exit(f'ISOLATED_PROCESS_STARTED pid=54120\nISOLATED_PROCESS_ENDED exit={code}\n')

    def test_access_violation(self):
        value = self.parse(3221225477)
        self.assertEqual(value['exit_hex'], '0xc0000005')
        self.assertEqual(value['category'], 'access_violation')
        self.assertTrue(value['natural_exit'])

    def test_callback_exception_separate(self):
        self.assertEqual(self.parse(3221226525)['category'], 'unhandled_callback_exception')

    def test_timeout_not_crash(self):
        self.assertFalse(self.parse(124)['natural_exit'])

    def test_normal_exit(self):
        self.assertEqual(self.parse(0)['category'], 'normal_exit')

    def test_incomplete_or_multiple_sessions_rejected(self):
        for text in ('ISOLATED_PROCESS_STARTED pid=1\n',
                     'ISOLATED_PROCESS_STARTED pid=1\nISOLATED_PROCESS_ENDED exit=0\nISOLATED_PROCESS_ENDED exit=1\n'):
            with self.assertRaises(ValueError): module.parse_exit(text)

    def test_out_of_range(self):
        with self.assertRaises(ValueError): self.parse(0x100000000)
