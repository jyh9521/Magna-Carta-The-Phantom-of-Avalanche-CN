"""Pinned glossary comparison: exact text is a candidate, never concept identity."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from resource_sgi import catalog


def cells(line):
    if not line.strip().startswith('|'):
        return None
    # Split only unescaped table separators; preserve all internal spaces.
    result = re.split(r'(?<!\\)\|', line.strip())
    if result[0] != '' or result[-1] != '':
        raise ValueError('table row missing outer delimiter')
    return [cell.strip().replace('\\|', '|') for cell in result[1:-1]]


def glossary(data, lock):
    if hashlib.sha256(data).hexdigest() != lock['sha256']:
        raise ValueError('reference glossary hash mismatch')
    if not re.fullmatch(r'[0-9a-f]{40}', lock['commit']):
        raise ValueError('reference commit must be a full hash')
    rows = []
    active = False
    for number, line in enumerate(data.decode('utf-8-sig').splitlines(), 1):
        row = cells(line)
        if row == lock['header']:
            active = True
            continue
        if active and row is None:
            active = False
        if not active or row is None:
            continue
        if len(row) != 5:
            raise ValueError(f'unsupported glossary row at line {number}')
        if all(re.fullmatch(r':?-+:?', cell) for cell in row):
            continue
        if not row[0] or not row[1]:
            raise ValueError('empty source or translation in glossary')
        rows.append(dict(line=number, source=row[0], target=row[1], category=row[2],
                         status=row[3], notes=row[4]))
    if not rows:
        raise ValueError('configured glossary table not found')
    return rows


def compare(source_catalog, reference, lock, decisions=(), translations=()):
    originals = {row['id']: row for row in source_catalog['records']}
    if len(originals) != len(source_catalog['records']):
        raise ValueError('duplicate catalog row ID')
    by_source = {}
    by_line = {row['line']: row for row in reference}
    for row in reference:
        by_source.setdefault(row['source'], []).append(row)
    confirmed = {}
    for decision in decisions:
        key = decision['id']
        if key not in originals or key in confirmed:
            raise ValueError('unknown or duplicate decision ID')
        if decision['relation'] != 'confirmed_shared' or not decision.get('evidence', '').strip():
            raise ValueError('shared concept requires explicit evidence')
        ref = by_line.get(decision['reference_line'])
        if (ref is None or decision['source'] != originals[key]['source']
                or decision['reference_source'] != ref['source']):
            raise ValueError('stale source or reference decision')
        if ref['status'] != lock['locked_status']:
            raise ValueError('reference translation is not locked')
        confirmed[key] = dict(expected=ref['target'], reference_line=ref['line'], evidence=decision['evidence'])
    seen = set()
    conflicts = []
    for translation in translations:
        key = translation['id']
        if key not in originals or key in seen:
            raise ValueError('unknown or duplicate translation ID')
        seen.add(key)
        if key in confirmed and translation['target'] is not None and translation['target'] != confirmed[key]['expected']:
            conflicts.append(dict(id=key, actual=translation['target'], **confirmed[key]))
    review = [dict(id=row['id'], source=row['source'], identifier=row['identifier'], ordinal=row['ordinal'],
                   relation='confirmed_shared' if row['id'] in confirmed else 'pending',
                   expected=confirmed.get(row['id'], {}).get('expected'),
                   candidates=[dict(**ref, basis='exact_complete_source_only_not_concept_proof')
                               for ref in by_source.get(row['source'], [])])
              for row in source_catalog['records']]
    return dict(schema=1, reference={k: lock[k] for k in ('repository', 'commit', 'path', 'sha256')},
                source_resource=source_catalog['resource'], source_sha256=source_catalog['sha256'],
                records=review, conflicts=conflicts, confirmed_shared_count=len(confirmed),
                pending_count=len(review)-len(confirmed), auto_merged_ids=0,
                game_started=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sgi', type=Path, required=True)
    p.add_argument('--resource', default='Sgi/0000.sgi')
    p.add_argument('--glossary', type=Path, required=True)
    p.add_argument('--lock', type=Path, required=True)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--decisions', type=Path)
    p.add_argument('--translations', type=Path)
    a = p.parse_args()
    if a.catalog.resolve() == a.report.resolve() or a.catalog.exists() or a.report.exists():
        raise ValueError('outputs must be distinct new files')
    lock = json.loads(a.lock.read_text(encoding='utf8'))
    source = catalog(a.sgi.read_bytes(), a.resource)
    reference = glossary(a.glossary.read_bytes(), lock)
    decisions = json.loads(a.decisions.read_text(encoding='utf8')) if a.decisions else []
    translations = json.loads(a.translations.read_text(encoding='utf8')) if a.translations else []
    report = compare(source, reference, lock, decisions, translations)
    for path, result in [(a.catalog, source), (a.report, report)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf8', newline='\n') as stream:
            json.dump(result, stream, ensure_ascii=True, indent=2)
            stream.write('\n')
    count = sum(bool(row['candidates']) for row in report['records'])
    result = 'CONFLICT' if report['conflicts'] else 'PASS'
    print(f'SERIES_AUDIT {result} records={len(report["records"])} exact_candidates={count} '
          f'confirmed={report["confirmed_shared_count"]} conflicts={len(report["conflicts"])} auto_merged_ids=0 game_started=false')
    if report['conflicts']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
