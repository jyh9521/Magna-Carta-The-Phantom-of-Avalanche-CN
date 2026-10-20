"""Reproducible, source-locked text rendering inside reviewed image masks."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

from resource_image import parse


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rectangle(value, width, height):
    if (not isinstance(value, list) or len(value) != 4
            or any(type(v) is not int for v in value)):
        raise ValueError('invalid image text rectangle')
    x1, y1, x2, y2 = value
    if not 0 <= x1 < x2 <= width or not 0 <= y1 < y2 <= height:
        raise ValueError('image text rectangle exceeds image')
    return tuple(value)


def erasable(pixel, mode):
    """The same policy applies to both explicit cleanup and layout cleanup."""
    if mode not in ('all_pixels', 'neutral_ink', 'nontransparent', 'overlay'):
        raise ValueError('unsupported image text erase mode')
    return (mode != 'overlay' and
            (mode == 'all_pixels' or pixel[3] != 0) and
            (mode != 'neutral_ink' or max(pixel[:3]) - min(pixel[:3]) <= 8))


def references(plans, source, snapshots):
    """Load explicitly hash-bound background donors, never inferred neighbours."""
    result = {}
    for plan in plans:
        for repair in plan.get('background_repairs', []):
            name = repair.get('resource')
            if name is None:
                continue
            if not isinstance(name, str) or '\\' in name or ':' in name:
                raise ValueError('invalid background donor path')
            rel = PurePosixPath(name)
            if rel.is_absolute() or '..' in rel.parts or rel.as_posix() != name:
                raise ValueError('noncanonical background donor path')
            path = source/rel
            if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):
                raise ValueError('linked background donor')
            raw = path.read_bytes()
            if digest(raw) != repair.get('source_sha256'):
                raise ValueError('background donor digest mismatch')
            snapshots[path] = raw
            result[name] = parse(raw)
    return result


def repair_background(original, result, plans, covered, donors):
    """Reconstruct reviewed chrome using explicit copies/samples, before text."""
    from PIL import Image
    for plan in plans:
        repairs = plan.get('background_repairs', [])
        if not isinstance(repairs, list):
            raise ValueError('invalid background repair list')
        for repair in repairs:
            box = rectangle(repair['xyxy'], *original.size)
            if any((x,y) not in covered for y in range(box[1],box[3]) for x in range(box[0],box[2])):
                raise ValueError('background repair exceeds cleanup footprints')
            donor = original
            if repair.get('resource'):
                image = donors[repair['resource']]
                donor = Image.frombytes('RGBA', (image.width,image.height), image.rgba())
            mode = repair.get('mode', 'copy')
            if mode == 'copy':
                src = rectangle(repair['source_xyxy'], *donor.size)
                if (src[2]-src[0],src[3]-src[1]) != (box[2]-box[0],box[3]-box[1]):
                    raise ValueError('background copy size mismatch')
                piece = donor.crop(src)
                for axis, transpose in [('flip_x',Image.Transpose.FLIP_LEFT_RIGHT),('flip_y',Image.Transpose.FLIP_TOP_BOTTOM)]:
                    flag = repair.get(axis,False)
                    if type(flag) is not bool:
                        raise ValueError('invalid background reflection')
                    if flag:
                        piece = piece.transpose(transpose)
                result.paste(piece, box[:2])  # Exact RGBA copy, not double alpha blending.
            elif mode in ('solid','row_sample','column_sample'):
                anchor = repair.get('anchor')
                if (not isinstance(anchor,list) or len(anchor)!=2 or any(type(v) is not int for v in anchor)
                        or not 0<=anchor[0]<donor.width or not 0<=anchor[1]<donor.height):
                    raise ValueError('invalid background repair anchor')
                for y in range(box[1],box[3]):
                    for x in range(box[0],box[2]):
                        point = tuple(anchor) if mode=='solid' else (anchor[0],y) if mode=='row_sample' else (x,anchor[1])
                        if not 0<=point[0]<donor.width or not 0<=point[1]<donor.height:
                            raise ValueError('background sample exceeds donor')
                        result.putpixel((x,y),donor.getpixel(point))
            else:
                raise ValueError('unsupported background repair mode')


def render(image, plans, font_path, donors=None):
    from PIL import Image, ImageDraw, ImageFont
    from fontTools.ttLib import TTFont
    outline = TTFont(font_path)
    cmap = outline.getBestCmap()
    variable = 'fvar' in outline
    outline.close()
    original = Image.frombytes('RGBA', (image.width, image.height), image.rgba())
    result = original.copy()
    covered = set()
    records = []
    # Reviewed cleanup footprints are distinct from target layout rectangles.
    # Erase every source footprint before drawing any target, so adjacent old
    # glyph outlines cannot erase a target drawn by an earlier plan.
    for plan in plans:
        if 'erase_rects_xyxy' not in plan:
            continue
        regions = plan['erase_rects_xyxy']
        if not isinstance(regions, list) or not regions:
            raise ValueError('empty reviewed source cleanup footprint')
        anchor = plan['background_anchor']
        erase = plan.get('erase_mode', 'all_pixels')
        erasable((0, 0, 0, 0), erase)  # Validate even an empty/transparent mask.
        preserve_alpha = plan.get('preserve_background_alpha', False)
        if type(preserve_alpha) is not bool:
            raise ValueError('invalid background alpha policy')
        mode = plan.get('background_mode', 'solid')
        if mode not in ('solid', 'row_sample', 'column_sample'):
            raise ValueError('unsupported cleanup background mode')
        if (not isinstance(anchor,list) or len(anchor)!=2 or any(type(v) is not int for v in anchor)
                or not 0 <= anchor[0] < image.width or not 0 <= anchor[1] < image.height):
            raise ValueError('invalid cleanup background anchor')
        for region in regions:
            rect = rectangle(region,image.width,image.height)
            for y in range(rect[1],rect[3]):
                for x in range(rect[0],rect[2]):
                    covered.add((x,y))
                    if not erasable(original.getpixel((x,y)), erase):
                        continue
                    point = tuple(anchor) if mode=='solid' else (anchor[0],y) if mode=='row_sample' else (x,anchor[1])
                    pixel = original.getpixel(point)
                    if preserve_alpha:
                        pixel = (*pixel[:3], original.getpixel((x,y))[3])
                    result.putpixel((x,y),pixel)
    repair_background(original, result, plans, covered, donors or {})
    protected = set()
    for plan in plans:
        for value in plan.get('protected_rects_xyxy', []):
            rect = rectangle(value,image.width,image.height)
            for y in range(rect[1],rect[3]):
                for x in range(rect[0],rect[2]):
                    result.putpixel((x,y),original.getpixel((x,y)))
                    protected.add((x,y))
    layout_covered = set()
    for plan in plans:
        box = rectangle(plan['mask_xyxy'], image.width, image.height)
        pixels = {(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2])}
        if layout_covered & pixels:
            raise ValueError('image text masks overlap')
        covered.update(pixels)
        layout_covered.update(pixels)
        text = plan.get('target')
        erase_only = plan.get('erase_only', False)
        if type(erase_only) is not bool:
            raise ValueError('invalid image fragment erase flag')
        if erase_only and (text is not None or not plan.get('group_id')):
            raise ValueError('erased image fragment requires an explicit target group')
        if not erase_only and (not isinstance(text, str) or not text or '\0' in text):
            raise ValueError('image text target is empty or invalid')
        if not erase_only and any(ord(c) not in cmap for c in text if not c.isspace()):
            raise ValueError('outline font does not cover image target')
        if not plan.get('source_text_evidence'):
            raise ValueError('reviewed image text evidence missing')
        mode = plan.get('background_mode', 'solid')
        anchor = plan.get('background_anchor')
        if (not isinstance(anchor, list) or len(anchor) != 2
                or any(type(v) is not int for v in anchor)
                or not 0 <= anchor[0] < image.width or not 0 <= anchor[1] < image.height):
            raise ValueError('invalid background anchor')
        if mode not in ('solid', 'row_sample', 'column_sample'):
            raise ValueError('unsupported image text background mode')
        erase = plan.get('erase_mode', 'all_pixels')
        if erase not in ('all_pixels', 'neutral_ink', 'nontransparent', 'overlay'):
            raise ValueError('unsupported image text erase mode')
        # Neutral white/gray/black lettering is separated from colored UI chrome.
        # Review chooses the mask and template anchor; this is not OCR or a
        # license to erase arbitrary artwork outside the reviewed rectangle.
        for y in range(box[1], box[3]):
            for x in range(box[0], box[2]):
                old = original.getpixel((x, y))
                if erase == 'overlay' or 'erase_rects_xyxy' in plan:
                    continue
                if not erasable(old, erase):
                    continue
                point = tuple(anchor) if mode == 'solid' else (anchor[0], y) if mode == 'row_sample' else (x, anchor[1])
                result.putpixel((x, y), original.getpixel(point))
        if erase_only:
            records.append(dict(target=None, mask_xyxy=list(box), group_id=plan['group_id'],
                                state='group_fragment_removed'))
            continue
        maximum, minimum = plan.get('font_size', 14), plan.get('minimum_font_size', 10)
        stroke = plan.get('stroke_width', 1)
        if (any(type(v) is not int for v in (maximum, minimum, stroke))
                or not 1 <= minimum <= maximum <= 128 or not 0 <= stroke <= 4):
            raise ValueError('invalid image text typography')
        fill = plan.get('color', [255, 255, 255, 255])
        edge = plan.get('stroke_color', [0, 0, 0, 255])
        for color in (fill, edge):
            if not isinstance(color, list) or len(color) != 4 or any(type(c) is not int or not 0 <= c <= 255 for c in color):
                raise ValueError('invalid RGBA text color')
        chosen = None
        rotation=plan.get('rotation',0)
        flow=plan.get('flow','horizontal')
        if flow not in ('horizontal','vertical') or (flow=='vertical' and rotation):
            raise ValueError('invalid image text flow/rotation combination')
        gap=plan.get('glyph_gap',2)
        if type(gap) is not int or not 0<=gap<=32:raise ValueError('invalid vertical glyph gap')
        if type(rotation) is not int or rotation not in (0,90,270):
            raise ValueError('invalid image text rotation')
        for size in range(maximum, minimum - 1, -1):
            font = ImageFont.truetype(str(font_path), size)
            if variable and hasattr(font, 'set_variation_by_axes'):
                axes = font.get_variation_axes()
                font.set_variation_by_axes([min(a['maximum'], max(a['minimum'], 600)) for a in axes])
            bounds = font.getbbox(text, stroke_width=stroke)
            w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
            if flow=='vertical':
                glyph_bounds=[font.getbbox(c,stroke_width=stroke) for c in text]
                w=max(b[2]-b[0] for b in glyph_bounds)
                h=sum(b[3]-b[1] for b in glyph_bounds)+gap*(len(text)-1)
            if rotation:w,h=h,w
            if w <= box[2] - box[0] - 2 and h <= box[3] - box[1] - 2:
                chosen = size, font, bounds, w, h
                break
        if chosen is None:
            raise ValueError('image target does not fit reviewed mask: ' + text)
        size, font, bounds, w, h = chosen
        align = plan.get('align', 'center')
        if align not in ('left', 'center', 'right'):
            raise ValueError('invalid text alignment')
        x = box[0] + (1 if align == 'left' else box[2] - box[0] - w - 1 if align == 'right' else (box[2] - box[0] - w) // 2)
        y = box[1] + (box[3] - box[1] - h) // 2
        if flow=='vertical':
            draw=ImageDraw.Draw(result);cursor=y
            for character in text:
                b=font.getbbox(character,stroke_width=stroke);gw=b[2]-b[0];gh=b[3]-b[1]
                gx=box[0]+(box[2]-box[0]-gw)//2
                draw.text((gx-b[0],cursor-b[1]),character,font=font,fill=tuple(fill),stroke_width=stroke,stroke_fill=tuple(edge))
                cursor+=gh+gap
        elif rotation:
            layer=Image.new('RGBA',(bounds[2]-bounds[0],bounds[3]-bounds[1]))
            ImageDraw.Draw(layer).text((-bounds[0],-bounds[1]),text,font=font,
                                     fill=tuple(fill),stroke_width=stroke,stroke_fill=tuple(edge))
            layer=layer.rotate(rotation,expand=True)
            result.paste(layer,(x,y),layer)
        else:
            ImageDraw.Draw(result).text((x - bounds[0], y - bounds[1]), text, font=font,
                                        fill=tuple(fill), stroke_width=stroke, stroke_fill=tuple(edge))
        records.append(dict(target=text, mask_xyxy=list(box), erase_rects_xyxy=plan.get('erase_rects_xyxy'), size=size,
                            measured_pixels=[w, h], rotation=rotation, flow=flow, fit=True))
    before, after = original.tobytes(), result.tobytes()
    if any(before[(y*image.width+x)*4:(y*image.width+x)*4+4] !=
           after[(y*image.width+x)*4:(y*image.width+x)*4+4] for x,y in protected):
        raise ValueError('text overlaps protected artwork')
    for i in range(image.width * image.height):
        if (i % image.width, i // image.width) not in covered and before[i*4:i*4+4] != after[i*4:i*4+4]:
            raise ValueError('render modifies a pixel outside the approved masks')
    rewritten = image.replace_rgba(after)
    if (rewritten.wrapper, rewritten.header, rewritten.suffix, rewritten.width, rewritten.height) != (
            image.wrapper, image.header, image.suffix, image.width, image.height):
        raise ValueError('image metadata changed during text rendering')
    return rewritten.to_bytes(), records, result


def build(source, plans_path, font_path, font_sha256, output):
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    plans_path, font_path = Path(plans_path).resolve(strict=True), Path(font_path).resolve(strict=True)
    if (output.exists() or output.is_relative_to(source) or source.is_relative_to(output)
            or any(p.is_relative_to(output) for p in (plans_path, font_path))):
        raise ValueError('image output must be a new separate directory')
    raw_plans, raw_font = plans_path.read_bytes(), font_path.read_bytes()
    if digest(raw_font) != font_sha256:
        raise ValueError('outline font digest mismatch')
    data = json.loads(raw_plans)
    if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('resources'), list):
        raise ValueError('invalid image text plan schema')
    originals, results, records, previews = {}, {}, [], {}
    for resource in data['resources']:
        if (not isinstance(resource, dict) or not isinstance(resource.get('plans'), list)
                or not resource['plans'] or any(not isinstance(p, dict) for p in resource['plans'])):
            raise ValueError('invalid image resource plan list')
    groups={p['group_id'] for r in data['resources'] for p in r.get('plans',[])
            if p.get('group_id') and isinstance(p.get('target'),str) and p['target']}
    if any(p.get('erase_only') and p.get('group_id') not in groups
           for r in data['resources'] for p in r.get('plans',[])):
        raise ValueError('image fragment has no translated group member')
    for resource in data['resources']:
        name = resource.get('resource')
        if not isinstance(name, str) or '\\' in name or ':' in name:
            raise ValueError('invalid image resource path')
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or name != rel.as_posix() or name in results:
            raise ValueError('duplicate or noncanonical image resource path')
        path = source / rel
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):
            raise ValueError('linked image resource is not supported')
        original = path.read_bytes()
        if digest(original) != resource.get('source_sha256'):
            raise ValueError('image source digest mismatch')
        image = parse(original)
        plans = resource.get('plans')
        if not isinstance(plans, list) or not plans:
            raise ValueError('image has no reviewed target plans')
        donors = references(plans, source, originals)
        rewritten, text_records, preview = render(image, plans, font_path, donors)
        if parse(rewritten).rgba() != preview.tobytes():
            raise ValueError('image pixel readback mismatch')
        originals[path] = original; results[name] = rewritten; previews[name] = preview
        records.append(dict(resource=name, original_sha256=digest(original), modified_sha256=digest(rewritten),
                            size=len(original), dimensions=[image.width,image.height], metadata_preserved=True,
                            outside_masks_preserved=True, texts=text_records))
    if not results:
        raise ValueError('empty image text build')
    if (plans_path.read_bytes() != raw_plans or font_path.read_bytes() != raw_font
            or any(p.read_bytes() != b for p, b in originals.items())):
        raise ValueError('image build input changed before publication')
    manifest=dict(schema=1, kind='reviewed_image_text_candidate', plans_sha256=digest(raw_plans),
                  font_sha256=font_sha256, resources=records, source_unchanged=True,
                  all_game_text_complete=False, deployed=False, game_started=False, in_game_verified=False)
    output.mkdir(parents=True)
    for name, raw in results.items():
        path = output/name; path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        preview_path = output/'previews'/f'{name}.png';preview_path.parent.mkdir(parents=True,exist_ok=True)
        previews[name].save(preview_path)
    (output/'build.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    return manifest


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--plans',type=Path,required=True);p.add_argument('--font',type=Path,required=True)
    p.add_argument('--font-sha256',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=build(a.source,a.plans,a.font,a.font_sha256,a.output)
    print(f'IMAGE_TEXT_BUILD PASS resources={len(r["resources"])} texts={sum(bool(t["target"]) for x in r["resources"] for t in x["texts"])} '
          'outside_masks_preserved=true metadata_preserved=true deployed=false game_started=false')
