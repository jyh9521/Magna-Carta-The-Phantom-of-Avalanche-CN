import importlib.util
from pathlib import Path
import unittest
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

if __name__=='__main__':unittest.main()
