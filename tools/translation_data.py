"""Source-bound target data validation, independent of a target locale."""
import argparse
import hashlib
import json
from pathlib import Path

from extract_text_catalog import TOKENS
from native_text_codec import encode
from term_glossary import conflicts as term_conflicts, validate as validate_terms


def source_digest(row):
    return hashlib.sha256(bytes.fromhex(row['source_hex'])).hexdigest()


def load_targets(paths):
    result=[]
    for path in paths:
        rows=json.loads(Path(path).read_text('utf8'))
        if not isinstance(rows,list):raise ValueError('translation input must be a row list')
        result.extend(rows)
    return result


def validate(catalog, targets, terms=None, mapping=None, require_complete=False):
    originals={row['id']:row for row in catalog}
    if len(originals)!=len(catalog):raise ValueError('duplicate source catalog ID')
    for row in catalog:
        raw=bytes.fromhex(row['source_hex'])
        if raw.decode(row.get('source_encoding','cp949'))!=row['source']:
            raise ValueError('source catalog text does not match original bytes')
    terms=[] if terms is None else validate_terms(terms)['terms']
    seen=set();errors=[];translated=0;preserved=0
    for target in targets:
        if not isinstance(target,dict) or not isinstance(target.get('id'),str):
            raise ValueError('translation record must have a string ID')
        key=target.get('id')
        if key not in originals or key in seen:
            raise ValueError('unknown or duplicate translation ID')
        seen.add(key);source=originals[key]
        if target.get('source_sha256')!=source_digest(source):
            errors.append(dict(id=key,kind='stale_source'));continue
        state=target.get('state')
        if state=='preserved':
            if target.get('target') is not None or not target.get('preservation_evidence'):
                errors.append(dict(id=key,kind='preservation_requires_null_target_and_evidence'))
            else:preserved+=1
            continue
        if state not in ('translated','reviewed') or not isinstance(target.get('target'),str):
            errors.append(dict(id=key,kind='translation_state_or_target_missing'));continue
        text=target['target']
        if '\0' in text or (source['source'] and not text):
            errors.append(dict(id=key,kind='unexpected_empty_or_terminator'));continue
        if TOKENS.findall(source['source'])!=TOKENS.findall(text):
            errors.append(dict(id=key,kind='protected_tokens_changed'));continue
        errors.extend(term_conflicts(source['source'],text,key,terms))
        if mapping is not None:
            try:encode(text,mapping)
            except ValueError as error:
                errors.append(dict(id=key,kind='encoding_or_glyph_error',detail=str(error)));continue
        translated+=1
    missing=[row['id'] for row in catalog if row['id'] not in seen]
    if require_complete and missing:
        errors.append(dict(kind='incomplete_catalog',missing_count=len(missing)))
    return dict(schema=1,source_fields=len(catalog),supplied_fields=len(targets),
                translated_fields=translated,preserved_fields=preserved,missing_fields=len(missing),
                missing_ids=missing,errors=errors,complete=not missing and not errors,
                game_started=False,in_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--translations',type=Path,nargs='+',required=True)
    p.add_argument('--terms',type=Path);p.add_argument('--font-overlay',type=Path)
    p.add_argument('--require-complete',action='store_true');p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists() or a.report.resolve() in {x.resolve() for x in [a.catalog,*a.translations]}:
        raise ValueError('validation report must be a new separate file')
    catalog=json.loads(a.catalog.read_text('utf8'));targets=load_targets(a.translations)
    terms=json.loads(a.terms.read_text('utf8')) if a.terms else None
    mapping=json.loads(a.font_overlay.read_text('utf8'))['mapping'] if a.font_overlay else None
    result=validate(catalog,targets,terms,mapping,a.require_complete)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=True,indent=2)+'\n',encoding='utf8',newline='\n')
    label='FAIL' if result['errors'] else 'PASS'
    print(f'TRANSLATION_DATA {label} supplied={len(targets)} translated={result["translated_fields"]} '
          f'missing={result["missing_fields"]} errors={len(result["errors"])} complete={str(result["complete"]).lower()} game_started=false')
    raise SystemExit(2 if result['errors'] else 0)
