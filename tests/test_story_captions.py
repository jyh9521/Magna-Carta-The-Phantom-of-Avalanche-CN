"""All-resource caption audit and native render/audio lifecycle regressions."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_story_captions as captions

class StoryCaptionsTests(unittest.TestCase):
 def run_fixture(self,name,*args):
  p=ROOT/'build/native/Release'/name
  if not p.exists():self.skipTest('Build owned Win32 fixture first')
  q=subprocess.run([str(p),*map(str,args)],capture_output=True,text=True,timeout=30)
  self.assertEqual(q.returncode,0,q.stdout+q.stderr);return q.stdout
 def test_final_frame_cold_start_and_active_d3d_scene(self):
  self.assertIn('cold_F5=first_frame caption=above_curtain',self.run_fixture('frame_overlay_fixture.exe'))
 def test_audio_lifecycle_and_source_identity(self):
  self.assertIn('pause=held restart=reset skip=cleared scene_frame=guarded',self.run_fixture('story_captions_fixture.exe',ROOT/'build/native/owned_audio_clock/Release/Mss32.dll'))
 def test_visible_native_dialogue_over_curtain_is_not_duplicated(self):
  self.assertIn('SUBTITLE_DEDUP PASS visible_native=priority curtain_slots=4 opacity_cases=4 hidden_box=retained visibility_transition=immediate',self.run_fixture('story_captions_fixture.exe'))
 def test_real_import_slot_calls_and_rollback(self):
  if not (ROOT/'build/native/Release/sample_clock_fixture.exe').is_file():
   self.skipTest('Build owned sample_clock_fixture first')
  api=ROOT/'build/native/owned_audio_clock/Release/Mss32.dll'
  self.assertTrue(api.exists())
  self.assertIn('SAMPLE_CLOCK_IAT PASS',self.run_fixture('sample_clock_fixture.exe',api))
 def test_cg_reused_model_position_and_height(self):
  p=ROOT/'build/native/Release/rigid_motion_fixture.exe'
  if not p.exists():self.skipTest('Build owned fixture first')
  old=subprocess.run([str(p),'--scene-cut-baseline'],capture_output=True,text=True,timeout=30)
  self.assertEqual(old.returncode,1);self.assertIn('CG_cut_must_not_replay_old_scene_position',old.stdout)
  self.assertIn('body_part_height=exact held_frame=stable render60=retained',self.run_fixture('rigid_motion_fixture.exe','--scene-cut'))
 def test_all_field_audio_resources_and_existing_dialogues(self):
  if not (ROOT/'runtime/data/Field').is_dir():self.skipTest('Local source resources required')
  with tempfile.TemporaryDirectory() as t:
   r=captions.compile(ROOT/'locales/zh-CN/story-captions.json',ROOT/'runtime/data',Path(t)/'data.h',None)
  self.assertEqual(r['fields_scanned'],597);self.assertEqual(r['resources'],48);self.assertEqual(r['voice_only_commands'].__len__(),67)
  self.assertEqual(r['missing_translations'],[]);self.assertTrue(r['audio_hashes_verified']);self.assertGreater(r['normal_dialogue_bindings'],2000)
 def test_actual_miles_stream_pause_and_caption_identity(self):
  exe=ROOT/'build/native/Release/dialogue_voice_chain_fixture.exe'
  voice=ROOT/'runtime/data/SVD/1344.SVD';fpb=ROOT/'runtime/data/Fpb/0233.fpb'
  if not exe.exists() or not voice.exists():self.skipTest('Local source and owned native fixture required')
  import hashlib
  from audit_dialogue_resources import parse_sound
  data=voice.read_bytes()
  with tempfile.TemporaryDirectory() as temp:
   audio=Path(temp)/'voice.mp3';audio.write_bytes(data[parse_sound(data)['header_bytes']:])
   args=[exe,'--dll',ROOT/'runtime/data/Mss32.dll','--audio',audio,'--native-engine',ROOT/'runtime/data/MCAlpha.dll','--fpb',fpb,'--tag','7','--tail-ms','1400','--expected-audio-sha256',hashlib.sha256(audio.read_bytes()).hexdigest(),'--expected-fpb-sha256',hashlib.sha256(fpb.read_bytes()).hexdigest()]
   q=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=40)
  self.assertEqual(q.returncode,0,q.stdout+q.stderr);self.assertIn('paused_cursor=frozen long_pause=held completed_caption=cleared',q.stdout)
 def test_opening_and_full_ending_in_catalog(self):
  c=captions.read_catalog(ROOT/'locales/zh-CN/story-captions.json');d={r['id']:r for r in c['resources']}
  self.assertTrue(all(d[n]['kind']=='speech' and d[n]['cues'] for n in range(470,480)))
  self.assertIn('自治权',''.join(x['target'] for x in d[476]['cues']))
 def test_test_package_frame_rate_is_explicit_and_bounded(self):
  import build_clean_overlay as overlay
  with self.assertRaises(ValueError):overlay.build(Path('no-source'),'',Path('no-runtime'),Path('no-output'),frame_rate=61)
  q=subprocess.run([sys.executable,str(ROOT/'tools/build_clean_overlay.py'),'--help'],capture_output=True,text=True)
  self.assertEqual(q.returncode,0);self.assertIn('--frame-rate {30,60}',q.stdout)
 def test_all_ordinary_bindings_native_visibility_matrix(self):
  import struct
  from resource_field_script import parse
  if not (ROOT/'runtime/data/Field').exists():self.skipTest('Local Field resources required')
  records=[]
  texts={}
  for p in (ROOT/'locales/zh-CN/text').glob('*.json'):
   for r in json.loads(p.read_text('utf8')):
    if isinstance(r,dict) and r.get('target') and r.get('id','').startswith('Fpb/'):
     a=r['id'].split(':');texts[(int(a[0][4:8]),int(a[-1]))]=r['target'].replace('$n','\n')
  for path in (ROOT/'runtime/data/Field').glob('*.fld'):
   try:field=parse(path.read_bytes())
   except ValueError:continue
   for event in field['events']:
    for action in event['actions']:
     if action['opcode'] in (700,704) and action['parameters'][7]>=0:
      text=texts[(field['playbook_id'],action['parameters'][6])].encode('utf-16le');records.append(struct.pack('<16iI',int(path.stem),action['opcode'],*action['parameters'],len(text))+text)
  self.assertEqual(len(records),2374)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'matrix.bin';p.write_bytes(b'SCM1'+struct.pack('<I',len(records))+b''.join(records))
   self.assertIn('SUBTITLE_MATRIX PASS bindings=2374 cases=109204',self.run_fixture('story_captions_fixture.exe','--matrix',p))
 def test_native_dialogue_and_choices_have_global_priority(self):
  self.assertIn('SUBTITLE_ARBITRATION PASS native700_701_704_705=priority choices=priority',self.run_fixture('story_captions_fixture.exe'))
 def test_all_standalone_speech_bindings_full_cue_lifetime(self):
  import struct
  from resource_field_script import parse
  catalog=captions.read_catalog(ROOT/'locales/zh-CN/story-captions.json');speech={r['id']:r for r in catalog['resources'] if r['kind']=='speech'};records=[]
  for p in (ROOT/'runtime/data/Field').glob('*.fld'):
   try:field=parse(p.read_bytes())
   except ValueError:continue
   for event in field['events']:
    for action in event['actions']:
     if action['opcode']!=603 or action['parameters'][0] not in speech:continue
     cues=speech[action['parameters'][0]]['cues'];data=struct.pack('<16iI',int(p.stem),603,*action['parameters'],len(cues))
     for cue in cues:
      text=cue['target'].encode('utf-16le');data+=struct.pack('<III',cue['start_ms'],cue['end_ms'],len(text))+text
     records.append(data)
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'voice.bin';p.write_bytes(b'SCV1'+struct.pack('<I',len(records))+b''.join(records))
   self.assertIn('start_mid_tail=exact final_pause=held end_skip=cleared',self.run_fixture('story_captions_fixture.exe','--voice-matrix',p))
 def test_removing_any_reviewed_phrase_is_rejected(self):
  catalog=json.loads((ROOT/'locales/zh-CN/story-captions.json').read_text('utf8'))
  for row in catalog['resources']:
   if row['kind']!='speech':continue
   for index in range(len(row['cues'])):
    c=copy.deepcopy(catalog);r=next(r for r in c['resources'] if r['id']==row['id']);del r['cues'][index]
    with tempfile.TemporaryDirectory() as t:
     p=Path(t)/'catalog.json';p.write_text(json.dumps(c))
     with self.assertRaises(ValueError):captions.read_catalog(p)
 def test_reviewed_tail_time_cannot_be_cropped(self):
  c=json.loads((ROOT/'locales/zh-CN/story-captions.json').read_text('utf8'));r=next(r for r in c['resources'] if r['id']==472);r['cues'][-1]['end_ms']=5000
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'catalog.json';p.write_text(json.dumps(c))
   with self.assertRaisesRegex(ValueError,'Uncovered reviewed speech'):captions.read_catalog(p)
 def test_complete_installed_dialogue_bytes_are_checked(self):
  from audit_story_caption_coverage import bind_private_text
  mapping={};bind_private_text(b'\xca\x40$nA','字$nA',mapping)
  self.assertEqual(mapping,{'字':b'\xca\x40'})
  for raw in [b'\xca\x40$n',b'\xca\x40$nAB',b'\xca\x40$nB']:
   with self.assertRaises(ValueError):bind_private_text(raw,'字$nA',mapping)
 def test_approved_reference_validator_rejects_suffix_loss(self):
  c=captions.read_catalog(ROOT/'locales/zh-CN/story-captions.json')
  texts={r['id']:r['target'] for p in (ROOT/'locales/zh-CN/text').glob('*.json') for r in json.loads(p.read_text('utf8')) if isinstance(r,dict) and r.get('target')}
  self.assertEqual(captions.validate_approved(c,texts),8)
  r=next(r for r in c['resources'] if r['id']==472);r['cues'].pop()
  with self.assertRaisesRegex(ValueError,'Truncated approved translation'):captions.validate_approved(c,texts)
 def test_existing_translation_is_not_truncated(self):
  c=captions.read_catalog(ROOT/'locales/zh-CN/story-captions.json')
  texts={r['id']:r['target'] for p in (ROOT/'locales/zh-CN/text').glob('*.json') for r in json.loads(p.read_text('utf8')) if isinstance(r,dict) and r.get('target')}
  normalized=lambda s:''.join(x for x in s if x.isalnum())
  for r in c['resources']:
   ref=r.get('existing_translation_reference')
   if ref:self.assertEqual(normalized(''.join(q['target'] for q in r['cues'])),normalized(texts[ref]),'Truncated approved translation: '+str(r['id']))
 def test_missing_translation_and_out_of_audio_range_rejected(self):
  c=json.loads((ROOT/'locales/zh-CN/story-captions.json').read_text('utf8'));r=next(x for x in c['resources'] if x['kind']=='speech')
  for mutation in ['empty','range']:
   q=copy.deepcopy(c);s=next(x for x in q['resources'] if x['id']==r['id'])
   if mutation=='empty':s['cues'][0]['target']=''
   else:s['cues'][0]['end_ms']=s['duration_ms']+1
   with tempfile.TemporaryDirectory() as t:
    p=Path(t)/'catalog.json';p.write_text(json.dumps(q))
    with self.assertRaises(ValueError):captions.read_catalog(p)
if __name__=='__main__':unittest.main()
