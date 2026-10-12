"""Fetch one explicitly declared HTTPS build input after size and SHA-256 checks."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.parse


def fetch(manifest, output):
    output = Path(output)
    if output.exists():
        raise ValueError('output already exists')
    entry = json.loads(Path(manifest).read_text(encoding='utf8'))
    url = urllib.parse.urlsplit(entry['download_url'])
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or type(entry['size']) is not int or not 0 < entry['size'] <= 64*1024*1024
            or len(entry['sha256']) != 64
            or any(c not in '0123456789abcdef' for c in entry['sha256'])):
        raise ValueError('invalid HTTPS build input')
    with urllib.request.urlopen(entry['download_url'], timeout=90) as response:
        if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
            raise ValueError('download redirected outside HTTPS')
        data = response.read(entry['size'] + 1)
    if len(data) != entry['size'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('downloaded input size or hash mismatch')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream: stream.write(data)
    return entry


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    entry = fetch(a.manifest,a.output)
    print(f'LOCKED_ASSET PASS bytes={entry["size"]} sha256={entry["sha256"]} game_started=false')
