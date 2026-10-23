"""Owned-only capture integration transactions; never invoke a game or launcher."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import integrate_shared_capture as tool


class SharedCaptureIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'runtime'
        (self.root/'modules').mkdir(parents=True)
        (self.root/'data').mkdir()
        (self.root/'config').mkdir()
        self.record = self.base/'transaction'
        self.start = b'# owned old Start template\n'
        (self.root/'Start.ps1').write_bytes(self.start)
        (self.root/'modules/current.dll').write_bytes(b'owned existing module')
        (self.root/'data/resource.bin').write_bytes(b'owned game data stand-in')
        (self.root/'data/slot.sav').write_bytes(b'owned save')
        (self.root/'config/enhancements.json').write_bytes(b'owned mutable settings')
        self.helper = self.base/'helper.exe'
        pe = bytearray(512);pe[:2] = b'MZ';struct.pack_into('<I', pe, 0x3c, 0x80)
        pe[0x80:0x84] = b'PE\0\0';struct.pack_into('<HH', pe, 0x84, 0x14c, 1)
        struct.pack_into('<HHH', pe, 0x94, 224, 0x0102, 0x10b)
        self.helper.write_bytes(pe)
        self.manifest = dict(schema=1, files={name:tool.digest((self.root/name).read_bytes())
                            for name in ('Start.ps1', 'modules/current.dll')}, recipes={'configured':{'module':'current'}})
        self.save_manifest()
        self.addCleanup(patch.stopall)
        patch.object(tool, 'BASE_START_SHA', tool.digest(self.start)).start()
        self.idle = patch.object(tool, 'idle').start()

    def save_manifest(self):
        (self.root/'runtime.json').write_text(json.dumps(self.manifest)+'\n', encoding='utf8')

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def apply(self):
        return tool.apply(self.root, self.helper, self.record)

    def test_four_existing_optional_file_states_restore_exactly(self):
        for helper, entry in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(helper=helper, entry=entry):
                for exists, name in ((helper, tool.CHANGES[1]), (entry, tool.CHANGES[2])):
                    if exists:
                        (self.root/name).write_bytes(b'owned prior '+name.encode())
                        self.manifest['files'][name] = tool.digest((self.root/name).read_bytes())
                self.save_manifest()
                before = self.snapshot()
                self.record = self.base/('record-'+str(helper)+str(entry))
                journal = self.apply()
                current = tool.load_json((self.root/'runtime.json').read_bytes())
                self.assertEqual(current['recipes'], self.manifest['recipes'])
                self.assertEqual(set(current['files']) - set(self.manifest['files']),
                                 set(tool.CHANGES[:-1]) - set(self.manifest['files']))
                for name in ('modules/current.dll','data/resource.bin','data/slot.sav','config/enhancements.json'):
                    self.assertEqual((self.root/name).read_bytes(), before[name])
                self.assertFalse(journal['game_started'])
                tool.rollback(self.record)
                self.assertEqual(self.snapshot(), before)
                # Reset optional baseline for the next combination.
                for name in tool.CHANGES[1:3]:
                    (self.root/name).unlink(missing_ok=True)
                    self.manifest['files'].pop(name, None)

    def test_invalid_helper_leaves_no_record(self):
        self.helper.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'capture helper'):
            self.apply()
        self.assertFalse(self.record.exists())

    def test_hash_valid_but_unsupported_start_rejected(self):
        (self.root/'Start.ps1').write_bytes(b'unknown route')
        self.manifest['files']['Start.ps1'] = tool.digest(b'unknown route');self.save_manifest()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'baseline'):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.record.exists())

    def test_manifest_drift_or_unrecorded_destination_is_rejected(self):
        (self.root/tool.CHANGES[2]).write_bytes(b'unrecorded')
        with self.assertRaisesRegex(ValueError, 'Unrecorded'):
            self.apply()
        (self.root/tool.CHANGES[2]).unlink()
        (self.root/'modules/current.dll').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError, 'Runtime input changed'):
            self.apply()
        self.assertFalse(self.record.exists())

    def test_rollback_refuses_changed_output_or_backup(self):
        self.apply()
        target = self.root/tool.CHANGES[2];original = target.read_bytes()
        target.write_bytes(b'changed entry')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'drift'):
            tool.rollback(self.record)
        self.assertEqual(self.snapshot(), before)
        target.write_bytes(original)
        (self.record/'original/Start.ps1').write_bytes(b'changed backup')
        with self.assertRaisesRegex(ValueError, 'backup drift'):
            tool.rollback(self.record)

    def test_write_failure_restores_original_state(self):
        before = self.snapshot();real = tool.write_file
        def fail(path, data):
            if path == self.root/tool.CHANGES[1]:
                raise OSError('owned injected write failure')
            return real(path, data)
        with patch.object(tool, 'write_file', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_record_nesting_and_active_runtime_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Independent'):
            tool.apply(self.root, self.helper, self.root/'transaction')
        self.idle.side_effect = ValueError('owned active runtime')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'active runtime'):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.record.exists())


if __name__ == '__main__':
    unittest.main()
