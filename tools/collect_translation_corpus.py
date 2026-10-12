"""Collect validated target rows into a reproducible font input directory."""
import argparse
import hashlib
import json
from pathlib import Path

from translation_data import load_targets, validate


def collect(catalog, translations, output, terms=None, allow_partial=False, links=None):
    paths=[Path(catalog),*map(Path,translations)]
    if terms is not None:paths.append(Path(terms))
    if links is not None:paths.append(Path(links))
    snapshots={p.resolve(strict=True):p.read_bytes() for p in paths}
    output=Path(output).resolve()
    if output.exists() or any(p.is_relative_to(output) for p in snapshots):
        raise ValueError('corpus output must be a new directory separate from inputs')
    rows=load_targets(translations)
    report=validate(json.loads(snapshots[Path(catalog).resolve()]),rows,
                    json.loads(snapshots[Path(terms).resolve()]) if terms else None,
                    require_complete=not allow_partial,
                    links=json.loads(snapshots[Path(links).resolve()]) if links else None)
    if report['errors']:raise ValueError('translation validation failed: '+json.dumps(report['errors']))
    targets=sorted((r for r in rows if r['state'] in ('translated','reviewed')),key=lambda r:r['id'])
    if not targets:raise ValueError('no translated font targets supplied')
    data=(json.dumps(targets,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if any(p.read_bytes()!=raw for p,raw in snapshots.items()):
        raise ValueError('corpus input changed before publication')
    manifest=dict(schema=1,kind='translation_font_corpus',target_rows=len(targets),
                  preserved_fields_excluded=report['preserved_fields'],
                  corpus_sha256=hashlib.sha256(data).hexdigest(),
                  inputs=[dict(sha256=hashlib.sha256(snapshots[p.resolve()]).hexdigest()) for p in paths],
                  catalog_complete=report['complete'],all_game_text_complete=False,
                  semantic_approval_not_inferred=True,game_started=False)
    output.mkdir(parents=True)
    (output/'corpus.json').write_bytes(data)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8',newline='\n')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--translations',type=Path,nargs='+',required=True)
    p.add_argument('--terms',type=Path);p.add_argument('--links',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-partial',action='store_true');a=p.parse_args()
    result=collect(a.catalog,a.translations,a.output,a.terms,a.allow_partial,a.links)
    print(f'TRANSLATION_CORPUS PASS rows={result["target_rows"]} '
          f'catalog_complete={str(result["catalog_complete"]).lower()} game_started=false')
