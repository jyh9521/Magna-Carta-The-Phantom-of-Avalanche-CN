import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import locale_package as m
class DeltaTests(unittest.TestCase):
    def test_roundtrip_empty_longer_shorter_and_matching_blocks(self):
        for a,b in [(b'',b''),(b'a',b'xyz'),(b'abc',b'x'),(b'A'*300,b'A'*128+b'Z'*64+b'A'*108)]:
            self.assertEqual(m.undelta(a,m.delta(a,b),len(b)),b)
    def test_corruption_and_target_size_are_rejected(self):
        p=m.delta(b'old',b'new')
        for bad in [p[:-1],b'bad'+p,p+b'junk']:
            with self.assertRaises(ValueError):m.undelta(b'old',bad,3)
        with self.assertRaises(ValueError):m.undelta(b'old',p,4)
    def test_noncanonical_paths_are_rejected(self):
        for n in ['../a','C:/a','a\\b','/a','./a','a/../b','']:
            with self.assertRaises(ValueError):m.canonical(n)
class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.source=self.root/'source';self.source.mkdir();self.candidate=self.root/'candidate';self.candidate.mkdir()
        self.before=b'A'*150;self.after=b'A'*64+b'localized'+b'A'*70
        for n,b in [('MagnaCarta.exe',b'controlled exe'),('MCAlpha.dll',b'controlled module'),('field.bin',self.before),('staff.pak',b'original staff'),('save.bin',b'unchanged save')]: (self.source/n).write_bytes(b)
        (self.candidate/'field.bin').write_bytes(self.after)
        (self.candidate/'build.json').write_text(json.dumps(dict(source_unchanged=True,game_started=False,resources=[dict(resource='field.bin',modified_sha256=m.sha(self.after))])),encoding='utf8')
        self.runtime=self.root/'runtime';self.runtime.mkdir()
        for n in ['workspace_profile.dll','workspace_launcher.exe']:(self.runtime/n).write_bytes(b'controlled runtime')
        self.scope=self.root/'scope.json';self.scope.write_text(json.dumps(dict(old_save_name_adaptation=dict(decision='excluded'),staff_credits=dict(whole_resource_preserved=True,resource='staff.pak',source_sha256=m.sha(b'original staff')),preserved_art_manifest='art.json')),encoding='utf8')
        (self.root/'art.json').write_text(json.dumps(dict(resources=[])),encoding='utf8');self.package=self.root/'package'
    def build(self):return m.build(self.source,[self.candidate],self.runtime,self.scope,self.package)
    def test_apply_and_rollback_never_change_source_or_saves(self):
        self.build();target=self.root/'copy';m.apply(self.package,self.source,target)
        self.assertEqual((target/'field.bin').read_bytes(),self.after);self.assertEqual((target/'save.bin').read_bytes(),b'unchanged save')
        m.rollback(self.package,self.source,target)
        self.assertEqual((target/'field.bin').read_bytes(),self.before);self.assertEqual((self.source/'field.bin').read_bytes(),self.before)
        self.assertEqual((target/'staff.pak').read_bytes(),b'original staff')
    def test_modified_or_unknown_source_refuses_before_copy(self):
        self.build();(self.source/'field.bin').write_bytes(b'unknown');target=self.root/'copy'
        with self.assertRaises(ValueError):m.apply(self.package,self.source,target)
        self.assertFalse(target.exists())
    def test_rollback_modified_copy_drift_refuses_all_writes(self):
        self.build();target=self.root/'copy';m.apply(self.package,self.source,target);(target/'field.bin').write_bytes(b'user edit')
        with self.assertRaises(ValueError):m.rollback(self.package,self.source,target)
        self.assertEqual((target/'field.bin').read_bytes(),b'user edit')
    def test_overlapping_candidates_and_existing_targets_refuse(self):
        with self.assertRaises(ValueError):m.build(self.source,[self.candidate,self.candidate],self.runtime,self.scope,self.package)
        self.assertFalse(self.package.exists());self.build()
        with self.assertRaises(ValueError):m.apply(self.package,self.source,self.source)
    def test_corrupted_candidate_is_not_silently_repackaged(self):
        (self.candidate/'field.bin').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'verified build manifest'):self.build()
        self.assertFalse(self.package.exists())
if __name__=='__main__':unittest.main()
