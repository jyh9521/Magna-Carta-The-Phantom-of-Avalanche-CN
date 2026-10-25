from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_configuration_profiles import build, profiles


class MaterialConfigurationTests(unittest.TestCase):
    def run_ps(self, code):
        return subprocess.run(['powershell.exe', '-NoProfile', '-STA', '-Command',
                               "$ErrorActionPreference='Stop';Import-Module '"+
                               str(ROOT/'src/configuration/EnhancementSettings.psm1')+"' -Force;"+code],
                              capture_output=True, text=True, timeout=60)

    def test_all_96_independent_settings_combinations(self):
        result = self.run_ps("""
$count=0
foreach($r in @('1080p','2k','4k','auto')){foreach($w in @('fullscreen','windowed','borderless')){
foreach($f in @(30,60)){foreach($pad in @($false,$true)){foreach($camera in @($false,$true)){
 $s=New-EnhancementSettings;$s.resolution=$r;$s.window_mode=$w;$s.frame_rate=$f;$s.native_gamepad=$pad;$s.free_view=$camera
 $v=Get-EnhancementRuntimeSettings $s
 if($v.display_profile -ne ('md3-'+$r+'-'+$w+'-'+$f) -or $v.motion60 -ne ($f -eq 60) -or $v.native_gamepad -or $v.free_view){throw 'Routing mismatch'}
 $count++
}}}}}
'MATERIAL_SETTINGS_MATRIX PASS combinations='+$count
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('combinations=96', result.stdout)

    def test_invalid_values_do_not_silently_fallback(self):
        result = self.run_ps("""
$bad=@({$s.resolution='8k'},{$s.window_mode='popup'},{$s.frame_rate=120},{$s.frame_rate='60'},{$s.native_gamepad='false'},{$s.free_view=1},{$s|Add-Member injected 1},{$s.schema=99})
foreach($change in $bad){$s=New-EnhancementSettings;& $change;$rejected=$false;try{Test-EnhancementSettings $s|Out-Null}catch{$rejected=$true};if(-not $rejected){throw 'Invalid setting accepted'}}
'MATERIAL_INVALID PASS cases=8'
""")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_settings_migrate_without_write(self):
        result = self.run_ps("""
foreach($p in @('baseline','render4k','wide4k','fps60','combined')){
 $old=[pscustomobject]@{schema=1;display_profile=$p;motion60=$false;native_gamepad=$true}
 $s=Convert-EnhancementSettings $old
 if($old.schema -ne 1 -or $s.schema -ne 2 -or -not $s.native_gamepad -or $s.free_view){throw 'Migration mismatch'}
 if($s.frame_rate -ne $(if($p -in @('fps60','combined')){60}else{30})){throw 'Frame migration mismatch'}
}
'MATERIAL_MIGRATION PASS profiles=5'
""")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_native_allowlist_matches_all_profile_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            header = build(Path(directory))
            self.assertEqual(header, (ROOT/'src/runtime/configuration_display_presets.h').read_text(encoding='utf8'))
            entries = list(profiles())
            self.assertEqual(len(entries), 24)
            for name, data, fps in entries:
                self.assertIn(hashlib.sha256(data).hexdigest(), header)
                self.assertIn(f'flipend({fps})'.encode(), data)
                self.assertNotIn(b'FullscreenMode = windowed', data)
            self.assertIn(b'display(-1)', next(data for name, data, _ in entries if name == 'md3-auto-borderless-30'))

    def test_real_wpf_choices_motion_and_offscreen_render_at_150_percent(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='material-ui-') as directory:
            d = Path(directory)
            for name in ['Configure.ps1', 'Configure.xaml', 'EnhancementSettings.psm1']:
                shutil.copyfile(ROOT/'src/configuration'/name, d/name)
            shutil.copyfile(ROOT/'locales/zh-CN/configuration-ui.json', d/'configuration-ui.json')
            shutil.copyfile(ROOT/'locales/zh-CN/art/title-wordmark.png', d/'configuration-logo.png')
            preview = d/'preview.png'
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA',
                                     '-File', str(d/'Configure.ps1'), '-SelfTest', '-PreviewPath', str(preview),
                                     '-PreviewScale', '1.5'], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('choices=9 groups=3', result.stdout)
            self.assertIn('ENHANCEMENT_MOTION_SELFTEST PASS', result.stdout)
            from PIL import Image
            with Image.open(preview) as image:
                self.assertEqual(image.size, (1185, 1005))
                self.assertGreater(len(image.getcolors(image.width*image.height)), 100)
            self.assertFalse((d/'enhancements.json').exists())


if __name__ == '__main__':
    unittest.main()
