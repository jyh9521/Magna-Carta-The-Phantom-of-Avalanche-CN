import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_shared_runtime as tool


class SharedRuntimeTests(unittest.TestCase):
    def inputs(self,root):
        game=root/'game'; prior=game/'.advanced-runtime'; prior.mkdir(parents=True)
        locale=game/'.locale-runtime'; (locale/'session-owned').mkdir(parents=True)
        (locale/'PrepareProfile.ps1').write_bytes(b'owned profile preparer')
        (locale/'session-owned/profile.bin').write_bytes(bytes(52))
        (game/'engine.dll').write_bytes(b'owned engine'); (game/'title.bgr').write_bytes(b'owned title')
        profiles={}
        for name in ['baseline','render4k','wide4k','fps60','combined']:
            (prior/(name+'.ini')).write_bytes(name.encode()); profiles[name]=tool.sha(prior/(name+'.ini'))
        (prior/'manifest.json').write_text(json.dumps(dict(schema=1,workspace=str(game),source_hashes={'engine.dll':tool.sha(game/'engine.dll')},config='config.ini',profiles=profiles)))
        (prior/'title-background.json').write_text(json.dumps(dict(active=True,tiles={'title.bgr':dict(after=tool.sha(game/'title.bgr'))})))
        (prior/'enhancements.json').write_text(json.dumps(tool.settings()))
        (prior/'configuration-ui.json').write_bytes(b'owned locale UI')
        native=root/'native.dll'; native.write_bytes(b'owned module')
        modules={name:native for name in ['display','modern','texture','camera','maps','launcher']}
        atlas=root/'atlas'; atlas.mkdir()
        (atlas/'manifest.json').write_text(json.dumps(dict(schema=1,navigation_verified=False,accepted=[])))
        (atlas/'label.txt').write_bytes(b'owned label')
        return game,modules,atlas

    def test_never_copies_game_and_all_recipes_share_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game,modules,atlas=self.inputs(root); out=root/'runtime'
            before=tool.sha(game/'engine.dll'); m=tool.prepare(game,modules,atlas,out)
            self.assertEqual(before,tool.sha(game/'engine.dll'))
            self.assertFalse((out/'data').exists())
            self.assertEqual(m['data_root'],'data')
            self.assertEqual(len(m['recipes']),11)
            self.assertTrue(m['recipes']['camera']['camera'])
            self.assertTrue(m['recipes']['maps']['maps'])
            self.assertTrue((out/'Configure.cmd').is_file())
            self.assertRaises(ValueError,tool.prepare,game,modules,atlas,out)

    def test_source_hash_drift_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game,modules,atlas=self.inputs(root)
            (game/'engine.dll').write_bytes(b'drift')
            self.assertRaises(ValueError,tool.prepare,game,modules,atlas,root/'runtime')
            self.assertFalse((root/'runtime').exists())
