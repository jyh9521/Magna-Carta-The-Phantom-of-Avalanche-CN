"""A single overlay must supply every pinned input, including unchanged libraries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from test_compiled_desktop import make_owned_fixture, sha, blob, DEFAULT, ROOT
import build_compiled_desktop as compiler
import build_compiled_release as release
import verify_compiled_release as audit
import verify_unified_overlay as replay


@unittest.skipUnless(os.name == 'nt', 'Windows compiled desktop integration')
class CompleteOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='complete overlay template ')
        cls.base = Path(cls.temp.name)
        cls.template, cls.resources, cls.icon, cls.payload = make_owned_fixture(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='complete overlay case ')
        self.addCleanup(self.temp.cleanup)
        self.case = Path(self.temp.name)
        self.source_game = self.case/'matching source'
        self.source_game.mkdir()
        self.inputs = {'Asura.dll': b'owned supported animation library',
                       'Core.dll': b'owned core library',
                       'redist/provider.m3d': b'owned audio provider',
                       'FrameData/original.fdi': b'owned unchanged resource'}
        for name, data in self.inputs.items():
            p = self.source_game/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        self.runtime = json.loads((self.resources/'runtime.json').read_bytes())
        self.runtime['data'].update({n: sha(self.inputs[n]) for n in ('Asura.dll', 'FrameData/original.fdi')})
        self.overlay = json.loads((self.resources/'Overlay-Manifest.json').read_bytes())
        self.overlay['source_files'].update({n: sha(b) for n, b in self.inputs.items()})
        self.source = self.case/'accepted.zip'
        self.work = self.case/'build'
        self.output = self.case/'complete.zip'
        self.compatibility_plan = None

    def accepted(self):
        payload = dict(self.payload)
        for p in self.resources.rglob('*'):
            if p.is_file() and p.relative_to(self.resources).as_posix().startswith('config/'):
                payload[p.relative_to(self.resources).as_posix()] = p.read_bytes()
        payload['runtime.json'] = blob(self.runtime)
        manifest = dict(self.overlay, files={n: sha(b) for n, b in payload.items()})
        payload['Overlay-Manifest.json'] = blob(manifest)
        with zipfile.ZipFile(self.source, 'w') as z:
            for n, b in payload.items():
                z.writestr(n, b)
        return sha(self.source.read_bytes())

    def build(self):
        options = dict(compatibility_plan=self.compatibility_plan) if self.compatibility_plan else {}
        return release.build(self.source, self.accepted(), self.icon, self.work,
                             self.output, source_game=self.source_game, **options)

    def compatibility(self):
        import hashlib
        name = 'Field/legacy.fld'
        data = b'owned supported world resource'
        p = self.source_game/name
        p.parent.mkdir(parents=True)
        p.write_bytes(data)
        self.overlay['source_files'][name] = sha(data)
        identity = hashlib.sha256(json.dumps(self.overlay['source_files'],sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        plan = dict(schema=1, kind='baseline_compatibility', source_manifest_sha256=identity,
                    files={name: dict(source_sha256=sha(data), observed_sha256=sha(b'old world'))})
        self.compatibility_plan = self.case/'compatibility.json'
        self.compatibility_plan.write_bytes(blob(plan))
        return plan

    def test_compatibility_resources_are_included_in_the_same_zip(self):
        self.compatibility()
        self.build()
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read('Field/legacy.fld'), b'owned supported world resource')
        audit.verify(self.output, self.icon)
        runtime = json.loads((self.work/'resources/runtime.json').read_bytes())
        self.assertIn('Field/legacy.fld', runtime['data'])
        self.assertEqual(len(runtime['baseline_compatibility']['files']), 1)

    def test_compatibility_plan_is_bound_to_the_source_manifest(self):
        plan = self.compatibility()
        plan['source_manifest_sha256'] = '0'*64
        self.compatibility_plan.write_bytes(blob(plan))
        with self.assertRaisesRegex(ValueError, 'Compatibility.*manifest'):
            self.build()
        self.assertFalse(self.output.exists())

    def test_compatibility_plan_cannot_substitute_unknown_source_bytes(self):
        plan = self.compatibility()
        plan['files']['Field/legacy.fld']['source_sha256'] = sha(b'unknown')
        self.compatibility_plan.write_bytes(blob(plan))
        with self.assertRaisesRegex(ValueError, 'Compatibility.*source'):
            self.build()
        self.assertFalse(self.output.exists())

    def test_missing_source_is_rejected_instead_of_building_an_incomplete_zip(self):
        digest = self.accepted()
        with self.assertRaisesRegex(ValueError, 'Source game required'):
            release.build(self.source, digest, self.icon, self.work, self.output)
        self.assertFalse(self.output.exists())

    def test_every_runtime_input_and_native_provider_is_bundled_and_bound(self):
        self.build()
        report = audit.verify(self.output, self.icon)
        self.assertEqual(report['external_inputs'], 0)
        with zipfile.ZipFile(self.output) as z:
            for n, b in self.inputs.items():
                self.assertEqual(z.read(n), b)
        runtime = json.loads((self.work/'resources/runtime.json').read_bytes())
        self.assertTrue(runtime['complete_inputs']['required'])
        self.assertEqual(runtime['complete_inputs']['files'], runtime['data'])
        self.assertIn('Core.dll', runtime['data'])
        self.assertIn('redist/provider.m3d', runtime['data'])

    def test_corrupt_or_missing_source_stops_before_output(self):
        (self.source_game/'Core.dll').write_bytes(b'unknown version')
        with self.assertRaisesRegex(ValueError, 'input.*mismatch|input drift'):
            self.build()
        self.assertFalse(self.output.exists())

    def test_conflicting_payload_is_not_silently_replaced(self):
        self.runtime['data']['scene.bin'] = sha(b'other input')
        with self.assertRaisesRegex(ValueError, 'input.*mismatch|input drift'):
            self.build()
        self.assertFalse(self.output.exists())

    def test_audit_no_longer_accepts_a_source_manifest_as_missing_payload(self):
        resources = self.case/'legacy resources'
        shutil.copytree(self.resources, resources)
        (resources/'runtime.json').write_bytes(blob(self.runtime))
        (resources/'Overlay-Manifest.json').write_bytes(blob(self.overlay))
        core = self.case/'legacy.dll'
        compiler.core(core, resources)
        archive = self.case/'legacy compiled.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for n, b in dict(self.payload, **{'modules/DesktopRuntime.dll': core.read_bytes()}).items():
                z.writestr(n, b)
        with self.assertRaisesRegex(ValueError, 'Missing bundled runtime input'):
            audit.verify(archive, self.icon)

    def test_one_overlay_replaces_old_library_and_preserves_user_files(self):
        self.build()
        installed = self.case/'existing installation'
        shutil.copytree(self.template, installed)
        (installed/'Asura.dll').write_bytes(b'owned incompatible old library')
        (installed/'MC00.SAV').write_bytes(b'personal save')
        (installed/'user-note.txt').write_bytes(b'untouched user file')
        key = sha(str(installed.resolve()).rstrip('\\/').upper().encode())[:16]
        local = self.case/'user data'
        settings = local/'MagnaCarta/Installations'/key/'enhancements.json'
        settings.parent.mkdir(parents=True)
        settings.write_bytes(blob(dict(DEFAULT, resolution='auto', frame_rate=30)))
        original_settings = settings.read_bytes()
        with zipfile.ZipFile(self.output) as z:
            z.extractall(installed)
        env = dict(os.environ, LOCALAPPDATA=str(local))
        for arg in ('--check-installed', '--verify-only'):
            result = subprocess.run([str(installed/'Game.exe'), arg], env=env,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0,
                             (settings.parent/'cache/Game.log').read_text(encoding='utf-8-sig'))
        self.assertEqual((installed/'Asura.dll').read_bytes(), self.inputs['Asura.dll'])
        self.assertEqual((installed/'MC00.SAV').read_bytes(), b'personal save')
        self.assertEqual((installed/'user-note.txt').read_bytes(), b'untouched user file')
        self.assertEqual(settings.read_bytes(), original_settings)


class SparseRollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sparse rollback ')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.main = self.work/'modified-copy'
        self.restored = self.work/'rollback-copy'
        self.main.mkdir()
        self.restored.mkdir()
        for name in ('library.dll', 'added.bin'):
            (self.main/name).write_bytes(b'new bytes')
            os.link(self.main/name, self.restored/name)
        (self.work/'before').mkdir()
        (self.work/'before/library.dll').write_bytes(b'old bytes')
        self.state = {'library.dll': dict(before=sha(b'old bytes'), after=sha(b'new bytes')),
                      'added.bin': dict(before=None, after=sha(b'new bytes'))}
        (self.work/'rollback-state.json').write_bytes(blob(self.state))

    def test_rollback_does_not_modify_the_primary_hardlinked_fixture(self):
        replay.rollback(self.work)
        self.assertEqual((self.restored/'library.dll').read_bytes(), b'old bytes')
        self.assertFalse((self.restored/'added.bin').exists())
        self.assertEqual((self.main/'library.dll').read_bytes(), b'new bytes')
        self.assertEqual((self.main/'added.bin').read_bytes(), b'new bytes')

    def test_drift_rejects_before_any_restore(self):
        replay.write(self.restored/'added.bin', b'external edit')
        with self.assertRaisesRegex(ValueError, 'Rollback target drift'):
            replay.rollback(self.work)
        self.assertEqual((self.restored/'library.dll').read_bytes(), b'new bytes')

    def test_path_escape_is_rejected(self):
        (self.work/'rollback-state.json').write_bytes(blob({'../outside.dll': self.state['library.dll']}))
        with self.assertRaisesRegex(ValueError, 'Invalid package path'):
            replay.rollback(self.work)

    def test_effective_base_combines_zip_and_unchanged_original_inputs(self):
        source = self.work/'source'
        source.mkdir()
        (source/'retained.dat').write_bytes(b'baseline')
        archive = self.work/'overlay.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('replaced.dat', b'replacement')
        overlay = {'source_files': {'retained.dat': sha(b'baseline'), 'replaced.dat': sha(b'old')}}
        report = replay.check_effective_base(archive, source, overlay)
        self.assertEqual(report, dict(original_files=2, supplied_by_zip=1,
                                      checked_in_place=1, uncovered_differences=0))
        (source/'retained.dat').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'Uncovered original input differences'):
            replay.check_effective_base(archive, source, overlay)


if __name__ == '__main__':
    unittest.main()
