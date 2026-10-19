"""Source locks, owned native/GPU fixture, reversible controls and VerifyOnly; no game launch."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import integrate_scaled_font as tool
from build_scaled_font_coverage import cache_bytes
import test_configuration_verify_transaction as routes

ROOT=Path(__file__).resolve().parents[1]


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='owned-scaled-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.runtime=self.root/'runtime';self.runtime.mkdir();(self.runtime/'modules').mkdir()
        self.cache=self.root/'cache';self.cache.mkdir();self.record=self.root/'record'
        start=b'owned baseline';(self.runtime/'Start.ps1').write_bytes(start)
        (self.runtime/'Play.cmd').write_bytes(b'owned original entry')
        (self.runtime/'modules/native-loading.dll').write_bytes(b'owned existing module')
        (self.runtime/'save.sav').write_bytes(b'owned save');(self.runtime/'settings.json').write_bytes(b'owned settings')
        self.manifest=dict(schema=1,files={p:tool.digest((self.runtime/p).read_bytes()) for p in ('Start.ps1','Play.cmd','modules/native-loading.dll')},native_scene_loading=dict(schema=1,enabled=True,module='native-loading'))
        (self.runtime/'runtime.json').write_text(json.dumps(self.manifest),encoding='utf8')
        m=dict(schema=1,scale=4,glyphs=1,files={})
        for h in (14,22):
            name=f'candidate-{h}.sgc';b=cache_bytes(h,4,[0xca40],bytes((h*4)**2));(self.cache/name).write_bytes(b);m['files'][name]=tool.digest(b)
        (self.cache/'FONT-LICENSE.txt').write_bytes(b'owned license');m['files']['FONT-LICENSE.txt']=tool.digest(b'owned license')
        (self.cache/'manifest.json').write_text(json.dumps(m),encoding='utf8')
        self.module=self.root/'candidate.dll';self.module.write_bytes(b'MZ'+bytes(64)+''.join(m['files'][f'candidate-{h}.sgc'] for h in (14,22)).encode())
        guard=patch.object(tool,'BASE_START_SHA',tool.digest(start));guard.start();self.addCleanup(guard.stop)
        self.before=self.snapshot()
    def snapshot(self):return {p.relative_to(self.runtime).as_posix():p.read_bytes() for p in self.runtime.rglob('*') if p.is_file()}
    def install(self):return tool.integrate(self.runtime,self.module,self.cache,self.record)
    def test_apply_rollback_preserves_every_other_file(self):
        self.install();m=json.loads((self.runtime/'runtime.json').read_bytes());self.assertEqual(m['scaled_font'],dict(schema=1,enabled=True,module='scaled-font',scale=4))
        for p,b in self.before.items():
            if p not in ('Start.ps1','runtime.json'):self.assertEqual((self.runtime/p).read_bytes(),b)
        tool.rollback(self.record);self.assertEqual(self.snapshot(),self.before)
    def test_reentry_and_unknown_baseline(self):
        with patch.object(tool,'BASE_START_SHA','0'*64),self.assertRaises(ValueError):self.install()
        self.assertEqual(self.snapshot(),self.before);self.install();now=self.snapshot()
        with self.assertRaises(ValueError):tool.integrate(self.runtime,self.module,self.cache,self.root/'second')
        self.assertEqual(self.snapshot(),now)
    def test_cache_hash_drift(self):
        (self.cache/'candidate-14.sgc').write_bytes(b'drift')
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(self.snapshot(),self.before)
    def test_wrong_module_binding(self):
        self.module.write_bytes(b'MZ'+bytes(80))
        with self.assertRaisesRegex(ValueError,'binding mismatch'):self.install()
        self.assertEqual(self.snapshot(),self.before)
    def test_wrong_scale_and_mapping(self):
        m=json.loads((self.cache/'manifest.json').read_bytes());m['scale']=1;(self.cache/'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValueError):tool.payload(self.cache)
    def test_backup_and_installed_drift(self):
        self.install();(self.record/'original/Start.ps1').write_bytes(b'drift');now=self.snapshot()
        with self.assertRaises(ValueError):tool.rollback(self.record)
        self.assertEqual(self.snapshot(),now)
    def test_foreign_installed_file_preserved(self):
        self.install();(self.runtime/'fonts/candidate-22.sgc').write_bytes(b'foreign');now=self.snapshot()
        with self.assertRaises(ValueError):tool.rollback(self.record)
        self.assertEqual(self.snapshot(),now)
    def test_partial_write_compensates(self):
        real=tool.write_file
        def fail(p,b):
            if p==self.runtime/'Start.ps1':raise OSError('owned failure')
            real(p,b)
        with patch.object(tool,'write_file',side_effect=fail),self.assertRaises(OSError):self.install()
        self.assertEqual(self.snapshot(),self.before)
    def test_header_is_deterministic_and_exclusive(self):
        a=self.root/'a.h';b=self.root/'b.h';tool.header(self.cache,a);tool.header(self.cache,b);self.assertEqual(a.read_bytes(),b.read_bytes())
        with self.assertRaises(ValueError):tool.header(self.cache,a)
    def test_package_metadata_and_rebuild_dependency(self):
        import build_player_test_bundle as bundle
        from prepare_shared_runtime import prepare
        self.install();m=json.loads((self.runtime/'runtime.json').read_bytes())
        for k in ('field_return_height','gui_parent_guard'):
            n=k.replace('_','-');m[k]=dict(schema=1,enabled=True,module=n);m['files']['modules/'+n+'.dll']='owned'
        r=bundle.validate_engine_fixes(self.runtime,m)
        self.assertTrue(r['scaled_font']['default_enabled']);self.assertFalse(r['scaled_font']['in_game_verified'])
        m['scaled_font']['scale']=1
        with self.assertRaises(ValueError):bundle.validate_engine_fixes(self.runtime,m)
        for modules,cache in [({'scaled-font':self.module},None),({},self.cache)]:
            with self.assertRaises(ValueError):prepare(self.root/'missing',modules,self.root/'atlas',self.root/'output',cache)
            self.assertFalse((self.root/'output').exists())


class NativeTests(unittest.TestCase):
    def test_actual_source_calls_and_unchanged_draw_path(self):
        source=ROOT/'runtime/data/MCAlpha.dll'
        if not source.exists():self.skipTest('local sample required')
        import pefile
        raw=source.read_bytes();contract=json.loads((ROOT/'assets/runtime/scaled-font-contract.json').read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),contract['engine_sha256']);p=pefile.PE(data=raw)
        for c in contract['calls']:
            self.assertEqual(p.get_data(c['rva']-8,21).hex(),c['context_hex'])
            self.assertEqual(c['rva']+5+struct.unpack('<i',p.get_data(c['rva']+1,4))[0],c['target'])
        self.assertEqual(hashlib.sha256((ROOT/'runtime/data/Drv/AsrD3DDrv.dll').read_bytes()).hexdigest(),contract['driver_sha256'])
    def test_native_gpu_three_states(self):
        fixture=ROOT/'build/native/Release/scaled_font_runtime_fixture.exe';cache=ROOT/'build/scaled-font-evidence/cache'
        if not fixture.exists() or not cache.exists():self.skipTest('build native fixture/cache first')
        for mode,n in [('baseline',0),('modified',40),('rollback',0)]:
            p=subprocess.run([str(fixture),mode,str(ROOT/'runtime/data/Drv/AsrD3DDrv.dll'),str(ROOT/'runtime/data/ddraw.dll'),str(cache)],capture_output=True,text=True,timeout=60)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertIn(f'cases=24 hd_textures={n}',p.stdout)
            self.assertIn('game_started=false',p.stdout);self.assertIn('instructions=restored',p.stdout)


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):routes.SharedVerifyIntegrationTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):routes.SharedVerifyIntegrationTests.tearDownClass.__func__(cls)
    fixture=routes.SharedVerifyIntegrationTests.fixture
    def test_play_optout_baseline_and_parent_environment(self):
        for recipe,flags,enabled,module in [('configured',[],1,'scaled-font'),('configured',['-WithoutScaledFont'],0,'native-loading'),('configured',['-WithoutNativeLoading'],1,'scaled-font'),('baseline',[],0,'display')]:
            for fail in (False,True):
                with self.subTest(recipe=recipe,flags=flags,fail=fail),tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
                    r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes())
                    m['recipes']['baseline']=dict(module='display',settings=dict(schema=1,display_profile='baseline',motion60=False,native_gamepad=False))
                    m['native_scene_loading']=dict(schema=1,enabled=True,module='native-loading');m['gui_parent_guard']=dict(schema=1,enabled=True,module='gui-parent-guard')
                    m['scaled_font']=dict(schema=1,enabled=True,module='scaled-font',scale=4);(r/'runtime.json').write_text(json.dumps(m))
                    capture=r/'capture.txt';env=os.environ.copy();env['OWNED_CAPTURE_FILE']=str(capture);env['OWNED_VERIFY_EXIT']='7' if fail else '0'
                    cmd="$env:MC_SCALED_FONT='parent';$env:MC_SCALED_FONT_ASSETS='parent-assets';try{& '"+str(r/'Start.ps1')+"' -VerifyOnly -Recipe "+recipe+' '+' '.join(flags)+";if("+('$true' if fail else '$false')+"){throw 'expected failure'}}catch{if("+('$false' if fail else '$true')+"){throw};if($_ -notmatch 'Shared launcher exit=7'){throw}};if($env:MC_SCALED_FONT -ne 'parent' -or $env:MC_SCALED_FONT_ASSETS -ne 'parent-assets'){throw 'env drift'};exit 0"
                    p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],env=env,capture_output=True,text=True,timeout=30)
                    self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                    actual=capture.read_text();self.assertIn('MC_SCALED_FONT='+str(enabled),actual);self.assertIn(module+'.dll',actual)
                    self.assertEqual((r/'data/DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned baseline\r\n')
    def test_invalid_metadata_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes());m['scaled_font']=dict(schema=1,enabled='true',module='scaled-font',scale=4);(r/'runtime.json').write_text(json.dumps(m))
            p=subprocess.run(['powershell.exe','-NoProfile','-File',str(r/'Start.ps1'),'-VerifyOnly'],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(p.returncode,0);self.assertIn('Invalid scaled font integration',p.stderr)
