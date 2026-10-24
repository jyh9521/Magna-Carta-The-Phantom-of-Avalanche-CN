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
 def test_real_import_slot_calls_and_rollback(self):
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
