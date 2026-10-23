"""Owned no-window shared-layout exception capture, never a game process."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_shared_capture import verify


class SharedExceptionCaptureTests(unittest.TestCase):
    def setUp(self):
        self.binary=ROOT/'build/native/Release'
        for name in ('capture_helper.exe','workspace_profile.dll','Core.dll','capture_dialog_sink.dll'):
            if not (self.binary/name).exists():
                self.skipTest('Build the owned capture fixture targets first')
        self.temp=tempfile.TemporaryDirectory(prefix='shared-capture-test-',dir=ROOT/'build')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)

    def test_production_hook_keeps_dialog_result_and_original_exception_heap(self):
        result=verify(self.binary,self.binary/'capture_helper.exe',self.base/'positive')
        self.assertTrue(result['full_memory_heap'])
        self.assertTrue(result['original_exception'])
        self.assertEqual(result['dump_count'],1)
        self.assertEqual(result['original_dialog_result'],42)
        self.assertFalse(result['game_started'])

    def test_shared_capture_rejects_unrelated_target_escape_and_existing_output(self):
        shared=self.base/'shared';modules=shared/'modules';cache=shared/'cache'
        modules.mkdir(parents=True);cache.mkdir()
        helper=modules/'capture_helper.exe';shutil.copyfile(self.binary/'capture_helper.exe',helper)
        (shared/'runtime.json').write_text('{"schema":1,"owned_capture_fixture":true}',encoding='utf8')
        # This process executes only the owned eight-second capture sample.
        process=subprocess.Popen([str(helper),'--fixture'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertIn('FIXTURE_HEAP',process.stdout.readline())
            self.assertIn('CAPTURE_FIXTURE_READY',process.stdout.readline())
            kept=cache/'kept.bin';kept.write_bytes(b'preserved')
            for pid,path in ((process.pid,self.base/'outside.dmp'),
                             (process.pid,kept),(os.getpid(),cache/'unrelated.dmp')):
                result=subprocess.run([str(helper),'--pid',str(pid),'--output',str(path)],
                                      capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,1,result.stdout)
                self.assertIn('FULL_CAPTURE_FAILED',result.stderr)
                self.assertEqual(kept.read_bytes(),b'preserved')
            self.assertFalse((cache/'unrelated.dmp').exists())
            self.assertFalse((self.base/'outside.dmp').exists())
            process.communicate(timeout=15)
            self.assertEqual(process.returncode,0)
        finally:
            if process.poll() is None:
                process.terminate()  # Only the Popen-owned fixture, never a game.
                process.communicate(timeout=5)
            process.stdout.close();process.stderr.close()


if __name__=='__main__':
    unittest.main()
