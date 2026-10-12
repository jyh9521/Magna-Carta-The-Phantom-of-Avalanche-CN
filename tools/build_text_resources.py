"""Rebuild source-locked native FPB targets into a new, non-deployed candidate."""
import argparse
import hashlib
import json
from pathlib import Path

from build_text_probe import relative
from native_text_codec import encode, decode, validate as validate_mapping
from resource_fpb import parse, rebuild
from resource_font import parse as parse_font
from translation_data import validate as validate_targets, load_targets


def digest(data):return hashlib.sha256(data).hexdigest()


def rebuild_fpb(original, resource, catalog, targets, mapping):
    source=parse(original)
    if rebuild(source)!=original:raise ValueError('original FPB roundtrip mismatch')
    rows=[row for row in catalog if row['resource']==resource]
    if len(rows)!=len(source):raise ValueError('catalog count does not match FPB')
    by_ordinal={row['ordinal']:row for row in rows}
    if len(by_ordinal)!=len(rows):raise ValueError('duplicate FPB catalog ordinal')
    chosen=[row for row in targets if row['id'] in {r['id'] for r in rows}]
    check=validate_targets(rows,chosen,mapping=mapping,require_complete=True)
    if check['errors']:raise ValueError('FPB targets incomplete or invalid: '+json.dumps(check['errors']))
    by_id={row['id']:row for row in chosen};result=[]
    for ordinal,(tag,raw) in enumerate(source):
        row=by_ordinal.get(ordinal)
        if (row is None or row['identifier']!=tag or row['source_hex']!=raw.hex()
                or row['id']!=f'{resource}:text:{ordinal}:{tag}'):
            raise ValueError('FPB catalog identifier or source bytes mismatch')
        target=by_id[row['id']]
        encoded=raw if target['state']=='preserved' else encode(target['target'],mapping)
        if target['state']!='preserved' and decode(encoded,mapping)!=target['target']:
            raise ValueError('target text encoding roundtrip mismatch')
        result.append((tag,encoded))
    modified=rebuild(result)
    if parse(modified)!=result:raise ValueError('modified FPB structure mismatch')
    if [tag for tag,_ in parse(modified)]!=[tag for tag,_ in source]:
        raise ValueError('resource IDs changed')
    return modified


def checked_fonts(source, package, state):
    validate_mapping(state['mapping']);outputs={}
    if len(state['native_original_sha256'])!=2 or len(state['native_modified_sha256'])!=2:
        raise ValueError('incomplete native font digests')
    indices={item['index'] for item in state['mapping'].values()}
    for font_set in (0,1):
        name=f'Chi{font_set}.dat';raw=(source/'Font'/name).read_bytes()
        modified=(package/name).read_bytes()
        if (digest(raw)!=state['native_original_sha256'][font_set]
                or digest(modified)!=state['native_modified_sha256'][font_set]):
            raise ValueError('native font package or source digest mismatch')
        font=parse_font(raw);expected=font;seen=set()
        for delta in state['deltas']:
            if delta['font_set']!=font_set:continue
            index=delta['index']
            if index in seen or index not in indices or digest(font.glyph(index))!=delta['original_glyph_sha256']:
                raise ValueError('unexpected or duplicate native glyph delta')
            seen.add(index);expected=expected.replace_glyph(index,bytes.fromhex(delta['bitmap_hex']))
            characters=[c for c,item in state['mapping'].items() if item['index']==index]
            if not any(bytes.fromhex(delta['bitmap_hex'])) and any(not c.isspace() for c in characters):
                raise ValueError('mapped glyph bitmap is empty')
        if seen!=indices or expected.to_bytes()!=modified:
            raise ValueError('font modifies bytes outside declared mapped glyphs')
        outputs[name]=modified
    return outputs


