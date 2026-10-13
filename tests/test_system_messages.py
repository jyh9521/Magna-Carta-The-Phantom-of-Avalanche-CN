import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_system_messages as m
class SystemMessageBuildTests(unittest.TestCase):
    def setUp(self):
        self.raw=b'HEADER\0%d issue %s\0END'
        self.row=dict(offset=7,expected_hex=b'%d issue %s'.hex(),target='%d: %s',evidence='controlled system message')
        self.plan=dict(schema=1,source_sha256=m.sha(self.raw),source_size=len(self.raw),source_encoding='cp949',code_page=949,fields=[self.row],envelopes=[],captions=[])
    def test_formats_and_source_identity(self):
        self.assertEqual(m.compile_rules(self.raw,self.plan),{'%d issue %s':'%d: %s'})
        for key,value in [('source_sha256','0'*64),('source_size',0),('code_page',1252)]:
            p=copy.deepcopy(self.plan);p[key]=value
            with self.assertRaises(ValueError):m.compile_rules(self.raw,p)
    def test_expected_bytes_offsets_and_placeholders(self):
        for key,value in [('offset',True),('offset',-1),('expected_hex','00'),('target','%s %d'),('target','%x'),('evidence','')]:
            p=copy.deepcopy(self.plan);p['fields'][0][key]=value
            with self.assertRaises(ValueError):m.compile_rules(self.raw,p)
    def test_duplicate_offsets_are_rejected(self):
        self.plan['fields'].append(copy.deepcopy(self.row))
        with self.assertRaises(ValueError):m.compile_rules(self.raw,self.plan)
    def test_build_is_reproducible_and_never_changes_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'module';source.write_bytes(self.raw);plans=p/'plans';plans.write_text(json.dumps(self.plan),encoding='utf8')
            for n in ['one','two']:m.build(source,plans,p/n)
            self.assertEqual((p/'one/system_message_rules.h').read_bytes(),(p/'two/system_message_rules.h').read_bytes())
            self.assertEqual(source.read_bytes(),self.raw)
            with self.assertRaises(ValueError):m.build(source,plans,p/'one')
    def test_repository_has_nine_fields_six_linked_messages(self):
        p=json.loads((Path(__file__).resolve().parents[1]/'locales/zh-CN/system-message-plans.json').read_text(encoding='utf8'))
        self.assertEqual(len(p['fields']),9)
        self.assertEqual(len({r['expected_hex'] for r in p['fields']}),6)
        for r in p['fields']:
            self.assertEqual(m.TOKENS.findall(bytes.fromhex(r['expected_hex']).decode('cp949')),m.TOKENS.findall(r['target']))
    def test_candidate_requires_declared_patch_and_matching_font(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'module';source.write_bytes(self.raw);plans=p/'plans';plans.write_text(json.dumps(self.plan),encoding='utf8');candidate=p/'candidate';candidate.write_bytes(self.raw)
            with self.assertRaisesRegex(ValueError,'requires verified'):m.build(source,plans,p/'out',candidate)
            self.assertFalse((p/'out').exists())
    def test_scope_excludes_old_names_and_staff_movie(self):
        root=Path(__file__).resolve().parents[1]/'locales/zh-CN'
        scope=json.loads((root/'scope-decisions.json').read_text(encoding='utf8'))
        self.assertEqual(scope['old_save_name_adaptation']['decision'],'excluded')
        self.assertTrue(scope['staff_credits']['whole_resource_preserved'])
        self.assertTrue(scope['opening_brand_logo']['whole_resource_preserved'])
        self.assertEqual(scope['opening_brand_logo']['resource'],'MOV/0023.BMC')
        movies=json.loads((root/'video-text-plans.json').read_text(encoding='utf8'))['videos']
        self.assertFalse(any(r['resource'] in ['MOV/MOV.pak','MOV/0023.BMC'] for r in movies))
if __name__=='__main__':unittest.main()
