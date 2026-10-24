"""BSP, source collision and curtain-state observations, not in-game fixes."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import resource_gid
import resource_wrd
from replay_native_collision import NativeCollision, TREE, NODES
from replay_native_fade import replay as replay_fade
import build_blocker_trace_update as package
import test_audio_provider_policy as support


def halfspace():
    # Exact serialized native layout: x-positive empty, x-negative solid.
    return bytes(1024)+struct.pack('<II',0,3)+struct.pack('<I',0)+bytes(22)+struct.pack('<4fI',1,0,0,0,0)+struct.pack('<4I',1,0,1,1)


class GidTests(unittest.TestCase):
    def test_exact_eof_and_binary_leaf(self):
        r=resource_gid.parse(halfspace())
        self.assertEqual((r['native_count'],len(r['nodes'])),(3,3))
        self.assertEqual(r['nodes'][0]['plane'],[1,0,0,0])
        self.assertEqual([n.get('solid') for n in r['nodes'][1:]],[0,1])
        self.assertTrue(r['exact_eof'])
        self.assertFalse(r['resource_binding_verified'])

    def test_truncation_and_trailing_rejected(self):
        for data in (b'',halfspace()[:-1],halfspace()+b'x'):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):resource_gid.parse(data)

    def test_counts_flags_and_nonfinite_rejected(self):
        cases=[]
        for at,value in ((1024,4097),(1028,99),(1032,3),(1032+4+22,0x7fc00000)):
            b=bytearray(halfspace());struct.pack_into('<I',b,at,value);cases.append(b)
        for b in cases:
            with self.assertRaises(ValueError):resource_gid.parse(b)
        with self.assertRaises(ValueError):resource_gid.parse(halfspace(),max_depth=0)

    def test_real_resource_mapping_is_not_filename_guess(self):
        folder=ROOT/'runtime/data'
        if not (folder/'MAP/0109.wrd').exists():self.skipTest('Local original geometry not distributed')
        for map_id,guide_id in ((106,59),(109,62),(111,64)):
            with self.subTest(map=map_id):
                r=resource_wrd.parse((folder/'MAP'/f'{map_id:04d}.wrd').read_bytes())
                self.assertEqual(r['guide_resource_id'],guide_id)
                g=resource_gid.parse((folder/'Gid'/f'{guide_id:04d}.gid').read_bytes())
                self.assertEqual(g['native_count'],len(g['nodes']))


class NativeTests(unittest.TestCase):
    def image(self):
        p=ROOT/'runtime/data/MCAlpha.dll'
        if not p.exists():self.skipTest('Local source-locked engine not distributed')
        return p.read_bytes()

    def test_actual_solver_inside_start_cannot_escape_halfspace(self):
        n=NativeCollision(self.image(),resource_gid.parse(halfspace()))
        self.assertEqual(n.point((1,0,0)),0)
        self.assertEqual(n.point((-1,0,0)),1)
        self.assertEqual(n.segment((1,0,0),(-1,0,0)),1)
        self.assertEqual(n.read(TREE+0x14),NODES)
        for v in [(100,0,0),(-100,0,0),(0,100,0),(0,-100,0)]:
            r=n.solve((-1,0,0),v)
            self.assertEqual(r['result'],[0,0,0])
            self.assertEqual(r['velocity_after'],[0,0,0])
        self.assertEqual(n.solve((10,0,0),(100,0,0))['result'],[100,0,0])

    def test_real_scene_254_curtain_and_paused_negative(self):
        image=self.image();p=ROOT/'runtime/data/Field/0254.fld'
        if not p.exists():self.skipTest('Local scene resource not distributed')
        healthy=replay_fade(image,p.read_bytes())
        held=replay_fade(image,p.read_bytes(),True)
        self.assertEqual((healthy['ticks'][-1]['percentage'],healthy['ticks'][-1]['complete']),(0,1))
        self.assertEqual((held['ticks'][-1]['percentage'],held['ticks'][-1]['complete']),(100,0))
        self.assertFalse(held['player_black_screen_reproduced'])
        self.assertFalse(healthy['rendered'])

    def test_snapshot_observer_abi_and_rollback(self):
        p=ROOT/'build/native/Release/contact_audio_trace_fixture.exe'
        if not p.exists():self.skipTest('Build owned observer fixture')
        r=subprocess.run([str(p),'--blocker'],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('checks=838',r.stdout)
        self.assertIn('results=unchanged last_error=preserved rollback=byte_exact',r.stdout)


class PackageTests(unittest.TestCase):
    setUp=support.PackageTests.setUp

    def build(self):
        b=bytearray(self.native.read_bytes());marker='BLOCKER_TRACE_READY'.encode('utf-16le');b[420:420+len(marker)]=marker;self.native.write_bytes(b)
        return package.build(self.previous,support.package.sha(self.previous.read_bytes()),self.native,self.root/'work',self.root/'blockers.zip')

    def test_existing_entry_has_exact_before_hash(self):
        result=self.build()
        with zipfile.ZipFile(result) as z:
            m=json.loads(z.read('Blocker-Trace-20261024/package.json'))
            row=next(x for x in m['files'] if x['path']=='Play-contact-audio.cmd')
            self.assertEqual(row['before'],support.package.sha(self.old['Play-contact-audio.cmd']))
            self.assertNotIn('Play-audio-fix.cmd',[x['path'] for x in m['files']])
            overlayrow=next(x for x in m['files'] if x['path']=='Overlay-Manifest.json')
            overlay=json.loads(z.read('Blocker-Trace-20261024/'+overlayrow['payload']))
            self.assertTrue(overlay['blocker_trace']['read_only'])
            self.assertNotIn('audio_provider_policy',overlay)

    def test_real_installer_restores_existing_entry(self):
        result=self.build();folder=self.root/'package'
        with zipfile.ZipFile(result) as z:z.extractall(folder)
        target=self.root/'installed'
        for n,b in self.old.items():
            p=target/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        (target/'MC01.sav').write_bytes(b'owned save sentinel')
        def run(action,path):
            p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(folder/'Blocker-Trace-20261024/Update.ps1'),'-Action',action,'-Runtime',str(path)],capture_output=True,text=True,timeout=40)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        for action in ['Verify','Install','Install','CheckInstalled']:run(action,target)
        restored=self.root/'rollback';shutil.copytree(target,restored);run('Rollback',restored)
        for n,b in self.old.items():self.assertEqual((restored/n).read_bytes(),b)
        self.assertEqual((restored/'MC01.sav').read_bytes(),b'owned save sentinel')
        self.assertIn(b'MC_BLOCKER_TRACE=1',(target/'Play-contact-audio.cmd').read_bytes())
