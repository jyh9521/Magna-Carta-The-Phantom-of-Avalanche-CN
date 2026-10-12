import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import graphics_candidate as module


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'
        self.game.mkdir()
        (self.game / 'fixture.bin').write_bytes(b'original')
        self.expected = {'fixture.bin': module.sha(b'original')}
        self.outputs = {'DDraw.dll': b'layer', 'D3DImm.dll': b'device', 'dgVoodoo.conf': module.CONFIG}
        self.hashes = {name: module.sha(data) for name, data in self.outputs.items()}
        patcher = patch.object(module, 'HASHES', self.hashes)
        patcher.start()
        self.addCleanup(patcher.stop)

    def apply(self):
        module.apply(self.game, self.root, self.outputs, self.expected)

    def test_roundtrip(self):
        self.apply()
        module.remove(self.game, self.root)
        self.assertEqual([p.name for p in self.game.iterdir()], ['fixture.bin'])

    def test_unknown_game(self):
        (self.game / 'fixture.bin').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.apply()

    def test_layer_stacking(self):
        (self.game / 'ddraw.dll').write_bytes(b'other')
        with self.assertRaises(ValueError): self.apply()

    def test_tampered_config_preserved(self):
        self.apply()
        (self.game / 'dgVoodoo.conf').write_bytes(b'changed')
        with self.assertRaises(ValueError): module.remove(self.game, self.root)
        self.assertTrue((self.game / 'DDraw.dll').exists())

    def test_manifest_path_rejected(self):
        self.apply()
        (self.game / module.STATE).write_text('{"outputs":{"../fixture.bin":"x"}}')
        with self.assertRaises(ValueError): module.remove(self.game, self.root)

    def test_output_mismatch(self):
        self.outputs['DDraw.dll'] = b'unknown'
        with self.assertRaises(ValueError): self.apply()
