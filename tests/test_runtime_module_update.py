"""Small owned-file deployment fixtures; no game data or executable entry points."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import update_runtime_modules as update
import build_text_runtime_update as package


def dll(tag):
    data = bytearray(512)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<H', data, 132, 0x14c)
    struct.pack_into('<H', data, 150, 0x2000)
    struct.pack_into('<H', data, 152, 0x10b)
    data[256:256+len(tag)] = tag
    return bytes(data)


class ModuleUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base/'runtime'
        self.root.mkdir()
        files = {'Start.ps1': b'owned entry, not executed', **{n: dll(n.encode()) for n in update.MODULES}}
        for name, data in files.items():
            path = self.root/name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
        manifest = dict(schema=1, files={n: update.digest(b) for n, b in files.items()})
        (self.root/'runtime.json').write_text(json.dumps(manifest))
        (self.root/'enhancements.json').write_bytes(b'user settings')
        (self.root/'MC00.sav').write_bytes(b'user save')
        self.module = self.base/'candidate.dll'
        self.module.write_bytes(dll(b'new owned source'))
        self.record = self.base/'record'
        self.before = self.snapshot()
        p = patch.object(update, 'idle')
        p.start()
        self.addCleanup(p.stop)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def apply(self):
        return update.apply(self.root, self.module, self.record)

    def test_roundtrip_preserves_settings_saves_and_restores_manifest_bytes(self):
        self.apply()
        for name in update.MODULES:
            self.assertEqual((self.root/name).read_bytes(), self.module.read_bytes())
        self.assertEqual((self.root/'enhancements.json').read_bytes(), b'user settings')
        self.assertEqual((self.root/'MC00.sav').read_bytes(), b'user save')
        # Mutable settings changed since deployment must also survive rollback.
        (self.root/'enhancements.json').write_bytes(b'new user settings')
        update.rollback(self.record)
        expected = dict(self.before, **{'enhancements.json': b'new user settings'})
        self.assertEqual(self.snapshot(), expected)

    def test_input_drift_rejects_before_creating_record(self):
        (self.root/'Start.ps1').write_bytes(b'changed entry')
        before = self.snapshot()
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.record.exists())

    def test_rollback_drift_rejects_whole_batch(self):
        self.apply()
        (self.root/update.MODULES[4]).write_bytes(b'later edit')
        before = self.snapshot()
        with self.assertRaises(ValueError): update.rollback(self.record)
        self.assertEqual(before, self.snapshot())

    def test_backup_drift_rejects_whole_batch(self):
        self.apply()
        (self.record/'original'/update.MODULES[2]).write_bytes(b'corrupt backup')
        before = self.snapshot()
        with self.assertRaises(ValueError): update.rollback(self.record)
        self.assertEqual(before, self.snapshot())

    def test_interrupted_apply_restores_original_files(self):
        original = update.write_file
        failed = False
        def once(path, data):
            nonlocal failed
            if path == self.root/update.MODULES[3] and not failed:
                failed = True
                raise OSError('injected write failure')
            original(path, data)
        with patch.object(update, 'write_file', side_effect=once):
            with self.assertRaises(OSError): self.apply()
        self.assertEqual(self.snapshot(), self.before)

    def test_unknown_module_format_rejected(self):
        for data in (b'not PE', dll(b'bad')[:140]):
            self.module.write_bytes(data)
            with self.assertRaises(ValueError): self.apply()
        self.assertEqual(self.snapshot(), self.before)

    def test_rollback_path_injection_rejected(self):
        self.apply()
        journal = json.loads((self.record/'changes.json').read_text())
        journal['changes'][0]['path'] = '../outside'
        (self.record/'changes.json').write_text(json.dumps(journal))
        before = self.snapshot()
        with self.assertRaises(ValueError): update.rollback(self.record)
        self.assertEqual(before, self.snapshot())

    def test_module_and_record_must_be_external(self):
        with self.assertRaises(ValueError):
            update.apply(self.root, self.root/update.MODULES[0], self.record)
        with self.assertRaises(ValueError):
            update.apply(self.root, self.module, self.root/'record')
        self.assertEqual(self.snapshot(), self.before)

    def test_owned_module_journal_builds_existing_player_updater(self):
        self.apply()
        output = self.base/'update.zip'
        package.build(self.root, self.record, output)
        import zipfile
        with zipfile.ZipFile(output) as archive:
            self.assertIsNone(archive.testzip())
            manifest = json.loads(archive.read('package.json'))
            self.assertEqual({r['path'] for r in manifest['files']}, set(update.CHANGES))
            self.assertTrue(all(not r['delta'] for r in manifest['files']))


if __name__ == '__main__':
    unittest.main()
