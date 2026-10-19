"""Audit/normalize explicitly selected prompt domains without touching dialogue."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from extract_text_catalog import TOKENS


def normalize(text, policy):
    """A layout line is independent; commas and multi-sentence lines keep punctuation."""
    separators = policy['line_separators']
    pattern = '(' + '|'.join(re.escape(s) for s in sorted(separators, key=len, reverse=True)) + ')'
    pieces = re.split(pattern, text) if separators else [text]
    for index in range(0, len(pieces), 2):
        line = pieces[index]
        terminal = policy['terminal']
        if (line.endswith(terminal) and len(line) > len(terminal)
                and not any(mark in line[:-len(terminal)] for mark in policy['retain_if_contains'])):
            pieces[index] = line[:-len(terminal)]
    result = ''.join(pieces)
    if TOKENS.findall(text) != TOKENS.findall(result):
        raise ValueError('normalization changed protected tokens')
    return result


def records(value, pointer=''):
    if isinstance(value, dict):
        if isinstance(value.get('target'), str):
            yield pointer + '/target', value
        for key, child in value.items():
            yield from records(child, pointer + '/' + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from records(child, pointer + '/' + str(index))


def selected(path, pointer, row, policy):
    for domain in policy['domains']:
        if path != domain['file']:
            continue
        if 'id_prefix' in domain and not row.get('id', '').startswith(domain['id_prefix']):
            continue
        if 'id_contains' in domain and domain['id_contains'] not in row.get('id', ''):
            continue
        if not any(pointer.startswith(prefix) for prefix in domain.get('pointer_prefixes', [''])):
            continue
        return domain['context']
    return None


def audit(locale, policy, apply=False):
    locale = Path(locale).resolve(strict=True)
    changed = []
    scanned = eligible = 0
    files = []
    for path in sorted(locale.rglob('*.json')):
        relative = path.relative_to(locale).as_posix()
        original = path.read_bytes()
        value = json.loads(original)
        local = []
        for pointer, row in records(value):
            scanned += 1
            context = selected(relative, pointer, row, policy)
            if context is None:
                continue
            eligible += 1
            before = row['target']
            after = normalize(before, policy)
            if before == after:
                continue
            change = dict(file=relative, pointer=pointer, id=row.get('id'),
                          source_sha256=row.get('source_sha256'), context=context,
                          before=before, after=after, removed=len(before)-len(after))
            local.append(change)
            row['target'] = after
        if not local:
            continue
        # Preserve original serialization and all unrelated bytes, including CRLF.
        modified = original
        for change in local:
            old = json.dumps(change['before'], ensure_ascii=False).encode('utf8')
            new = json.dumps(change['after'], ensure_ascii=False).encode('utf8')
            # Addressed rows may share their text; replace only the target key.
            modified = modified.replace(b'"target": ' + old, b'"target": ' + new)
        if json.loads(modified) != value:
            raise ValueError('serialization changed an unselected field: ' + relative)
        if apply:
            if path.read_bytes() != original:
                raise ValueError('input drift')
            path.write_bytes(modified)
            if path.read_bytes() != modified:
                raise ValueError('write readback mismatch')
        files.append(dict(file=relative, before_sha256=hashlib.sha256(original).hexdigest(),
                          after_sha256=hashlib.sha256(modified).hexdigest()))
        changed.extend(local)
    return dict(schema=1, scanned_targets=scanned, eligible_targets=eligible,
                changed_fields=len(changed), removed_terminals=sum(r['removed'] for r in changed),
                files=files, changes=changed, applied=apply,
                protected_tokens_unchanged=True, dialogue_unchanged=True, in_game_verified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--locale', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.report.exists() or args.report.resolve().is_relative_to(args.locale.resolve()):
        raise ValueError('report must be new and outside locale inputs')
    report = audit(args.locale, json.loads(args.policy.read_text('utf8')), args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(f'PROMPT_PUNCTUATION {"APPLIED" if args.apply else "AUDIT"} scanned={report["scanned_targets"]} eligible={report["eligible_targets"]} changed={report["changed_fields"]} removed={report["removed_terminals"]}')
    raise SystemExit(0 if args.apply or not report['changed_fields'] else 2)
