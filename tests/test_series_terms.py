import hashlib
import sys
from pathlib import Path
import struct
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_series_terms as m
from resource_sgi import catalog
from test_text_probe import fixture


HEADER = ['Source', 'Target', 'Category', 'Status', 'Notes']


def reference(text=None):
    text = text or '| Source | Target | Category | Status | Notes |\n|---|---|---|---|---|\n| full term | inherited | item | locked | context |\n'
    data = text.encode('utf8')
    lock = dict(repository='https://example.invalid/reference', commit='a' * 40,
                path='GLOSSARY.md', sha256=hashlib.sha256(data).hexdigest(),
                header=HEADER, locked_status='locked')
    return m.glossary(data, lock), lock


def source(text='full term'):
    return dict(resource='fixture.sgi', sha256='b' * 64,
                records=[dict(id='fixture.sgi:name:0:5', source=text, identifier=5, ordinal=0)])


def decision(rows):
    return dict(id='fixture.sgi:name:0:5', relation='confirmed_shared', evidence='manually verified same concept',
                source='full term', reference_line=rows[0]['line'], reference_source='full term')


class SeriesTests(unittest.TestCase):
    def test_reference_hash_locked(self):
        rows, lock = reference()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            m.glossary(b'changed', lock)

    def test_full_commit_required(self):
        data = b'| Source | Target | Category | Status | Notes |\n'
        lock = dict(sha256=hashlib.sha256(data).hexdigest(), commit='main')
        with self.assertRaisesRegex(ValueError, 'full hash'): m.glossary(data, lock)

    def test_escaped_pipe_and_unrelated_table(self):
        text = '| Source | Target | Category | Status | Notes |\n|---|---|---|---|---|\n| full term | inherited | item | locked | a\\|b |\n\n| Person | Sex | Pronoun | Alias |\n| A | B | C | D |\n'
        rows, lock = reference(text)
        self.assertEqual(len(rows), 1); self.assertEqual(rows[0]['notes'], 'a|b')

    def test_same_source_different_meaning_not_merged(self):
        rows, lock = reference('| Source | Target | Category | Status | Notes |\n|---|---|---|---|---|\n| full term | one | system | locked | meaning one |\n| full term | two | item | locked | meaning two |\n')
        report = m.compare(source(), rows, lock)
        self.assertEqual(len(report['records'][0]['candidates']), 2)
        self.assertEqual(report['confirmed_shared_count'], 0)
        self.assertIsNone(report['records'][0]['expected'])

    def test_no_substring_or_similarity_matching(self):
        rows, lock = reference()
        for text in ['long full term', 'full-term', 'full term(extra)', 'Full term']:
            self.assertEqual(m.compare(source(text), rows, lock)['records'][0]['candidates'], [])

    def test_exact_name_stays_pending(self):
        rows, lock = reference(); report = m.compare(source(), rows, lock)
        self.assertEqual(report['records'][0]['relation'], 'pending')
        self.assertEqual(report['auto_merged_ids'], 0)

    def test_confirmed_translation_inherits_locked_target(self):
        rows, lock = reference()
        report = m.compare(source(), rows, lock, [decision(rows)],
                           [dict(id='fixture.sgi:name:0:5', target='inherited')])
        self.assertEqual(report['records'][0]['expected'], 'inherited')
        self.assertEqual(report['conflicts'], [])

    def test_conflict_recorded_for_confirmed_concept(self):
        rows, lock = reference()
        report = m.compare(source(), rows, lock, [decision(rows)],
                           [dict(id='fixture.sgi:name:0:5', target='different English-derived name')])
        self.assertEqual(report['conflicts'][0]['expected'], 'inherited')
        self.assertEqual(len(report['conflicts']), 1)

    def test_pending_translation_not_forced(self):
        rows, lock = reference()
        report = m.compare(source(), rows, lock, [], [dict(id='fixture.sgi:name:0:5', target='different concept')])
        self.assertEqual(report['conflicts'], [])

    def test_confirmation_requires_evidence(self):
        rows, lock = reference(); d = decision(rows); d['evidence'] = ''
        with self.assertRaisesRegex(ValueError, 'explicit evidence'): m.compare(source(), rows, lock, [d])

    def test_stale_source_or_reference_refused(self):
        rows, lock = reference(); d = decision(rows); d['reference_source'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'stale'): m.compare(source(), rows, lock, [d])

    def test_unlocked_upstream_refused(self):
        rows, lock = reference(); rows[0]['status'] = 'draft'
        with self.assertRaisesRegex(ValueError, 'not locked'): m.compare(source(), rows, lock, [decision(rows)])

    def test_duplicate_or_unknown_translation_id_refused(self):
        rows, lock = reference(); t = dict(id='fixture.sgi:name:0:5', target='x')
        with self.assertRaises(ValueError): m.compare(source(), rows, lock, [], [t, t])
        with self.assertRaises(ValueError): m.compare(source(), rows, lock, [], [dict(id='unknown', target='x')])

    def test_catalog_preserves_ids_ordinals_raw_bytes(self):
        data = bytearray(fixture()); struct.pack_into('<I', data, 172, 5)
        rows = catalog(bytes(data), 'fixture.sgi')['records']
        self.assertEqual(rows[0]['identifier'], rows[1]['identifier'])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[0]['source_hex'], bytes(data[12:25]).hex())
        self.assertEqual(rows[1]['ordinal'], 1)

    def test_catalog_keeps_whitespace_and_no_translation(self):
        data = bytearray(fixture()); data[12:26] = b' A B ' + b'\0' * 9
        report = catalog(bytes(data), 'fixture.sgi')
        self.assertEqual(report['records'][0]['source'], ' A B ')
        self.assertIsNone(report['records'][0]['target'])
        self.assertTrue(report['roundtrip_exact'])


if __name__ == '__main__': unittest.main()
