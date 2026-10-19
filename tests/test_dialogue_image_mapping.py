from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'build/native/Release'

class DialogueImageMappingTests(unittest.TestCase):
    @unittest.skipUnless((BIN/'dialogue_reveal_fixture.exe').is_file(), 'Requires owned Win32 fixture')
    def test_split_regions_and_unreadable_targets(self):
        p=subprocess.run([str(BIN/'dialogue_reveal_fixture.exe')],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('DIALOGUE_MEMORY_REGRESSION PASS',p.stdout)

    @unittest.skipUnless((BIN/'dialogue_image_fixture.exe').is_file() and (ROOT/'runtime/data/MCAlpha.dll').is_file(), 'Requires supported user-supplied image and owned Win32 fixture')
    def test_actual_loader_mapping_without_entrypoint(self):
        p=subprocess.run([str(BIN/'dialogue_image_fixture.exe'),str(ROOT/'runtime/data/MCAlpha.dll')],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('DIALOGUE_IMAGE_FIXTURE PASS mapped_image=true production_guards=true rollback=exact entrypoint_executed=false game_started=false',p.stdout)
