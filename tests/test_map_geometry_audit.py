from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from audit_map_geometry import audit


class MapGeometryAuditTests(unittest.TestCase):
    def test_empty_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertRaisesRegex(ValueError, 'No WRD', audit, Path(d))

    def test_unknown_resource_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); sample = root/'0001.wrd'; sample.write_bytes(b'owned unknown format')
            result = audit(root)
            self.assertEqual(len(result['rejected']), 1)
            self.assertEqual(result['accepted'], [])
            self.assertEqual(sample.read_bytes(), b'owned unknown format')
            self.assertFalse(result['game_started'])

    def test_report_never_overwrites_existing_file_or_source_tree(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/'source'; source.mkdir()
            existing = root/'existing.json'; existing.write_bytes(b'keep report')
            for output in [existing, source/'report.json']:
                result = subprocess.run([sys.executable, str(ROOT/'tools/audit_map_geometry.py'),
                                         '--source', str(source), '--report', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('Report must be new and outside source data', result.stderr)
            self.assertEqual(existing.read_bytes(), b'keep report')
            self.assertFalse((source/'report.json').exists())
