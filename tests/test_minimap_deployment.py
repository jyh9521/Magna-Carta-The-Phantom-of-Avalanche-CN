"""Owned file fixtures for map installation; no game process or original binary."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import deploy_minimap as tool
import map_point_assets as point_tool


class MinimapDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = self.root/'runtime'
        self.atlas = self.root/'atlas'
        self.record = self.root/'record'
        for p in (self.runtime/'data/MAP', self.runtime/'maps', self.runtime/'modules', self.atlas):
            p.mkdir(parents=True)
        self.native = self.root/'candidate.dll'
        data = bytearray(512)
        data[:2] = b'MZ'
        struct.pack_into('<I', data, 0x3c, 128)
        data[128:132] = b'PE\0\0'
        struct.pack_into('<H', data, 132, 0x14c)
        struct.pack_into('<HH', data, 150, 0x2002, 0x10b)
        marker = 'MAP_F9_CYCLE_V1'.encode('utf-16le')
        data[256:256+len(marker)] = marker
        self.native.write_bytes(data)
        files = {'Start.ps1': b'original startup', 'maps/0009.png': b'old terrain',
                 'maps/0009.map': b'old metadata', 'maps/manifest.json': b'old atlas',
                 'maps/label.txt': b'old label', 'modules/scaled-font.dll': b'accepted fixes'}
        for name, blob in files.items():
            (self.runtime/name).write_bytes(blob)
        (self.runtime/'data/MAP/0009.wrd').write_bytes(b'owned terrain input')
        (self.runtime/'data/MC00.SAV').write_bytes(b'owned save')
        (self.runtime/'enhancements.json').write_bytes(b'owned preferences')
        state = dict(schema=1, data_root='data', files={n: tool.sha(b) for n, b in files.items()},
                     data={'MAP/0009.wrd': tool.sha(b'owned terrain input')},
                     recipes={'configured': {'module': 'configured'}})
        (self.runtime/'runtime.json').write_text(json.dumps(state))
        (self.atlas/'0009.png').write_bytes(b'new line terrain')
        (self.atlas/'0009.map').write_bytes(b'new metadata')
        (self.atlas/'label.txt').write_bytes('Map'.encode('utf-16le'))
        atlas = dict(schema=1, projection='first_instance_frame_column_major_XY', navigation_verified=False,
                     accepted=[dict(id=9, source_sha256=tool.sha(b'owned terrain input'),
                                    png_sha256=tool.digest(self.atlas/'0009.png'),
                                    metadata_sha256=tool.digest(self.atlas/'0009.map'))])
        (self.atlas/'manifest.json').write_text(json.dumps(atlas))
        self.before = self.snapshot()
        idle = patch.object(tool, 'idle')
        idle.start()
        self.addCleanup(idle.stop)

    def snapshot(self):
        return {p.relative_to(self.runtime).as_posix(): p.read_bytes()
                for p in self.runtime.rglob('*') if p.is_file()}

    def apply(self):
        return tool.apply(self.runtime, self.native, self.atlas, self.record)

    def test_install_and_exact_rollback_preserve_game_settings_and_previous_fixes(self):
        changes = self.apply()
        state = json.loads((self.runtime/'runtime.json').read_text())
        self.assertEqual(state['map_overlay'], dict(schema=1, enabled=True, module='minimap'))
        self.assertEqual((self.runtime/'modules/minimap.dll').read_bytes(), self.native.read_bytes())
        self.assertEqual((self.runtime/'maps/0009.png').read_bytes(), b'new line terrain')
        for name, data in self.before.items():
            if name not in changes:
                self.assertEqual((self.runtime/name).read_bytes(), data)
        tool.rollback(self.runtime, self.record)
        self.assertEqual(self.snapshot(), self.before)

    def test_frame_map_requires_verified_compass_sources(self):
        self.native.write_bytes(self.native.read_bytes() + 'MAP_FRAME_PRESENT_V2'.encode('utf-16le'))
        with self.assertRaisesRegex(ValueError, 'Compass layout source drift'):
            self.apply()
        self.assertEqual(self.snapshot(), self.before)
        self.assertFalse(self.record.exists())

    def test_frame_map_records_compass_inputs_and_restores_manifest(self):
        self.native.write_bytes(self.native.read_bytes() + 'MAP_FRAME_PRESENT_V2'.encode('utf-16le'))
        compass = self.runtime/'data/FrameData/0136.fdi'
        compass.parent.mkdir()
        compass.write_bytes(b'owned compass position source')
        before = self.snapshot()
        with patch.object(tool, 'COMPASS_SOURCES', {'FrameData/0136.fdi': tool.digest(compass)}):
            self.apply()
        state = json.loads((self.runtime/'runtime.json').read_text())
        self.assertEqual(state['data']['FrameData/0136.fdi'], tool.digest(compass))
        tool.rollback(self.runtime, self.record)
        self.assertEqual(self.snapshot(), before)

    def test_record_reuse_rejected_before_changes(self):
        self.record.mkdir()
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.snapshot(), self.before)

    def test_record_cannot_be_a_payload_target(self):
        self.record = self.runtime/'modules/minimap.dll'
        with self.assertRaisesRegex(ValueError, 'independent deployment record'):
            self.apply()
        self.assertEqual(self.snapshot(), self.before)

    def test_existing_temp_is_not_deleted_or_overwritten(self):
        path = self.root/'atomic-data'
        path.write_bytes(b'original')
        temporary = self.root/'atomic-data.minimap-tmp'
        temporary.write_bytes(b'external temporary')
        with self.assertRaises(FileExistsError):
            tool.atomic(path, b'candidate')
        self.assertEqual(path.read_bytes(), b'original')
        self.assertEqual(temporary.read_bytes(), b'external temporary')

    def test_unknown_module_rejected(self):
        self.native.write_bytes(b'old module')
        with self.assertRaisesRegex(ValueError, 'Win32 DLL'):
            self.apply()
        self.assertFalse(self.record.exists())
        self.assertEqual(self.snapshot(), self.before)

    def test_existing_runtime_drift_rejected(self):
        (self.runtime/'Start.ps1').write_bytes(b'external edit')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Runtime drift'):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.record.exists())

    def test_map_input_source_binding(self):
        p = self.atlas/'manifest.json'
        data = json.loads(p.read_text())
        data['accepted'][0]['source_sha256'] = '0'*64
        p.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Map source drift'):
            self.apply()
        self.assertFalse(self.record.exists())
        self.assertEqual(self.snapshot(), self.before)

    def test_atlas_drift_rejected(self):
        (self.atlas/'0009.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Map asset drift'):
            self.apply()
        self.assertFalse(self.record.exists())

    def test_apply_failure_compensates_only_completed_writes(self):
        original = tool.atomic
        calls = 0

        def fail_once(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('injected write failure')
            original(path, data)

        with patch.object(tool, 'atomic', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.apply()
        self.assertEqual(self.snapshot(), self.before)

    def test_rollback_refuses_external_edits_before_any_restore(self):
        self.apply()
        (self.runtime/'maps/0009.png').write_bytes(b'external change')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Rollback target drift'):
            tool.rollback(self.runtime, self.record)
        self.assertEqual(self.snapshot(), before)

    def test_rollback_refuses_changed_original_before_any_restore(self):
        self.apply()
        (self.record/'original/Start.ps1').write_bytes(b'bad backup')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Rollback source drift'):
            tool.rollback(self.runtime, self.record)
        self.assertEqual(self.snapshot(), before)

    def test_manifest_escape_rejected(self):
        p = self.runtime/'runtime.json'
        state = json.loads(p.read_text())
        state['files']['../escape'] = '0'*64
        p.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'relative payload path'):
            self.apply()
        self.assertFalse(self.record.exists())

    def test_corrupt_rollback_path_rejected(self):
        self.apply()
        (self.record/'changes.json').write_text(json.dumps({'data/MC00.SAV': {'after': '0'*64, 'before': None}}))
        with self.assertRaisesRegex(ValueError, 'Unexpected rollback target'):
            tool.rollback(self.runtime, self.record)
        self.assertEqual((self.runtime/'data/MC00.SAV').read_bytes(), b'owned save')

    def test_unregistered_existing_module_preserved(self):
        (self.runtime/'modules/minimap.dll').write_bytes(b'unregistered existing candidate')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Unregistered existing'):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.record.exists())

    def test_rollback_write_failure_compensates(self):
        self.apply()
        before = self.snapshot()
        original = tool.atomic
        calls = 0

        def fail_once(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('injected rollback failure')
            original(path, data)

        with patch.object(tool, 'atomic', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'injected rollback'):
                tool.rollback(self.runtime, self.record)
        self.assertEqual(self.snapshot(), before)
        tool.rollback(self.runtime, self.record)
        self.assertEqual(self.snapshot(), self.before)

    def test_flat_test_layout_overlay_manifest_roundtrip(self):
        (self.runtime/'MAP').mkdir()
        (self.runtime/'MAP/0009.wrd').write_bytes(b'owned terrain input')
        p = self.runtime/'runtime.json'
        state = json.loads(p.read_text())
        state['data_root'] = '.'
        p.write_text(json.dumps(state))
        overlay = self.runtime/'Overlay-Manifest.json'
        overlay.write_text(json.dumps(dict(files={})))
        before = self.snapshot()
        self.apply()
        updated = json.loads(overlay.read_text())
        self.assertEqual(updated['files']['runtime.json'], tool.digest(p))
        tool.rollback(self.runtime, self.record)
        self.assertEqual(self.snapshot(), before)

    def points(self):
        engine = b'owned point loader identity'
        source = b'owned Field script'
        (self.runtime/'data/MCAlpha.dll').write_bytes(engine)
        (self.runtime/'data/Field').mkdir()
        (self.runtime/'data/Field/0751.fld').write_bytes(source)
        path = self.atlas/'points'
        path.mkdir()
        point = dict(event_index=0, region_id=1, target_field=757, target_map=17,
                     trigger_actor=1, flags=0, x=10., y=20., z=30.)
        data = point_tool.HEADER.pack(b'MCP1', 751, 13, 1)+point_tool.ROW.pack(
            *(point[k] for k in point_tool.FIELDS))
        (path/'0751.poi').write_bytes(data)
        manifest = dict(schema=1, format='MCP1', header_bytes=16, row_bytes=36,
                        source_engine_sha256=tool.sha(engine), current_passability_evaluated=False,
                        marker_count=1, accepted=[dict(field_id=751, map_id=13, file='0751.fld',
                                                      source_sha256=tool.sha(source), poi_sha256=tool.sha(data),
                                                      points=[point])])
        (path/'manifest.json').write_text(json.dumps(manifest))
        patcher = patch.object(point_tool, 'ENGINE_SHA256S', {tool.sha(engine)})
        patcher.start()
        self.addCleanup(patcher.stop)
        return path, manifest

    def test_points_deploy_nested_paths_and_exact_rollback(self):
        self.points()
        before = self.snapshot()
        self.apply()
        self.assertEqual((self.runtime/'maps/points/0751.poi').read_bytes(),
                         (self.atlas/'points/0751.poi').read_bytes())
        state = json.loads((self.runtime/'runtime.json').read_text())
        self.assertEqual(state['files']['maps/points/0751.poi'],
                         tool.digest(self.runtime/'maps/points/0751.poi'))
        tool.rollback(self.runtime, self.record)
        self.assertEqual(self.snapshot(), before)

    def test_points_source_drift_rejects_before_writes(self):
        self.points()
        (self.runtime/'data/Field/0751.fld').write_bytes(b'new Field')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Field source drift'):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.record.exists())

    def test_points_binary_drift_rejects(self):
        path, _ = self.points()
        (path/'0751.poi').write_bytes(b'truncated')
        with self.assertRaisesRegex(ValueError, 'point asset drift'):
            self.apply()
        self.assertFalse(self.record.exists())

    def test_points_manifest_validation(self):
        path, valid = self.points()
        for change in ('actor', 'nan', 'duplicate', 'count', 'path', 'version'):
            data = json.loads(json.dumps(valid))
            if change == 'actor':data['accepted'][0]['points'][0]['trigger_actor'] = -1
            elif change == 'nan':data['accepted'][0]['points'][0]['x'] = float('nan')
            elif change == 'duplicate':data['accepted'] *= 2
            elif change == 'count':data['marker_count'] = 2
            elif change == 'path':data['accepted'][0]['file'] = '../escape.fld'
            else:data['row_bytes'] = 32
            (path/'manifest.json').write_text(json.dumps(data))
            with self.subTest(change=change), self.assertRaises(ValueError):
                point_tool.point_assets(path)

    def test_unlisted_points_rejected(self):
        path, _ = self.points()
        (path/'other.poi').write_bytes(b'undeclared')
        with self.assertRaisesRegex(ValueError, 'Unlisted'):
            point_tool.point_assets(path)

    def test_new_points_set_cannot_leave_stale_field_files(self):
        self.points()
        old = self.runtime/'maps/points/0999.poi'
        old.parent.mkdir()
        old.write_bytes(b'old accepted Field')
        p = self.runtime/'runtime.json'
        state = json.loads(p.read_text())
        state['files']['maps/points/0999.poi'] = tool.digest(old)
        p.write_text(json.dumps(state))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Stale map points'):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.record.exists())


if __name__ == '__main__':
    unittest.main()
