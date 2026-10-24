"""Native allocation evidence and reversible candidate delivery, not game acceptance."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import analyze_contact_audio_log as analysis
import build_audio_provider_update as package


def module(candidate=True):
    b = bytearray(512)
    b[:2] = b'MZ'
    struct.pack_into('<I', b, 60, 128)
    b[128:132] = b'PE\0\0'
    struct.pack_into('<H', b, 132, 0x14c)
    struct.pack_into('<H', b, 150, 0x2000)
    struct.pack_into('<H', b, 152, 0x10b)
    for offset, name in ((280, 'CONTACT_AUDIO_READY'), (360, 'AUDIO_PROVIDER_POLICY_READY' if candidate else 'baseline')):
        text = name.encode('utf-16le')
        b[offset:offset+len(text)] = text
    return bytes(b)


class AnalysisTests(unittest.TestCase):
    def test_full_pool_failure_is_observed_not_assumed(self):
        text = b'CONTACT_AUDIO_READY x=1\nCONTACT_AUDIO_SOUND snapshot_valid=1 state_after=0 channel_after=-1 slots_busy=8 slots_capacity=8\n'
        r = analysis.analyze(text)
        self.assertEqual((r['sound_starts'], r['allocation_failures'], r['full_pool_failures']), (1,1,1))
        self.assertFalse(r['rendered_picture_observed'])
        self.assertFalse(r['gameplay_fix_verified'])

    def test_invalid_snapshot_does_not_prove_failure(self):
        r = analysis.analyze(b'CONTACT_AUDIO_SOUND snapshot_valid=0 state_after=0 channel_after=-1 slots_busy=8 slots_capacity=8\n')
        self.assertEqual(r['allocation_failures'], 0)
        self.assertEqual(r['valid_sound_starts'], 0)

    def test_nonfull_failure_stays_distinct(self):
        r = analysis.analyze(b'CONTACT_AUDIO_SOUND snapshot_valid=1 state_after=0 channel_after=-1 slots_busy=7 slots_capacity=8\n')
        self.assertEqual((r['allocation_failures'], r['full_pool_failures']), (1,0))

    def test_save_crc_and_unsupported_inputs(self):
        b = bytearray(80)
        struct.pack_into('<I', b, 0, 4)
        struct.pack_into('<I', b, 22, 715)
        b += struct.pack('<I', zlib.crc32(b))
        r = analysis.analyze(b'', b)['save']
        self.assertTrue(r['checksum_valid'])
        self.assertEqual(r['field_id'], 715)
        b[35] ^= 1
        self.assertFalse(analysis.analyze(b'', b)['save']['checksum_valid'])
        b[0] = 3
        with self.assertRaises(ValueError): analysis.analyze(b'', b)
        with self.assertRaises(ValueError): analysis.analyze(b'', b'')

    def test_captured_report_when_locally_available(self):
        p = ROOT/'build/player-incident-20261024/inputs'
        if not (p/'profile.log').exists(): self.skipTest('Local player trace is not distributed')
        r = analysis.analyze((p/'profile.log').read_bytes(), (p/'MC01.sav').read_bytes())
        self.assertEqual(r['source_sha256'], '39a86b984c9051984ece8733c7f7ff22a9371c305d74ce0f63a7647429c7cc06')
        self.assertEqual((r['sound_starts'], r['allocation_failures'], r['full_pool_failures']), (1881,455,455))
        self.assertTrue(r['save']['checksum_valid'])
        self.assertEqual(r['save']['stored_crc32'], '9981b2f7')


class NativeTests(unittest.TestCase):
    def test_native_allocator_real_miles_and_byte_rollback(self):
        exe = ROOT/'build/native/Release/native_audio_pool_fixture.exe'
        engine, miles = ROOT/'runtime/data/MCAlpha.dll', ROOT/'runtime/data/mss32.dll'
        if not all(p.exists() for p in (exe, engine, miles)): self.skipTest('Local Win32 build and supported original audio required')
        for mode, code, expected in (('baseline',1,'capacity=8 requests=16 accepted=8 dropped=8'),
                ('modified',0,'capacity=56 requests=16 accepted=16 dropped=0'),
                ('fallback',0,'capacity=8 requests=16 accepted=8 dropped=8'),
                ('rollback',0,'capacity=8 requests=16 accepted=8 dropped=8')):
            with self.subTest(mode=mode):
                r = subprocess.run([str(exe),str(engine),str(miles),'--'+mode], capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, code, r.stdout+r.stderr)
                if mode=='modified' and 'preferred_available=false' in r.stdout:
                    self.assertIn('AUDIO_PROVIDER_POLICY_FALLBACK',r.stdout)
                    self.assertIn('capacity=8 requests=16 accepted=8 dropped=8',r.stdout)
                else:
                    self.assertIn(expected, r.stdout)
                self.assertIn('rollback=byte_exact', r.stdout)
                self.assertIn('game_started=false', r.stdout)

    def test_wrapper_scopes_flags_and_propagates_exit(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/package.ENTRY).write_bytes((ROOT/'assets/shared-runtime'/package.ENTRY).read_bytes())
            (p/'Play.cmd').write_text('@echo POLICY=%MC_AUDIO_PROVIDER_POLICY% TRACE=%MC_CONTACT_AUDIO_TRACE%\n@exit /b 7\n')
            (p/'driver.cmd').write_text('@echo off\nset MC_AUDIO_PROVIDER_POLICY=prior\nset MC_CONTACT_AUDIO_TRACE=old\ncall "%~dp0Play-audio-fix.cmd"\necho EXIT=%errorlevel% POLICY=%MC_AUDIO_PROVIDER_POLICY% TRACE=%MC_CONTACT_AUDIO_TRACE%\n')
            r = subprocess.run(['cmd.exe','/d','/c',str(p/'driver.cmd')],capture_output=True,text=True,timeout=10)
            self.assertIn('POLICY=1 TRACE=1',r.stdout)
            self.assertIn('EXIT=7 POLICY=prior TRACE=old',r.stdout)
        self.assertNotIn(b'MC_AUDIO_PROVIDER_POLICY',(ROOT/'src/configuration/StartShared.ps1').read_bytes())


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        old = {n:module(False) for n in package.MODULES}
        old['Play-contact-audio.cmd'] = b'@exit /b 0\r\n'
        runtime = dict(data_root='.',files={n:package.sha(b) for n,b in old.items()})
        old['runtime.json'] = json.dumps(runtime).encode()
        overlay = dict(kind='clean_game_overlay',files={n:package.sha(b) for n,b in old.items()},contact_audio_diagnostic=dict(module_sha256=package.sha(module(False))))
        old['Overlay-Manifest.json'] = json.dumps(overlay).encode()
        self.old = old
        self.previous = self.root/'observer.zip'
        with zipfile.ZipFile(self.previous,'x') as z:
            rows=[]
            for i,(n,b) in enumerate(old.items()):
                key=f'payload/{i:04d}.bin'
                z.writestr('Contact-Audio-Trace-20261024/'+key,b)
                rows.append(dict(path=n,after=package.sha(b),size=len(b),payload=key,payload_sha256=package.sha(b),delta=False))
            z.writestr('Contact-Audio-Trace-20261024/package.json',json.dumps(dict(diagnostic_only=True,files=rows)))
        self.native = self.root/'candidate.dll'
        self.native.write_bytes(module())

    def build(self, **options):
        args=dict(previous=self.previous,previous_sha256=package.sha(self.previous.read_bytes()),module=self.native,work=self.root/'work',output=self.root/'candidate.zip')
        args.update(options)
        return package.build(**args)

    def test_reject_wrong_package_hash_before_outputs(self):
        with self.assertRaises(ValueError): self.build(previous_sha256='0'*64)
        self.assertFalse((self.root/'work').exists())

    def test_reject_missing_candidate_marker(self):
        self.native.write_bytes(module(False))
        with self.assertRaises(ValueError): self.build()

    def test_package_only_owned_files_and_opt_in(self):
        result=self.build()
        with zipfile.ZipFile(result) as z:
            m=json.loads(z.read(package.FOLDER+'/package.json'))
            self.assertEqual({r['path'] for r in m['files']},set(package.FILES))
            self.assertEqual(len(m['files']),15)
            self.assertFalse(m['default_enabled'])
            self.assertFalse(m['in_game_verified'])
            self.assertIsNone(next(r for r in m['files'] if r['path']==package.ENTRY)['before'])

    def test_install_idempotence_independent_rollback_and_sentinels(self):
        result=self.build()
        extracted=self.root/'package'
        with zipfile.ZipFile(result) as z:z.extractall(extracted)
        target=self.root/'installed'
        for n,b in self.old.items():
            f=target/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
        sentinel=target/'Save/MC01.sav';sentinel.parent.mkdir();sentinel.write_bytes(b'owned-save-sentinel')
        settings=target/'settings.json';settings.write_bytes(b'owned-settings-sentinel')
        script=extracted/package.FOLDER/'Update.ps1'
        def run(action,folder):
            r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Action',action,'-Runtime',str(folder)],capture_output=True,text=True,timeout=40)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            return r.stdout
        run('Verify',target)
        self.assertIn('MODIFIED PASS files=15',run('Install',target))
        run('Install',target)
        run('CheckInstalled',target)
        independent=self.root/'rollback-copy'
        shutil.copytree(target,independent)
        run('Rollback',independent)
        for n,b in self.old.items():self.assertEqual((independent/n).read_bytes(),b)
        self.assertFalse((independent/package.ENTRY).exists())
        self.assertEqual(sentinel.read_bytes(),b'owned-save-sentinel')
        self.assertEqual(settings.read_bytes(),b'owned-settings-sentinel')
        self.assertEqual((independent/'Save/MC01.sav').read_bytes(),b'owned-save-sentinel')
        self.assertTrue((target/package.ENTRY).exists())
