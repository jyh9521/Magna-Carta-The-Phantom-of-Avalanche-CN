import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
spec=importlib.util.spec_from_file_location('observer',Path(__file__).resolve().parents[1]/'tools/observe_window.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class GeometryTests(unittest.TestCase):
    def test_borderless_cover(self):
        row=m.geometry(m.POPUP|m.VISIBLE,[-1920,0,0,1080],[0,0,1920,1080],[-1920,0,0,1080])
        self.assertTrue(row['borderless_style']);self.assertTrue(row['covers_monitor'])
        self.assertEqual(row['client_size'],[1920,1080])

    def test_caption_rejected(self):
        row=m.geometry(m.POPUP|m.CAPTION,[0,0,640,480],[0,0,624,441],[0,0,1920,1080])
        self.assertFalse(row['borderless_style']);self.assertFalse(row['covers_monitor'])

    def test_borderless_does_not_imply_fullscreen(self):
        row=m.geometry(m.POPUP,[10,10,650,490],[0,0,640,480],[0,0,1920,1080])
        self.assertTrue(row['borderless_style']);self.assertFalse(row['covers_monitor']);self.assertFalse(row['visible'])

    def test_exit_during_path_query_is_normal_end(self):
        self.assertEqual(m.target_status(False,False,False),'target_ended')

    def test_live_identity_failure_is_not_normal_end(self):
        self.assertEqual(m.target_status(True,False,False),'identity_query_failed')
        self.assertEqual(m.target_status(True,True,False),'identity_changed')
        self.assertEqual(m.target_status(True,True,True),'active')

    def test_exit_race_preserves_collected_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session=root/'build/runtime-launch/fixture';session.mkdir(parents=True)
            exe=root/'build/fixture/MagnaCarta.exe';exe.parent.mkdir();exe.write_bytes(b'owned fixture')
            (session/'stdout.log').write_text('ISOLATED_PROCESS_STARTED pid=123')
            (session/'stderr.log').write_text('')
            (session/'profile.log').write_text('IAT_READY module='+str(exe))
            codes=iter([259,259,259,0]);queries=iter([True,False])
            def exit_code(handle,pointer):pointer._obj.value=next(codes);return True
            def path_query(handle,flags,buffer,size):
                success=next(queries)
                if success:buffer.value=str(exe)
                return success
            kernel=SimpleNamespace(OpenProcess=Mock(return_value=42),GetExitCodeProcess=exit_code,
                QueryFullProcessImageNameW=path_query,CloseHandle=Mock())
            user=SimpleNamespace(EnumWindows=Mock(return_value=1))
            digest=Mock();digest.hexdigest.return_value='be2ae107373835defc6ec33643eaf435dcc5c882ea0b6e3c47032cd013690651'
            with patch.object(m,'api',return_value=(user,kernel)),patch.object(m.hashlib,'sha256',return_value=digest),patch.object(m.time,'sleep'):
                m.observe(session,root,2)
            report=json.loads((session/'window-observation.json').read_text())
            self.assertEqual(report['status'],'target_ended');self.assertEqual(len(report['samples']),1)
            kernel.OpenProcess.assert_called_once();kernel.CloseHandle.assert_called_once_with(42)

if __name__=='__main__':unittest.main()
