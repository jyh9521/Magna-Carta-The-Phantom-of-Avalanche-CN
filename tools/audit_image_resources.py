"""Compare every installed BGR with read-only CD/1.04 inputs and reviewed masks.

No game execution, image mounting, or full-game extraction. Optional extraction
contains only the small source-locked image fixtures needed by the two builders.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw, ImageChops
from build_image_text import rectangle
from resource_image import parse


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def original_images(iso_path, patch_path):
    import pycdlib
    result = {}
    iso = pycdlib.PyCdlib()
    iso.open(str(iso_path))
    try:
        for parent, _, files in iso.walk(iso_path='/SETUP/BGR'):
            for name in files:
                if not name.upper().endswith('.BGR'):
                    continue
                stream = io.BytesIO()
                iso.get_file_from_iso_fp(stream, iso_path=parent+'/'+name)
                key = 'BGR/'+name.upper()
                if key in result:
                    raise ValueError('Duplicate source image: '+key)
                result[key] = stream.getvalue()
    finally:
        iso.close()
    with zipfile.ZipFile(patch_path) as patch:
        seen = set()
        for item in patch.infolist():
            if item.filename.lower().startswith('bgr/') and item.filename.lower().endswith('.bgr'):
                if len(Path(item.filename).parts) != 2:
                    raise ValueError('Unexpected patch image path')
                key = 'BGR/'+Path(item.filename).name.upper()
                if key in seen:
                    raise ValueError('Duplicate patch image: '+key)
                seen.add(key)
                result[key] = patch.read(item)
    if not result:
        raise ValueError('No source images')
    return result


def reviewed_images(plans, groups):
    """Return per-tile allowed rectangles, hashes, and protected source areas."""
    rows = {}
    for resource in plans['resources']:
        name = resource['resource']
        rows[name] = dict(source_sha256=resource['source_sha256'], allowed=[], protected=[])
        for plan in resource['plans']:
            rows[name]['allowed'] += [plan['mask_xyxy'], *plan.get('erase_rects_xyxy', [])]
            rows[name]['protected'] += plan.get('protected_rects_xyxy', [])
    for group in groups['groups']:
        allowed = [rect for p in group['plans'] for rect in [p['mask_xyxy'], *p.get('erase_rects_xyxy', [])]]
        artwork = group.get('artwork', {})
        allowed += [p['mask_xyxy'] for p in artwork.get('overlays', [])]
        if artwork.get('background_patch'):
            allowed.append(artwork['background_patch']['mask_xyxy'])
        for tile in group['tiles']:
            name = tile['resource']
            if name in rows:
                raise ValueError('Image belongs to multiple build units: '+name)
            rows[name] = dict(source_sha256=tile['source_sha256'], allowed=allowed,
                              protected=[r for p in group['plans'] for r in p.get('protected_rects_xyxy', [])],
                              origin=tile['xy'])
    return rows


def local_boxes(boxes, origin, size):
    ox, oy = origin
    w, h = size
    for a,b,c,d in boxes:
        box = [max(0,a-ox),max(0,b-oy),min(w,c-ox),min(h,d-oy)]
        if box[0]<box[2] and box[1]<box[3]:
            yield box


def pixels(image):
    return Image.frombytes('RGBA', (image.width,image.height), image.rgba())


def audit(originals, workspace, plans, groups, checks, overrides=None):
    workspace = Path(workspace).resolve(strict=True)
    reviewed = reviewed_images(plans, groups)
    approved = {r['resource']: r for r in checks.get('approved_replacements', [])}
    actual = {'BGR/'+p.name.upper(): p for p in (workspace/'BGR').iterdir() if p.is_file() and p.suffix.lower()=='.bgr'}
    overrides = overrides or {}
    if overrides.keys()-actual.keys():
        raise ValueError('Candidate adds unknown image names')
    read = lambda name: overrides[name] if name in overrides else actual[name].read_bytes()
    if len(actual) != len(list((workspace/'BGR').glob('*.[Bb][Gg][Rr]'))):
        raise ValueError('Case-colliding image names')
    errors = []
    if actual.keys() != originals.keys():
        errors.append(dict(kind='inventory',missing=sorted(originals.keys()-actual.keys()),extra=sorted(actual.keys()-originals.keys())))
    if reviewed.keys()-originals.keys() or approved.keys()-originals.keys():
        raise ValueError('Review references missing source images')
    records = []
    for name, raw in sorted(originals.items()):
        if name not in actual:
            continue
        before = parse(raw)
        current = read(name)
        after = parse(current)
        a,b = sha(raw),sha(current)
        row = dict(resource=name,source_sha256=a,current_sha256=b,changed=a!=b,
                   dimensions=[after.width,after.height],reviewed=name in reviewed,
                   approved_replacement=name in approved)
        if name in approved:
            r = approved[name]
            if a!=r['source_sha256'] or b!=r['target_sha256'] or row['dimensions']!=r['dimensions']:
                errors.append(dict(resource=name,kind='approved_replacement_drift'))
            records.append(row)
            continue
        if (before.wrapper,before.header,before.suffix)!=(after.wrapper,after.header,after.suffix):
            errors.append(dict(resource=name,kind='metadata'))
            records.append(row)
            continue
        if name in reviewed:
            r = reviewed[name]
            if r['source_sha256'] != a:
                raise ValueError('Reviewed source hash mismatch: '+name)
            src,dst = pixels(before),pixels(after)
            mask = Image.new('L',src.size)
            draw = ImageDraw.Draw(mask)
            for box in local_boxes(r['allowed'],r.get('origin',[0,0]),src.size):
                draw.rectangle((box[0],box[1],box[2]-1,box[3]-1),fill=255)
            # Compare all four channels, including hidden RGB; alpha-only
            # Image.getbbox on RGBA would miss an opaque RGB-only regression.
            diff = ImageChops.difference(src,dst)
            changed = ImageChops.lighter(ImageChops.lighter(diff.getchannel('R'),diff.getchannel('G')),
                                         ImageChops.lighter(diff.getchannel('B'),diff.getchannel('A')))
            outside = ImageChops.multiply(changed, ImageChops.invert(mask))
            row['outside_changed_pixels'] = sum(v!=0 for v in outside.tobytes())
            if row['outside_changed_pixels']:
                errors.append(dict(resource=name,kind='outside_reviewed_masks',pixels=row['outside_changed_pixels']))
            for box in local_boxes(r['protected'],r.get('origin',[0,0]),src.size):
                if src.crop(box).tobytes()!=dst.crop(box).tobytes():
                    errors.append(dict(resource=name,kind='protected_artwork',xyxy=box))
        elif a != b:
            errors.append(dict(resource=name,kind='unreviewed_change'))
        records.append(row)
    for check in checks.get('checks', []):
        name = check['resource']
        dst = pixels(parse(read(name)))
        src = pixels(parse(originals[check.get('donor',name)]))
        for box in check['regions_xyxy']:
            rectangle(box,*dst.size)
            region = dst.crop(box)
            if check['kind']=='source':
                expected = src.crop(box)
            elif check['kind']=='rgba':
                expected = Image.new('RGBA',region.size,tuple(check['rgba']))
            elif check['kind']=='alpha':
                expected = src.crop(box).getchannel('A')
                region = region.getchannel('A')
            else:
                raise ValueError('Unknown image invariant')
            if region.tobytes()!=expected.tobytes():
                errors.append(dict(resource=name,kind='invariant',meaning=check['meaning'],xyxy=box))
    for check in checks.get('phrases', []):
        group = next(g for g in groups['groups'] if g['id']==check['group'])
        if [p.get('target') for p in group['plans'] if p.get('target')] != [check['target']]:
            errors.append(dict(kind='split_phrase',group=check['group']))
    return dict(schema=1,images=len(records),reviewed=len(reviewed),approved_replacements=len(approved),
                changed_images=sum(r['changed'] for r in records),records=records,errors=errors,
                game_started=False,in_game_verified=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['iso','patch','workspace','plans','groups','checks','report']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--extract-to',type=Path)
    p.add_argument('--candidates',type=Path,nargs='+')
    p.add_argument('--retain-approved',action='store_true')
    a = p.parse_args()
    if a.report.exists() or (a.extract_to and a.extract_to.exists()):
        p.error('New report / minimal source fixture directory required')
    plans,groups,checks = [json.loads(x.read_text(encoding='utf8')) for x in [a.plans,a.groups,a.checks]]
    originals = original_images(a.iso,a.patch)
    overrides = {}
    if a.candidates:
        from locale_package import collect
        approved = {r['resource'] for r in checks.get('approved_replacements',[])}
        overrides = {n:path.read_bytes() for n,path in collect(a.candidates).items()
                     if not (a.retain_approved and n in approved)}
    report = audit(originals,a.workspace,plans,groups,checks,overrides)
    report['input_sha256'] = {n:sha(path.read_bytes()) for n,path in [('iso',a.iso),('patch',a.patch),('plans',a.plans),('groups',a.groups),('checks',a.checks)]}
    if a.extract_to:
        names = set(reviewed_images(plans,groups))
        names.update(r['resource'] for unit in [*plans['resources'],*groups['groups']]
                     for plan in unit['plans'] for r in plan.get('background_repairs',[]) if r.get('resource'))
        for name in sorted(names):
            dest = a.extract_to/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(originals[name])
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('IMAGE_INTEGRITY %s images=%d reviewed=%d replacements=%d errors=%d game_started=false' %
          ('FAIL' if report['errors'] else 'PASS',report['images'],report['reviewed'],report['approved_replacements'],len(report['errors'])))
    return 1 if report['errors'] else 0


if __name__=='__main__':
    raise SystemExit(main())
