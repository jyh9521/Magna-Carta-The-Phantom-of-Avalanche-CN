import copy
import hashlib
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from resource_fixed_text import fields, rebuild_fixed, checked_decisions


class FixedTextTests(unittest.TestCase):
    def fixture(self, ext='.itm'):
        size = {'.itm': 264, '.sgi': 164, '.abi': 344, '.cha': 267}[ext]
        block = bytearray(b'\xa5' * size)
        struct.pack_into('<I', block, 0, 77)
        block[4:4 + (60 if ext == '.abi' else 100)] = bytes(60 if ext == '.abi' else 100)
        block[4:7] = b'old'
        if ext == '.itm':
            block[164:264] = bytes(100)
            block[164:168] = b'desc'
        original = struct.pack('<II', 1, 0x12345678) + block
        resource = 'sample' + ext
        catalog = fields(original, resource)
        targets = [dict(id=r['id'], source_sha256=hashlib.sha256(bytes.fromhex(r['source_hex'])).hexdigest(),
                        target='new', state='translated') for r in catalog]
        policy = dict(schema=1, decisions=[dict(id=t['id'], source_sha256=t['source_sha256'],
                       field_semantics='display_name' if r['field'] == 'name' else 'display_description',
                       evidence='controlled numeric-ID display consumer fixture')
                       for r, t in zip(catalog, targets)])
        return original, resource, catalog, targets, {}, policy

    def test_all_layouts_preserve_header_attributes_and_length(self):
        for ext in ('.itm', '.sgi', '.abi', '.cha'):
            args = self.fixture(ext)
            result = rebuild_fixed(*args)
            self.assertEqual(len(result), len(args[0]))
            self.assertEqual(result[:12], args[0][:12])
            for row in args[2]:
                self.assertEqual(result[row['offset']:row['offset'] + 4], b'new\0')
            self.assertEqual(result[-40:], args[0][-40:])

    def test_unknown_layout_and_truncation_are_rejected(self):
        with self.assertRaises(ValueError): fields(b'', 'test.unknown')
        for ext in ('.itm', '.sgi', '.abi', '.cha'):
            args = self.fixture(ext)
            with self.assertRaises(ValueError): fields(args[0][:-1], args[1])

    def test_catalog_offset_id_and_capacity_spoofing_are_rejected(self):
        for key in ('offset', 'identifier', 'ordinal', 'candidate_capacity'):
            args = list(self.fixture())
            args[2][0][key] += 1
            with self.assertRaisesRegex(ValueError, 'catalog'): rebuild_fixed(*args)

    def test_missing_and_duplicate_targets_are_rejected(self):
        args = list(self.fixture())
        args[3].pop()
        with self.assertRaises(ValueError): rebuild_fixed(*args)
        args = list(self.fixture())
        args[3].append(copy.deepcopy(args[3][0]))
        with self.assertRaises(ValueError): rebuild_fixed(*args)

    def test_policy_requires_unique_source_bound_evidence(self):
        for change in ('missing', 'stale', 'duplicate', 'evidence'):
            args = list(self.fixture())
            p = args[5]['decisions']
            if change == 'missing': p.pop()
            if change == 'stale': p[0]['source_sha256'] = '0' * 64
            if change == 'duplicate': p.append(copy.deepcopy(p[0]))
            if change == 'evidence': p[0]['evidence'] = ''
            with self.assertRaises(ValueError): rebuild_fixed(*args)

    def test_formatter_budget_is_stricter_than_disk_capacity(self):
        for ext, limit in (('.sgi', 39), ('.itm', 39), ('.cha', 39), ('.abi', 59)):
            args = list(self.fixture(ext))
            args[3][0]['target'] = 'x' * limit
            rebuild_fixed(*args)
            args[3][0]['target'] += 'x'
            with self.assertRaisesRegex(ValueError, 'budget overflow'): rebuild_fixed(*args)

    def test_description_terminator_budget(self):
        args = list(self.fixture())
        args[3][1]['target'] = 'd' * 99
        rebuild_fixed(*args)
        args[3][1]['target'] += 'd'
        with self.assertRaisesRegex(ValueError, 'overflow'): rebuild_fixed(*args)

    def test_internal_object_policy_never_rewrites_label(self):
        args = list(self.fixture('.cha'))
        args[5]['decisions'][0]['field_semantics'] = 'internal_object_label'
        with self.assertRaisesRegex(ValueError, 'not approved'): rebuild_fixed(*args)
        args[3][0].update(state='preserved', target=None, preservation_evidence='controlled object label')
        self.assertEqual(rebuild_fixed(*args), args[0])
        args[5]['decisions'][0]['field_semantics'] = 'display_name'
        with self.assertRaisesRegex(ValueError, 'silently preserved'): rebuild_fixed(*args)

    def test_nonzero_padding_outside_replacement_span_is_preserved(self):
        args = list(self.fixture('.sgi'))
        data = bytearray(args[0]); data[40] = 0xb1; args[0] = bytes(data)
        result = rebuild_fixed(*args)
        self.assertEqual(result[40], 0xb1)

    def test_expansion_refuses_unknown_nonzero_padding(self):
        args = list(self.fixture('.sgi'))
        data = bytearray(args[0]); data[16] = 0xb1; args[0] = bytes(data)
        args[3][0]['target'] = 'longer'
        with self.assertRaisesRegex(ValueError, 'nonzero field padding'): rebuild_fixed(*args)


if __name__ == '__main__': unittest.main()
