import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import ImageFont

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_image_text as m
from resource_image import parse
from test_resource_image import tga


class Outline:
    def __init__(self, *_): pass
    def __contains__(self, _): return False
    def getBestCmap(self): return {i:'glyph' for i in range(32,127)}
    def close(self): pass


class ImageTextBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir()
        self.raw=tga(width=80,height=40);(self.source/'fixture.bgr').write_bytes(self.raw)
        self.font=self.root/'font.ttf';self.font.write_bytes(b'controlled-outline')
        self.font_hash=m.digest(self.font.read_bytes());self.plans=self.root/'plans.json'
        self.output=self.root/'output'
        self.plan=dict(target='Text',mask_xyxy=[5,5,75,35],background_anchor=[0,0],
                       font_size=12,minimum_font_size=10,stroke_width=0,source_text_evidence='controlled original field')
        self.data=dict(schema=1,resources=[dict(resource='fixture.bgr',source_sha256=m.digest(self.raw),plans=[self.plan])])
        self.default=ImageFont.load_default()
        self.tt=patch('fontTools.ttLib.TTFont',Outline);self.tt.start();self.addCleanup(self.tt.stop)
        self.ft=patch('PIL.ImageFont.truetype',return_value=self.default);self.ft.start();self.addCleanup(self.ft.stop)

    def build(self):
        self.plans.write_text(json.dumps(self.data),encoding='utf8')
        return m.build(self.source,self.plans,self.font,self.font_hash,self.output)

    def test_build_preserves_metadata_and_pixels_outside_mask(self):
        r=self.build();original=parse(self.raw);modified=parse((self.output/'fixture.bgr').read_bytes())
        self.assertEqual((original.wrapper,original.header,original.suffix),
                         (modified.wrapper,modified.header,modified.suffix))
        a,b=original.rgba(),modified.rgba()
        for y in range(40):
            for x in range(80):
                if not (5<=x<75 and 5<=y<35):
                    i=(y*80+x)*4;self.assertEqual(a[i:i+4],b[i:i+4])
        self.assertFalse(r['deployed']);self.assertFalse(r['game_started'])
        self.assertEqual((self.source/'fixture.bgr').read_bytes(),self.raw)

    def test_vertical_flow_stacks_upright_glyphs_and_preserves_outside(self):
        p=dict(self.plan,target='AB',mask_xyxy=[25,5,45,35],flow='vertical',glyph_gap=3)
        raw,records,_=m.render(parse(self.raw),[p],self.font)
        self.assertEqual(records[0]['flow'],'vertical');self.assertEqual(records[0]['rotation'],0)
        self.assertGreater(records[0]['measured_pixels'][1],records[0]['measured_pixels'][0])
        a,b=parse(self.raw).rgba(),parse(raw).rgba()
        for y in range(40):
            for x in range(80):
                if not(25<=x<45 and 5<=y<35):
                    at=(y*80+x)*4;self.assertEqual(a[at:at+4],b[at:at+4])
        with self.assertRaises(ValueError):m.render(parse(self.raw),[dict(p,rotation=90)],self.font)

    def test_stale_source_and_font_lock_refuse_output(self):
        self.data['resources'][0]['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'digest mismatch'):self.build()
        self.assertFalse(self.output.exists())
        self.data['resources'][0]['source_sha256']=m.digest(self.raw);self.font_hash='0'*64
        with self.assertRaisesRegex(ValueError,'font digest mismatch'):self.build()

    def test_source_cleanup_can_cover_outline_outside_target_layout(self):
        image=parse(self.raw)
        raw=bytearray(image.rgba())
        at=(3*80+10)*4;raw[at:at+4]=b'\xff\xff\xff\xff'
        changed=image.replace_rgba(bytes(raw)).to_bytes()
        self.plan['erase_rects_xyxy']=[[9,2,12,5],self.plan['mask_xyxy']]
        result,_,_=m.render(parse(changed),[self.plan],self.font)
        after=parse(result).rgba()
        self.assertEqual(after[at:at+4],image.rgba()[:4])
        self.assertEqual(after[:4],image.rgba()[:4])

    def test_empty_or_invalid_cleanup_footprints_fail(self):
        for rects in [[],[[0,0,81,4]],[[0,0,True,4]]]:
            self.plan['erase_rects_xyxy']=rects
            with self.assertRaises(ValueError):m.render(parse(self.raw),[self.plan],self.font)

    def test_missing_evidence_and_empty_target_refuse_output(self):
        for key,value in [('source_text_evidence',''),('target',''),('target','x\0')]:
            plan=copy.deepcopy(self.plan);plan[key]=value;self.data['resources'][0]['plans']=[plan]
            with self.assertRaises(ValueError):self.build()
            self.assertFalse(self.output.exists())

    def test_unsupported_character_and_overflow_refuse_output(self):
        self.plan['target']='中'
        with self.assertRaisesRegex(ValueError,'does not cover'):self.build()
        self.plan['target']='x'*200
        with self.assertRaisesRegex(ValueError,'does not fit'):self.build()
        self.assertFalse(self.output.exists())

    def test_duplicate_resource_and_overlapping_masks_refuse_output(self):
        self.data['resources'].append(copy.deepcopy(self.data['resources'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):self.build()
        self.data['resources'].pop();self.data['resources'][0]['plans'].append(copy.deepcopy(self.plan))
        with self.assertRaisesRegex(ValueError,'overlap'):self.build()

    def test_out_of_bounds_and_wrong_types_refuse_output(self):
        for box in [[-1,5,75,35],[5,5,81,35],[5,5,75,41],[5,5,5,35],[5,5,True,35],None]:
            self.plan['mask_xyxy']=box
            with self.assertRaises(ValueError):self.build()

    def test_path_traversal_absolute_and_backslash_refuse_output(self):
        for name in ['../fixture.bgr','/fixture.bgr','a\\fixture.bgr','a/../fixture.bgr','C:/fixture.bgr','./fixture.bgr']:
            self.data['resources'][0]['resource']=name
            with self.assertRaises(ValueError):self.build()
            self.assertFalse(self.output.exists())

    def test_existing_or_nested_outputs_are_rejected(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError,'new separate'):self.build()
        self.output=self.source/'nested'
        with self.assertRaisesRegex(ValueError,'new separate'):self.build()

    def test_input_drift_during_render_refuses_publication(self):
        original=m.render
        def drift(*args):
            result=original(*args);(self.source/'fixture.bgr').write_bytes(b'changed');return result
        with patch.object(m,'render',side_effect=drift):
            with self.assertRaisesRegex(ValueError,'input changed'):self.build()
        self.assertFalse(self.output.exists())

    def test_background_modes_and_erase_mode_validation(self):
        self.plan['background_mode']='unsupported'
        with self.assertRaises(ValueError):self.build()
        self.plan['background_mode']='column_sample';self.plan['erase_mode']='unsupported'
        with self.assertRaises(ValueError):self.build()
        self.plan['erase_mode']='neutral_ink';self.build()

    def test_neutral_ink_erasure_preserves_colored_chrome(self):
        image=parse(self.raw);rgba=bytearray(image.rgba());i=(6*80+6)*4;rgba[i:i+4]=bytes([255,128,0,255]);image=image.replace_rgba(rgba)
        self.plan.update(erase_mode='neutral_ink')
        raw,records,preview=m.render(image,[self.plan],self.font)
        self.assertEqual(parse(raw).rgba()[i:i+4],bytes([255,128,0,255]))

    def test_erase_only_fragment_requires_translated_group(self):
        fragment=dict(target=None,erase_only=True,group_id='group',mask_xyxy=[0,0,4,4],
                      background_anchor=[79,39],source_text_evidence='continuation of a split title')
        self.data['resources'][0]['plans'].append(fragment)
        with self.assertRaisesRegex(ValueError,'no translated group'):self.build()
        self.plan['group_id']='group'
        report=self.build()
        self.assertEqual(report['resources'][0]['texts'][1]['state'],'group_fragment_removed')

    def test_malformed_resource_and_plan_rows_are_rejected(self):
        for rows in [[None],[dict(plans=[None])],[dict(plans='text')]]:
            self.data['resources']=rows
            with self.assertRaisesRegex(ValueError,'plan list'):self.build()
            self.assertFalse(self.output.exists())

    def test_nontransparent_mode_preserves_zero_alpha(self):
        image=parse(self.raw);rgba=bytearray(image.rgba());i=(6*80+6)*4
        rgba[i:i+4]=bytes([255,128,0,0]);image=image.replace_rgba(rgba)
        self.plan['erase_mode']='nontransparent'
        raw,_,_=m.render(image,[self.plan],self.font)
        self.assertEqual(parse(raw).rgba()[i:i+4],bytes([255,128,0,0]))

    def test_explicit_cleanup_respects_transparent_corners(self):
        image=parse(self.raw);rgba=bytearray(image.rgba());i=(6*80+6)*4
        rgba[i:i+4]=bytes([255,128,0,0]);image=image.replace_rgba(rgba)
        self.plan.update(erase_mode='nontransparent',erase_rects_xyxy=[[5,5,75,35]])
        raw,_,_=m.render(image,[self.plan],self.font)
        self.assertEqual(parse(raw).rgba()[i:i+4],bytes([255,128,0,0]))

    def test_explicit_neutral_cleanup_preserves_colored_chrome(self):
        image=parse(self.raw);rgba=bytearray(image.rgba());i=(6*80+6)*4
        rgba[i:i+4]=bytes([255,128,0,255]);image=image.replace_rgba(rgba)
        self.plan.update(erase_mode='neutral_ink',erase_rects_xyxy=[[5,5,75,35]])
        raw,_,_=m.render(image,[self.plan],self.font)
        self.assertEqual(parse(raw).rgba()[i:i+4],bytes([255,128,0,255]))

    def test_rounded_background_cleanup_preserves_antialias_alpha(self):
        image=parse(self.raw);rgba=bytearray(image.rgba());i=(6*80+6)*4
        rgba[i:i+4]=bytes([255,128,0,37]);image=image.replace_rgba(rgba)
        self.plan.update(erase_mode='nontransparent',preserve_background_alpha=True,
                         erase_rects_xyxy=[[5,5,75,35]])
        raw,_,_=m.render(image,[self.plan],self.font)
        self.assertEqual(parse(raw).rgba()[i+3],37)

    def test_background_copy_reflects_rgba_without_double_alpha(self):
        image=parse(self.raw);rgba=bytearray(image.rgba())
        for y in range(2):
            for x in range(2):
                i=(y*80+x)*4;rgba[i:i+4]=bytes([x*80,y*80,44,37])
        image=image.replace_rgba(rgba)
        self.plan.update(erase_rects_xyxy=[[5,5,75,35]],background_repairs=[
            dict(xyxy=[6,6,8,8],source_xyxy=[0,0,2,2],flip_y=True)])
        _,_,preview=m.render(image,[self.plan],self.font)
        self.assertEqual(preview.getpixel((6,6)),(0,80,44,37))
        self.assertEqual(preview.getpixel((7,7)),(80,0,44,37))

    def test_background_repair_is_confined_to_reviewed_cleanup(self):
        self.plan.update(erase_rects_xyxy=[[5,5,75,35]],background_repairs=[
            dict(xyxy=[0,0,2,2],source_xyxy=[0,0,2,2])])
        with self.assertRaisesRegex(ValueError,'exceeds cleanup'):
            m.render(parse(self.raw),[self.plan],self.font)

    def test_protected_artwork_rejects_text_overlap_not_silent_clipping(self):
        self.plan.update(protected_rects_xyxy=[self.plan['mask_xyxy']])
        with self.assertRaisesRegex(ValueError,'overlaps protected'):
            m.render(parse(self.raw),[self.plan],self.font)

    def test_background_donor_hash_and_path_are_guarded(self):
        for name,sha in [('fixture.bgr','0'*64),('../fixture.bgr',m.digest(self.raw))]:
            self.plan.update(erase_rects_xyxy=[[5,5,75,35]],background_repairs=[
                dict(xyxy=[6,6,8,8],source_xyxy=[0,0,2,2],resource=name,source_sha256=sha)])
            with self.assertRaises(ValueError):self.build()
            self.assertFalse(self.output.exists())

    def test_copy_geometry_and_policy_are_validated(self):
        for repair in [dict(xyxy=[6,6,8,8],source_xyxy=[0,0,3,3]),
                       dict(xyxy=[6,6,8,8],source_xyxy=[0,0,2,2],flip_y=1),
                       dict(xyxy=[6,6,8,8],mode='unknown')]:
            self.plan.update(erase_rects_xyxy=[[5,5,75,35]],background_repairs=[repair])
            with self.assertRaises(ValueError):m.render(parse(self.raw),[self.plan],self.font)

    def test_rotated_label_fits_mask_and_retains_headers(self):
        self.plan.update(target='Side',mask_xyxy=[5,5,25,35],rotation=90)
        r=self.build()
        self.assertEqual(r['resources'][0]['texts'][0]['rotation'],90)
        self.assertEqual(parse((self.output/'fixture.bgr').read_bytes()).header,parse(self.raw).header)

    def test_invalid_rotation_is_rejected(self):
        for rotation in [45,True,'90']:
            self.plan['rotation']=rotation
            with self.assertRaisesRegex(ValueError,'rotation'):self.build()

    def test_overlay_does_not_erase_the_background(self):
        self.plan['erase_mode']='overlay'
        image=parse(self.raw);changed,_,_=m.render(image,[self.plan],self.font)
        before,after=image.rgba(),parse(changed).rgba()
        # No text at the mask's upper-left corner: original pixel remains,
        # unlike a background reconstruction over the entire mask.
        i=(5*80+5)*4;self.assertEqual(before[i:i+4],after[i:i+4])

    def test_user_excluded_low_resolution_art_is_not_modified_by_plans(self):
        locale=Path(__file__).resolve().parents[1]/'locales/zh-CN'
        kept=json.loads((locale/'image-text-preserve.json').read_text(encoding='utf8'))
        names={r['resource'] for r in kept['resources']}
        self.assertEqual(len(names),24);self.assertEqual(kept['authority'],'direct_user_reply')
        modified={r['resource'] for r in json.loads((locale/'image-text-plans.json').read_text(encoding='utf8'))['resources']}
        modified.update(t['resource'] for g in json.loads((locale/'image-group-plans.json').read_text(encoding='utf8'))['groups'] for t in g['tiles'])
        self.assertFalse(names & modified)
        for r in kept['resources']:
            self.assertEqual(r['decision'],'preserve_original');self.assertFalse(r['counts_as_translation'])
            self.assertEqual(len(bytes.fromhex(r['source_sha256'])),32)


if __name__=='__main__':unittest.main()
