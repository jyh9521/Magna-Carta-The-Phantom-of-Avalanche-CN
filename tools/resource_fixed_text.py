"""Source-bound rewriting of verified, fixed-size display fields.

Policies approve individual fields, not resource identifiers or internal object
labels. Disk capacities and conservative formatter budgets are independent.
"""
from pathlib import PurePosixPath
import hashlib

from extract_text_catalog import fixed_records, text_row
from native_text_codec import encode, decode
from resource_sgi import catalog as sgi_catalog
from translation_data import validate


def fields(data, resource):
    ext = PurePosixPath(resource).suffix.lower()
    if ext in ('.itm', '.abi', '.cha'):
        return fixed_records(data, resource, ext)
    if ext == '.sgi':
        return [text_row(resource, r['ordinal'], r['identifier'], 'name',
                         r['offset'], bytes.fromhex(r['source_hex']), 100)
                for r in sgi_catalog(data, resource)['records']]
    raise ValueError('unsupported fixed text resource')


def checked_decisions(data):
    if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('decisions'), list):
        raise ValueError('invalid fixed field decisions')
    result = {}
    for row in data['decisions']:
        if (not isinstance(row, dict) or not isinstance(row.get('id'), str)
                or row['id'] in result or not row.get('evidence')
                or row.get('field_semantics') not in ('display_name', 'display_description', 'internal_object_label')
                or not isinstance(row.get('source_sha256'), str)
                or len(row['source_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in row['source_sha256'])):
            raise ValueError('invalid or duplicate fixed field decision')
        result[row['id']] = row
    return result


def rebuild_fixed(original, resource, catalog, targets, mapping, decisions):
    actual = fields(original, resource)
    supplied = [r for r in catalog if r['resource'] == resource]
    by_id = {r['id']: r for r in supplied}
    if len(by_id) != len(actual) or len(by_id) != len(supplied):
        raise ValueError('fixed field catalog count mismatch')
    for row in actual:
        source = by_id.get(row['id'])
        if source is None or any(source.get(k) != row.get(k) for k in
                                 ('ordinal', 'identifier', 'field', 'offset', 'source_hex', 'source', 'candidate_capacity')):
            raise ValueError('fixed field catalog does not match original bytes')
    chosen = [r for r in targets if r['id'] in by_id]
    report = validate(actual, chosen, mapping=mapping, require_complete=True)
    if report['errors']:
        raise ValueError('fixed targets incomplete or invalid')
    policies = checked_decisions(decisions)
    result = bytearray(original)
    changes = []
    for target in chosen:
        row = by_id[target['id']]
        policy = policies.get(row['id'])
        digest = hashlib.sha256(bytes.fromhex(row['source_hex'])).hexdigest()
        if policy is None or policy['source_sha256'] != digest:
            raise ValueError('missing or stale fixed field decision')
        if target['state'] == 'preserved':
            if policy['field_semantics'] != 'internal_object_label':
                raise ValueError('display field cannot be silently preserved')
            continue
        expected_role = 'display_name' if row['field'] == 'name' else 'display_description'
        if policy['field_semantics'] != expected_role:
            raise ValueError('internal field is not approved for rewriting')
        encoded = encode(target['target'], mapping)
        capacity = row['candidate_capacity']
        # Single/two-item acquisition messages permit at most 79 combined name
        # bytes with the original templates: 39 per name is conservative.
        budget = (59 if resource.lower().endswith('.abi') else 39) if row['field'] == 'name' else 99
        if len(encoded) + 1 > capacity or len(encoded) > budget:
            raise ValueError('fixed field or formatter budget overflow: ' + row['id'])
        if decode(encoded, mapping) != target['target']:
            raise ValueError('fixed target encoding roundtrip mismatch')
        start = row['offset']
        # Preserve bytes after both original and new terminators. In particular,
        # do not normalize unknown nonzero padding elsewhere in a field.
        span = max(row['original_span'], len(encoded) + 1)
        if any(original[start + row['original_span']:start + span]):
            raise ValueError('expanded target overlaps unknown nonzero field padding: ' + row['id'])
        result[start:start + span] = encoded + bytes(span - len(encoded))
        changes.append((start, start + span))
    rebuilt = bytes(result)
    if len(rebuilt) != len(original):
        raise ValueError('fixed resource length changed')
    allowed = set(i for start, end in changes for i in range(start, end))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(original, rebuilt))):
        raise ValueError('fixed resource modifies a non-target byte')
    # Private native codes are deliberately not decoded as CP949 on readback.
    # All record IDs/header/attributes are outside approved field spans above.
    for target in chosen:
        row = by_id[target['id']]
        slot = rebuilt[row['offset']:row['offset'] + row['candidate_capacity']]
        if b'\0' not in slot:
            raise ValueError('rebuilt fixed field has no terminator')
        raw = slot.split(b'\0', 1)[0]
        if target['state'] == 'preserved':
            if raw != bytes.fromhex(row['source_hex']):
                raise ValueError('preserved fixed field changed')
        elif decode(raw, mapping) != target['target']:
            raise ValueError('fixed resource readback mismatch')
    return rebuilt
