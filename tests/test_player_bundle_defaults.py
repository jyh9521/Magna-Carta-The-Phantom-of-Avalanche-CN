import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_player_test_bundle as tool


class PlayerBundleDefaultsTests(unittest.TestCase):
    def test_package_defaults_do_not_export_local_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, runtime, output = (root/n for n in ('source', 'runtime', 'package'))
            source.mkdir(); runtime.mkdir()
            for name in ('MagnaCarta.exe', 'MCAlpha.dll'):
                (source/name).write_bytes(b'owned original fixture')
            (runtime/'data').mkdir()
            for name in ('MagnaCarta.exe', 'MCAlpha.dll', 'ddraw.dll', 'DDrawCompat-MagnaCarta.ini'):
                (runtime/'data'/name).write_bytes(b'owned runtime fixture')
            (runtime/'config').mkdir()
            local = b'{"schema":2,"resolution":"auto","window_mode":"windowed","frame_rate":60,"native_gamepad":true,"free_view":true,"window_resolution":"1920x1080"}'
            (runtime/'config/enhancements.json').write_bytes(local)
            (runtime/'Configure.cmd').write_bytes(b'owned entry')
            (runtime/'runtime.json').write_text(json.dumps(dict(data={}, files={})))
            real_sha = tool.sha
            supported = {'MagnaCarta.exe':'be2ae107373835defc6ec33643eaf435dcc5c882ea0b6e3c47032cd013690651',
                         'MCAlpha.dll':'79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f'}
            def fixture_sha(path):
                return supported[path.name] if path.parent == source else real_sha(path)
            with patch.object(tool, 'sha', side_effect=fixture_sha), patch.object(tool, 'validate_engine_fixes', return_value={}), patch.object(tool.urllib.request, 'urlopen', return_value=Mock(read=lambda:b'owned license fixture')), contextlib.redirect_stdout(io.StringIO()):
                manifest = tool.build(source, runtime, output)
            packaged = output/'payload/config/enhancements.json'
            self.assertEqual(json.loads(packaged.read_text()), dict(schema=2, resolution='1080p', window_mode='borderless', frame_rate=30, native_gamepad=False, free_view=False, window_resolution='1280x720'))
            self.assertEqual((runtime/'config/enhancements.json').read_bytes(), local)
            self.assertEqual(manifest['payload']['config/enhancements.json'], real_sha(packaged))
