import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import driver_candidate as tool


class DriverTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'; self.game.mkdir()
        (self.game / 'Drv').mkdir()
        (self.game / 'fixture.bin').write_bytes(b'engine')
        self.source = self.root / 'source'; self.source.mkdir()
        self.old = {}; self.new = {}
        for name in tool.ORIGINAL:
            (self.game / 'Drv' / name).write_bytes(b'old-' + name.encode())
            (self.source / name).write_bytes(b'new-' + name.encode())
            self.old[name] = tool.sha((self.game / 'Drv' / name).read_bytes())
            self.new[name] = tool.sha((self.source / name).read_bytes())
        self.expected = {'fixture.bin': tool.sha(b'engine')}

    def apply(self):
        return tool.apply(self.game, self.root, self.source, self.expected, self.old, self.new)

    def restore(self):
        tool.rollback(self.game, self.root, self.expected, self.old, self.new)

    def test_roundtrip(self):
        self.apply()
        for n in self.new: self.assertEqual(tool.sha((self.game/'Drv'/n).read_bytes()),self.new[n])
        self.restore()
        for n in self.old: self.assertEqual(tool.sha((self.game/'Drv'/n).read_bytes()),self.old[n])
        self.assertEqual((self.game/'fixture.bin').read_bytes(), b'engine')

    def test_unknown_source_rejected_before_writes(self):
        (self.source/'AsrGlDrv.dll').write_bytes(b'unknown')
        with self.assertRaises(ValueError): self.apply()
        self.assertFalse((self.game/tool.BACKUP).exists())

    def test_layer_rejected(self):
        (self.game/'ddraw.dll').write_bytes(b'layer')
        with self.assertRaises(ValueError): self.apply()

    def test_changed_backup_preserved(self):
        self.apply(); (self.game/tool.BACKUP/'AsrGlDrv.dll').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.restore()
        self.assertEqual(tool.sha((self.game/'Drv/AsrD3DDrv.dll').read_bytes()),self.new['AsrD3DDrv.dll'])

    def test_changed_candidate_preserved(self):
        self.apply(); (self.game/'Drv/AsrGlDrv.dll').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.restore()

    def test_existing_history_rejected(self):
        self.apply()
        with self.assertRaises(ValueError): self.apply()

    def test_write_failure_restores_originals(self):
        replace = tool.replace_bytes
        calls = 0
        def fail_second(path, data):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError('fixture failure')
            return replace(path, data)
        with patch.object(tool, 'replace_bytes', fail_second):
            with self.assertRaises(OSError): self.apply()
        for n in self.old: self.assertEqual(tool.sha((self.game/'Drv'/n).read_bytes()),self.old[n])

if __name__ == '__main__': unittest.main()
