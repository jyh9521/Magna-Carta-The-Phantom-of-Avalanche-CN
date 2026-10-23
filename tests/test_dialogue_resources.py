from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import audit_dialogue_resources as audit
from resource_fpb import rebuild


def owned_field(tag=17, voice=2):
    header = bytearray(1060)
    struct.pack_into('<i', header, 8, 7)
    command = struct.pack('<15i', 700, 10000, 100, 0, 100, 0, 1, tag, voice, 90, 0, 0, 0, 0, 0)
    tail = struct.pack('<4i', 1, 0, 0, 1) + command
    return bytes(header)+bytes(24)+tail


def owned_sound():
    header = bytearray(56)
    header[:4] = audit.MAGIC
    struct.pack_into('<III', header, 4, 1, 1, 18)
    return bytes(header)+b'owned-compressed-audio'


class DialogueResourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        for folder in ('Field', 'Fpb', 'SVD'):
            (self.source/folder).mkdir(parents=True)
        (self.source/'Field/0001.fld').write_bytes(owned_field())
        (self.source/'Fpb/0007.fpb').write_bytes(rebuild([(17, b'AB$nCD')]))
        (self.source/'SVD/0002.SVD').write_bytes(owned_sound())

    def test_script_binding_is_tag_not_ordinal_and_no_text_payload(self):
        result = audit.audit(self.source)
        row = result['selected'][0]
        self.assertEqual((row['text_tag'], row['text_ordinal'], row['voice_id']), (17, 0, 2))
        self.assertEqual(row['text_sha256'], audit.digest(b'AB$nCD'))
        self.assertEqual(result['counts']['text_resolved'], 1)
        self.assertNotIn('AB$nCD', json.dumps(result))
        self.assertFalse(result['game_started'])

    def test_missing_text_and_voice_rejected(self):
        (self.source/'Field/0001.fld').write_bytes(owned_field(tag=18))
        with self.assertRaisesRegex(ValueError, 'Missing dialogue tag'):
            audit.audit(self.source)
        (self.source/'Field/0001.fld').write_bytes(owned_field(voice=3))
        with self.assertRaisesRegex(ValueError, 'Missing original voice'):
            audit.audit(self.source)

    def test_explicit_silent_command(self):
        (self.source/'Field/0001.fld').write_bytes(owned_field(voice=-1))
        result = audit.audit(self.source)
        self.assertEqual(result['counts']['voice_none'], 1)
        self.assertNotIn('audio', result['selected'][0])

    def test_duplicate_fpb_tag_rejected(self):
        (self.source/'Fpb/0007.fpb').write_bytes(rebuild([(17, b'A'), (17, b'B')]))
        with self.assertRaisesRegex(ValueError, 'Duplicate FPB tag'):
            audit.audit(self.source)

    def test_unknown_field_is_explicit_and_known_field_still_audited(self):
        (self.source/'Field/0002.fld').write_bytes(b'unsupported variant')
        result = audit.audit(self.source)
        self.assertEqual(len(result['rejected_fields']), 1)
        self.assertEqual(result['counts']['accepted_fields'], 1)

    def test_report_and_cache_cannot_overwrite_source(self):
        with self.assertRaisesRegex(ValueError, 'outside the resource root'):
            audit.audit(self.source, cache=self.source/'cache')
        with self.assertRaisesRegex(ValueError, 'outside the resource root'):
            audit.outside_source(self.source/'report.json', self.source)

    def test_source_drift_during_audit_is_rejected(self):
        original = audit.parse_sound
        def drift(data):
            (self.source/'Fpb/0007.fpb').write_bytes(rebuild([(17, b'changed')]))
            return original(data)
        with patch.object(audit, 'parse_sound', side_effect=drift):
            with self.assertRaisesRegex(ValueError, 'Resource changed during audit'):
                audit.audit(self.source)

    def test_sound_header_and_cache_bind_source_and_decoder(self):
        sound = owned_sound()
        decoder = dict(path='owned-decoder', executable_sha256='a'*64, version_sha256='b'*64)
        decoded = dict(exit_status=0, sample_rate=44100, pcm_samples=44100,
                       pcm_sha256='c'*64, duration_seconds=1.0)
        cache = self.root/'cache'
        with patch.object(audit, 'decode_pcm', return_value=decoded) as decode:
            first = audit.decode_cached(sound, decoder, cache)
            second = audit.decode_cached(sound, decoder, cache)
            self.assertFalse(first['cache_hit'])
            self.assertTrue(second['cache_hit'])
            self.assertEqual(decode.call_count, 1)
            audit.decode_cached(sound+b'changed', decoder, cache)
            self.assertEqual(decode.call_count, 2)
            changed_decoder = dict(decoder, executable_sha256='d'*64)
            audit.decode_cached(sound, changed_decoder, cache)
            self.assertEqual(decode.call_count, 3)
        item = cache/(first['cache_key']+'.json')
        value = json.loads(item.read_text('utf8'))
        value['result']['pcm_samples'] = 0
        item.write_text(json.dumps(value), encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'cache identity or content mismatch'):
            audit.decode_cached(sound, decoder, cache)

    def test_both_wrapper_versions_have_exact_payload_offsets(self):
        short = audit.parse_sound(owned_sound())
        self.assertEqual(short['header_bytes'], 56)
        zero_metadata = bytearray(owned_sound())
        struct.pack_into('<I', zero_metadata, 4, 0xc5826848)
        self.assertEqual(audit.parse_sound(zero_metadata)['header_bytes'], 56)
        header = bytearray(108)
        header[:4] = audit.MAGIC
        header[4:56] = b'SoftMax(C) 2001, SED File V0.1a, Dev#4 han-kue, Park'
        struct.pack_into('<II', header, 60, 1, 18)
        legacy = audit.parse_sound(bytes(header)+b'owned-audio')
        self.assertEqual(legacy['header_bytes'], 108)
        self.assertEqual((short['storage_word'], short['filter_word']), (1, 18))
        self.assertEqual((legacy['storage_word'], legacy['filter_word']), (1, 18))

    def test_truncated_or_unknown_wrapper_rejected(self):
        for value in (b'', bytes(200), owned_sound()[:56]):
            with self.assertRaises(ValueError):
                audit.parse_sound(value)


if __name__ == '__main__':
    unittest.main()
