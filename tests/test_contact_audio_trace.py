"""Optional observer ABI and installer tests, not gameplay acceptance."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_contact_audio_update as package


def module(marker=False):
    b=bytearray(512);b[:2]=b'MZ';struct.pack_into('<I',b,60,128)
    b[128:132]=b'PE\0\0';struct.pack_into('<H',b,132,0x14c)
    struct.pack_into('<H',b,150,0x2000);struct.pack_into('<H',b,152,0x10b)
    if marker:
        text='CONTACT_AUDIO_READY'.encode('utf-16le');b[300:300+len(text)]=text
    return bytes(b)


class ContactAudioTraceTests(unittest.TestCase):
    def test_owned_native_abi_pass_and_uninstrumented_baseline(self):
        exe=ROOT/'build/native/Release/contact_audio_trace_fixture.exe'
        if not exe.exists():
            self.skipTest('Build owned Win32 contact_audio_trace_fixture')
        baseline=subprocess.run([str(exe),'--baseline'],capture_output=True,text=True,timeout=20)
        self.assertEqual(baseline.returncode,1,baseline.stdout+baseline.stderr)
        self.assertIn('observation=absent physics_audio_passthrough=true',baseline.stdout)
        result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        for part in ('abi=exact','results=unchanged','last_error=preserved',
                     'rollback=byte_exact','commercial_code_executed=false'):
            self.assertIn(part,result.stdout)

    def test_normal_entry_does_not_enable_trace(self):
        self.assertNotIn(b'MC_CONTACT_AUDIO_TRACE',(ROOT/'src/configuration/StartShared.ps1').read_bytes())
        source=(ROOT/'src/runtime/workspace_profile.cpp').read_text('utf-8')
        self.assertIn('GetEnvironmentVariableW(L"MC_CONTACT_AUDIO_TRACE",contactAudioFlag,8)==1',source)
        self.assertIn("contactAudioFlag[0]==L'1'",source)

    def test_wrapper_scopes_environment_and_preserves_play_exit_status(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'Play-contact-audio.cmd').write_bytes((ROOT/'assets/shared-runtime/Play-contact-audio.cmd').read_bytes())
            (r/'Play.cmd').write_text('@if not "%MC_CONTACT_AUDIO_TRACE%"=="1" exit /b 9\n@exit /b 7\n')
            driver=r/'driver.cmd';driver.write_text('@echo off\nset MC_CONTACT_AUDIO_TRACE=previous\ncall "%~dp0Play-contact-audio.cmd"\nset RC=%ERRORLEVEL%\necho RESULT=%RC% ENV=%MC_CONTACT_AUDIO_TRACE%\n')
            p=subprocess.run(['cmd.exe','/d','/c',str(driver)],capture_output=True,text=True,timeout=15)
            self.assertIn('RESULT=7 ENV=previous',p.stdout,p.stdout+p.stderr)


class ContactAudioPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.old={n:module() for n in package.MODULES}
        runtime=dict(schema=1,data_root='.',files={n:package.sha(b) for n,b in self.old.items()},data={},recipes={})
        self.old['runtime.json']=(json.dumps(runtime)+'\n').encode()
        overlay=dict(kind='clean_game_overlay',files={n:package.sha(b) for n,b in self.old.items()})
        self.old['Overlay-Manifest.json']=json.dumps(overlay).encode()
        self.previous=self.root/'previous.zip'
        with zipfile.ZipFile(self.previous,'x') as z:
            for n,b in self.old.items():z.writestr(n,b)
        self.native=self.root/'observer.dll';self.native.write_bytes(module(True))

    def build(self,**options):
        args=dict(previous=self.previous,module=self.native,work=self.root/'work',
            output=self.root/'update.zip',previous_sha256=package.sha(self.previous.read_bytes()))
        args.update(options);return package.build(**args)

    def installed_fixture(self):
        archive=self.build();r=self.root/'runtime';r.mkdir()
        for n,b in self.old.items():
            f=r/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
        with zipfile.ZipFile(archive) as z:z.extractall(r)
        (r/'MC00.sav').write_bytes(b'owned save sentinel')
        (r/'config').mkdir();(r/'config/enhancements.json').write_bytes(b'owned mutable settings')
        return r

    def action(self,r,action,success=True):
        p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass',
            '-File',str(r/package.FOLDER/'Update.ps1'),'-Runtime',str(r),'-Action',action],
            capture_output=True,text=True,timeout=40)
        self.assertEqual(p.returncode==0,success,p.stdout+p.stderr)
        return p.stdout

    def test_real_powershell_install_repeat_rollback_and_reinstall(self):
        r=self.installed_fixture()
        self.assertIn('BASELINE PASS files=15 writes=0',self.action(r,'Verify'))
        self.assertFalse((r/package.ENTRY).exists())
        for action in ('Install','CheckInstalled','Install'):
            self.assertIn('MODIFIED PASS files=15',self.action(r,action))
        self.assertEqual((r/package.ENTRY).read_bytes(),(ROOT/'assets/shared-runtime'/package.ENTRY).read_bytes())
        self.assertIn('ROLLBACK PASS files=15 original_hashes=exact',self.action(r,'Rollback'))
        for n,b in self.old.items():self.assertEqual((r/n).read_bytes(),b)
        self.assertFalse((r/package.ENTRY).exists())
        self.action(r,'Install')
        self.assertEqual((r/'MC00.sav').read_bytes(),b'owned save sentinel')
        self.assertEqual((r/'config/enhancements.json').read_bytes(),b'owned mutable settings')

    def test_mixed_version_rejection_has_zero_writes(self):
        r=self.installed_fixture();f=r/package.MODULES[-1];f.write_bytes(b'owned drift')
        before={str(p.relative_to(r)):p.read_bytes() for p in r.rglob('*') if p.is_file()}
        self.action(r,'Install',False)
        self.assertEqual(before,{str(p.relative_to(r)):p.read_bytes() for p in r.rglob('*') if p.is_file()})

    def test_source_hash_and_missing_observer_fail_before_output(self):
        with self.assertRaises(ValueError):self.build(previous_sha256='0'*64)
        self.assertFalse((self.root/'work').exists())
        self.native.write_bytes(module(False))
        with self.assertRaises(ValueError):self.build()
        self.assertFalse((self.root/'work').exists())

    def test_payload_is_owned_files_only_and_deduplicated(self):
        archive=self.build()
        with zipfile.ZipFile(archive) as z:
            m=json.loads(z.read(package.FOLDER+'/package.json'))
            self.assertEqual({r['path'] for r in m['files']},set(package.FILES))
            self.assertTrue(m['diagnostic_only']);self.assertFalse(m['default_enabled'])
            self.assertEqual(len({r['payload'] for r in m['files']}),4)
            self.assertFalse(any(r['delta'] for r in m['files']))
            self.assertIsNone(next(r for r in m['files'] if r['path']==package.ENTRY)['before'])


if __name__=='__main__':unittest.main()
