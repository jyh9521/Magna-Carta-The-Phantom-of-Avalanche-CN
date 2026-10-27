"""Locale catalog, native call-site identity and owned title-version regression."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_title_version as catalog
import build_compiled_release as release


class CatalogTests(unittest.TestCase):
    def test_release_labels(self):
        data = catalog.labels(ROOT/'locales/zh-CN/title-version.json')
        self.assertEqual(data['original_prefix'], 'Original: ')
        self.assertEqual(data['patch_line'], 'CN Localization & Enhancement Patch: v1.0.0')

    def test_generated_header_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'a.h', Path(tmp)/'b.h'
            for p in (a, b):
                catalog.build(ROOT/'locales/zh-CN/title-version.json', p)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertIn(b'constexpr char titlePatchLine[]', a.read_bytes())

    def test_rejects_control_codes_overflow_and_unknown_fields(self):
        base = catalog.labels(ROOT/'locales/zh-CN/title-version.json')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'label.json'
            for delta in ({'patch_line': ''}, {'patch_line': 'a'*81}, {'original_prefix': 'a'*25},
                          {'patch_line': '\n'}, {'patch_line': '\0'}, {'patch_line': '汉字'},
                          {'schema': True}, {'schema': 2}, {'background': '#123456'}):
                with self.subTest(delta=delta):
                    p.write_text(json.dumps(dict(base, **delta)), encoding='utf8')
                    with self.assertRaises(ValueError):
                        catalog.labels(p)

    @unittest.skipUnless((ROOT/'runtime/data/MCAlpha.dll').exists(), 'Matching game input not supplied')
    def test_source_locked_native_call_sites(self):
        import pefile
        data = (ROOT/'runtime/data/MCAlpha.dll').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), '7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e')
        pe = pefile.PE(data=data)
        self.assertEqual(pe.FILE_HEADER.TimeDateStamp, 0x3ed73966)
        self.assertEqual(pe.get_data(0xb6fad, 5), bytes.fromhex('e8 8e e0 f8 ff'))
        self.assertEqual(pe.get_data(0xb7046, 5), bytes.fromhex('e8 35 64 f9 ff'))
        self.assertEqual(pe.get_data(0xf1748, 8), b'v%.2f%s\0')

    @unittest.skipUnless(os.name == 'nt' and (ROOT/'build/native/Release/title_version_fixture.exe').exists(), 'Native Win32 fixture not built')
    def test_native_baseline_modified_rollback(self):
        for mode in ('baseline', 'modified', 'rollback', 'legacy-abi'):
            with self.subTest(mode=mode):
                result = subprocess.run([str(ROOT/'build/native/Release/title_version_fixture.exe'), '--'+mode], capture_output=True, text=True, check=True)
                self.assertIn('TITLE_VERSION_'+mode.upper().replace('-', '_')+' PASS', result.stdout)
                self.assertIn('game_started=false', result.stdout)

    @unittest.skipUnless(os.name == 'nt' and (ROOT/'build/native/Release/title_version_fixture.exe').exists(), 'Native Win32 fixture not built')
    def test_actual_null_constructor_is_not_suppressed(self):
        result=subprocess.run([str(ROOT/'build/native/Release/title_version_fixture.exe'), '--null-constructor'],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertIn('MCTitle.cpp:282 pNumber != NULL',result.stderr)


class ProfilePackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = (b'owned fixture ' + release.TITLE_MARKER + b' Original: \0'
                     b'CN Localization & Enhancement Patch: v1.0.0\0')
        self.names = (*release.PROFILE_MODULES, 'modules/minimap.dll')
        self.payload = {name: b'old' for name in self.names}
        self.manifest = {'files': {name: 'old' for name in self.names}}
        self.current = {'files': {name: release.raw_sha(self.data) for name in self.names}}
        for name in self.names:
            p = self.root/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(self.data)

    def refresh(self, protected=()):
        return release.refresh_profiles(self.payload, self.manifest, self.current, self.root, protected, ROOT/'locales/zh-CN')

    def test_all_routes_updated_and_no_background(self):
        title = self.refresh()
        self.assertEqual(set(title['modules']), set(self.names))
        self.assertEqual(title['background'], 'none')
        self.assertEqual(title['native_abi'], 'preserve-ebx-esi-edi')
        self.assertTrue(all(b == self.data for b in self.payload.values()))

    def test_all_legacy_v1_routes_rejected_before_payload_changes(self):
        data=self.data.replace(release.TITLE_MARKER, 'TITLE_VERSION_V1'.encode('utf-16le'))
        for name in self.names:
            (self.root/name).write_bytes(data)
            self.current['files'][name]=release.raw_sha(data)
        with self.assertRaisesRegex(ValueError, 'Unfixed title-version V1'):
            self.refresh()
        self.assertTrue(all(b == b'old' for b in self.payload.values()))

    def test_one_stale_route_is_rejected_atomically(self):
        name = self.names[3]
        (self.root/name).write_bytes(b'old profile')
        self.current['files'][name] = release.raw_sha(b'old profile')
        with self.assertRaisesRegex(ValueError, 'Mixed title-version'):
            self.refresh()
        self.assertTrue(all(b == b'old' for b in self.payload.values()))

    def test_map_route_can_be_added_to_the_original_accepted_overlay(self):
        self.payload.pop('modules/minimap.dll')
        self.manifest['files'].pop('modules/minimap.dll')
        self.refresh()
        self.assertEqual(self.payload['modules/minimap.dll'], self.data)

    def test_checksum_drift_is_rejected(self):
        (self.root/self.names[0]).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'profile drift'):
            self.refresh()

    def test_original_game_resource_is_never_replaced(self):
        with self.assertRaisesRegex(ValueError, 'owned runtime profile'):
            self.refresh(protected=(self.names[0],))

    def test_locale_drift_is_rejected(self):
        name = self.names[-1]
        data = self.data.replace(b'v1.0.0', b'v9.9.9')
        (self.root/name).write_bytes(data)
        self.current['files'][name] = release.raw_sha(data)
        with self.assertRaisesRegex(ValueError, 'Mixed title-version'):
            self.refresh()


if __name__ == '__main__':
    unittest.main()
