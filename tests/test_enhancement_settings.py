from pathlib import Path
import json
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'src/configuration/EnhancementSettings.psm1'
class EnhancementSettingsTests(unittest.TestCase):
    def run_script(self,code):
        return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',"$ErrorActionPreference='Stop'; Import-Module '"+str(MODULE)+"' -Force; "+code],capture_output=True,text=True)
    def test_default_values(self):
        p=self.run_script('New-EnhancementSettings | ConvertTo-Json -Compress');self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout),dict(schema=2,resolution='4k',window_mode='borderless',window_resolution='1280x720',frame_rate=30,native_gamepad=False,free_view=False))
    def test_all_profiles(self):
        for mode in ('baseline','render4k','wide4k','fps60','combined'):
            p=self.run_script("$s=[pscustomobject]@{schema=1;display_profile='wide4k';motion60=$false;native_gamepad=$false};$s.display_profile='"+mode+"';Test-EnhancementSettings $s|Out-Null");self.assertEqual(p.returncode,0,p.stderr)
    def test_invalid_fields_and_types(self):
        for change in ("$s.display_profile='unknown'","$s.motion60='true'","$s.schema=99","$s|Add-Member x 1","$s.motion60=$true"):
            p=self.run_script('$s=New-EnhancementSettings;'+change+';Test-EnhancementSettings $s|Out-Null');self.assertNotEqual(p.returncode,0)
    def test_atomic_save_and_exact_load(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='enhancement-fixture-') as d:
            path=Path(d)/'settings.json'
            code="$p='"+str(path)+"';$s=New-EnhancementSettings;$null=Write-EnhancementSettings $p $s;$s.frame_rate=60;$s.free_view=$true;$s.native_gamepad=$true;$null=Write-EnhancementSettings $p $s;Read-EnhancementSettings $p|ConvertTo-Json -Compress"
            p=self.run_script(code);self.assertEqual(p.returncode,0,p.stderr);v=json.loads(p.stdout);self.assertTrue(v['free_view']);self.assertTrue(v['native_gamepad']);self.assertEqual(v['frame_rate'],60);self.assertFalse(Path(str(path)+'.previous').exists())
    def test_unknown_file_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='enhancement-fixture-') as d:
            path=Path(d)/'settings.json';path.write_bytes(b'{"schema":99}')
            p=self.run_script("Write-EnhancementSettings '"+str(path)+"' (New-EnhancementSettings)");self.assertNotEqual(p.returncode,0);self.assertEqual(path.read_bytes(),b'{"schema":99}')
    def test_gui_feature_gating_and_locale_separation(self):
        s=(ROOT/'src/configuration/Configure.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('configuration-ui.json',s);self.assertNotIn('3840',s)
        x=(ROOT/'src/configuration/Configure.xaml').read_text(encoding='utf8')
        self.assertEqual(x.count('<ComboBox '),1);self.assertIn('Name="WindowResolutionChoices"',x);self.assertIn('ColorAnimation',x)
        labels=json.loads((ROOT/'locales/zh-CN/configuration-ui.json').read_text(encoding='utf8'))
        self.assertEqual(labels['choices']['resolution']['2k'],'2K')
if __name__=='__main__':unittest.main()
