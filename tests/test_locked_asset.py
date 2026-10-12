import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fetch_locked_asset as m


class Response(io.BytesIO):
    def geturl(self): return self.url


class LockedAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = self.root/'input.json'; self.output = self.root/'out'/'font.ttf'
        self.data = b'controlled build input'
        self.entry = dict(download_url='https://example.org/locked.ttf', size=len(self.data),
                          sha256=hashlib.sha256(self.data).hexdigest())

    def fetch(self, data=None, final_url=None):
        self.manifest.write_text(json.dumps(self.entry), encoding='utf8')
        response = Response(self.data if data is None else data)
        response.url = final_url or self.entry['download_url']
        with patch.object(m.urllib.request, 'urlopen', return_value=response):
            return m.fetch(self.manifest, self.output)

    def test_digest_locked_download(self):
        self.assertEqual(self.fetch(), self.entry)
        self.assertEqual(self.output.read_bytes(), self.data)

    def test_wrong_hash_leaves_no_output(self):
        with self.assertRaisesRegex(ValueError, 'size or hash'): self.fetch(b'X'*len(self.data))
        self.assertFalse(self.output.exists())

    def test_oversize_read_leaves_no_output(self):
        with self.assertRaisesRegex(ValueError, 'size or hash'): self.fetch(self.data+b'excess')
        self.assertFalse(self.output.exists())

    def test_http_refused(self):
        self.entry['download_url'] = 'http://example.org/input'
        with self.assertRaisesRegex(ValueError, 'invalid HTTPS'): self.fetch()

    def test_downgrade_redirect_refused(self):
        with self.assertRaisesRegex(ValueError, 'outside HTTPS'): self.fetch(final_url='http://example.org/input')
        self.assertFalse(self.output.exists())

    def test_existing_output_preserved(self):
        self.output.parent.mkdir(); self.output.write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError, 'already exists'): self.fetch()
        self.assertEqual(self.output.read_bytes(), b'preserve')

    def test_invalid_limit_or_digest_refused(self):
        for value in [True, -1, 64*1024*1024+1]:
            self.entry['size'] = value
            with self.assertRaisesRegex(ValueError, 'invalid HTTPS'): self.fetch()
        self.entry['size'] = len(self.data); self.entry['sha256'] = 'G'*64
        with self.assertRaisesRegex(ValueError, 'invalid HTTPS'): self.fetch()


if __name__ == '__main__': unittest.main()