def build(source, catalog_path, coverage_path, target_paths, font_package, output, terms_path=None, allow_partial=False):
    source=Path(source).resolve(strict=True);output=Path(output).resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('output must be a new separate directory')
    inputs=[Path(catalog_path),Path(coverage_path),*map(Path,target_paths)]
    if terms_path:inputs.append(Path(terms_path))
    font_package=Path(font_package).resolve(strict=True)
    if output.is_relative_to(font_package):raise ValueError('output must be outside font package')
    inputs.extend([font_package/'overlay.json',font_package/'Chi0.dat',font_package/'Chi1.dat'])
    snapshots={path.resolve(strict=True):path.read_bytes() for path in inputs}
    catalog=json.loads(Path(catalog_path).read_text('utf8'));coverage=json.loads(Path(coverage_path).read_text('utf8'))
    targets=load_targets(target_paths);font_state=json.loads((font_package/'overlay.json').read_text('utf8'))
    terms=json.loads(Path(terms_path).read_text('utf8')) if terms_path else None
    report=validate_targets(catalog,targets,terms,font_state['mapping'],not allow_partial)
    if report['errors']:raise ValueError('translation validation failed: '+json.dumps(report['errors']))
    source_rows={row['id']:row for row in catalog};resources={source_rows[row['id']]['resource'] for row in targets}
    locked={row['path']:row for row in coverage}
    if len(locked)!=len(coverage):raise ValueError('duplicate coverage path')
    original_files={};outputs={};resource_report=[]
    for resource in sorted(resources):
        rel=relative(resource)
        if rel in outputs:raise ValueError('duplicate normalized resource output path')
        if rel.suffix.lower()!='.fpb':raise ValueError('resource format not supported by this builder')
        path=source/rel
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):
            raise ValueError('linked resource is not supported')
        original=path.read_bytes();entry=locked.get(resource)
        if entry is None or digest(original)!=entry['sha256'] or len(original)!=entry['size']:
            raise ValueError('resource coverage digest mismatch')
        changed=rebuild_fpb(original,resource,catalog,targets,font_state['mapping'])
        original_files[path]=original;outputs[rel]=changed
        resource_report.append(dict(resource=resource,original_sha256=digest(original),
                                    modified_sha256=digest(changed),original_size=len(original),modified_size=len(changed),
                                    identifiers_preserved=True,encoded_text_roundtrip=True))
    if not resources:raise ValueError('no resource targets supplied')
    original_files.update({source/'Font'/f'Chi{i}.dat':(source/'Font'/f'Chi{i}.dat').read_bytes() for i in (0,1)})
    font_outputs=checked_fonts(source,font_package,font_state)
    if any(path.read_bytes()!=data for path,data in {**snapshots,**original_files}.items()):
        raise ValueError('build input changed before publication')
    # Candidate completeness means only the supplied catalog, never image/hardcoded coverage.
    manifest=dict(schema=1,kind='native_text_resource_candidate',catalog_validation=report,
                  catalog_sha256=digest(snapshots[Path(catalog_path).resolve()]),
                  coverage_sha256=digest(snapshots[Path(coverage_path).resolve()]),
                  font_overlay_sha256=digest(snapshots[(font_package/'overlay.json').resolve()]),
                  target_inputs=[dict(sha256=digest(snapshots[Path(p).resolve()])) for p in target_paths],
                  resources=resource_report,fonts={name:digest(data) for name,data in font_outputs.items()},
                  requires_native_text_step=True,all_game_text_complete=False,
                  source_unchanged=True,deployed=False,game_started=False,in_game_verified=False)
    output.mkdir(parents=True)
    for rel,data in outputs.items():
        path=output/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    for name,data in font_outputs.items():
        path=output/'Font'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (output/'build.json').write_text(json.dumps(manifest,ensure_ascii=True,indent=2)+'\n',encoding='utf8',newline='\n')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--catalog',type=Path,required=True);p.add_argument('--coverage',type=Path,required=True)
    p.add_argument('--translations',type=Path,nargs='+',required=True);p.add_argument('--font-package',type=Path,required=True)
    p.add_argument('--terms',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-partial',action='store_true');a=p.parse_args()
    result=build(a.source,a.catalog,a.coverage,a.translations,a.font_package,a.output,a.terms,a.allow_partial)
    print(f'TEXT_RESOURCE_BUILD PASS resources={len(result["resources"])} translated={result["catalog_validation"]["translated_fields"]} '
          f'catalog_complete={str(result["catalog_validation"]["complete"]).lower()} all_game_text_complete=false deployed=false game_started=false')
