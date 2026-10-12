from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import extract_text_catalog as m
from resource_fpb import rebuild


def table(extension, identifier=7, name='이름', description='설명'):
    size, fields = m.LAYOUTS[extension]
    record = bytearray(b'\x55' * size); struct.pack_into('<I', record, 0, identifier)
    for field, offset, capacity in fields:
        raw = (name if field == 'name' else description).encode('cp949') + b'\0'
        record[offset:offset + len(raw)] = raw
    return struct.pack('<II', 1, 0x11223344) + record


class CatalogTests(unittest.TestCase):
    def test_fixed_fields_with_unknown_bytes_preserved(self):
        for extension in ['.itm', '.abi', '.cha']:
            data = table(extension); rows = m.fixed_records(data, 'fixture'+extension, extension)
            self.assertEqual(rows[0]['identifier'], 7); self.assertEqual(rows[0]['source'], '이름')
            self.assertEqual(data, table(extension))
            self.assertEqual(rows[0]['offset'], 12)

    def test_character_names_do_not_imply_person_or_save_translation(self):
        rows=m.fixed_records(table('.cha',name='바퀴'),'Cha/0000.cha','.cha')
        self.assertEqual(rows[0]['source'],'바퀴')
        self.assertEqual(rows[0]['field_semantics'],'display_name_or_internal_object_name')
        self.assertTrue(rows[0]['save_name_override'])
        self.assertEqual(rows[0]['translation_eligibility'],'requires_per_record_role_review')
        self.assertEqual(rows[0]['candidate_capacity'],100)

    def test_description_offset_and_empty_field(self):
        rows = m.fixed_records(table('.itm', description=''), 'fixture.itm', '.itm')
        self.assertEqual(rows[1]['offset'], 172); self.assertEqual(rows[1]['source'], '')
        self.assertIsNone(rows[1]['target'])

    def test_count_truncation_and_terminator(self):
        for data in [b'', table('.abi')[:-1], table('.abi')+b'\0']:
            with self.assertRaises(ValueError): m.fixed_records(data, 'fixture.abi', '.abi')
        data = bytearray(table('.abi')); data[12:72] = b'A'*60
        with self.assertRaises(ValueError): m.fixed_records(bytes(data), 'fixture.abi', '.abi')

    def test_controls_are_kept_and_protected(self):
        raw = '앞$n %s {0} <tag>\n뒤'.encode('cp949')
        row = m.text_row('fixture.fpb', 0, 2, 'text', 20, raw)
        self.assertEqual(row['source_hex'], raw.hex())
        self.assertEqual(row['protected_tokens'], ['$n', '%s', '{0}', '<tag>', '\n'])

    def test_internal_whitespace_not_trimmed(self):
        row = m.text_row('fixture', 0, 1, 'name', 12, b' A  B ')
        self.assertEqual(row['source'], ' A  B ')

    def test_binary_scan_remains_quarantined(self):
        data = b'\0'+ '칼린츠'.encode('cp949')+b'\0'
        rows = m.heuristic_strings(data)
        self.assertEqual(rows[0]['offset'], 1)
        self.assertEqual(rows[0]['state'], 'quarantined_not_safe_to_patch')

    def test_whole_tree_inventory_keeps_opaque_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source=root/'input'; source.mkdir()
            (source/'test.fpb').write_bytes(rebuild([(1, '대사$n'.encode('cp949'))]))
            (source/'test.itm').write_bytes(table('.itm'))
            (source/'ui.bgr').write_bytes(b'opaque image fixture')
            (source/'unknown.dat').write_bytes(b'unknown')
            report=m.extract(source,root/'output')
            self.assertEqual(report['structured_fields'],3)
            self.assertEqual(report['input_files'],4)
            self.assertFalse(report['all_text_extracted'])
            self.assertEqual(len(report['pending_coverage']),2)

    def test_output_reuse_and_nested_output_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input';source.mkdir()
            with self.assertRaises(ValueError):m.extract(source,source/'output')
            output=root/'output';output.mkdir()
            with self.assertRaises(ValueError):m.extract(source,output)


if __name__ == '__main__': unittest.main()
