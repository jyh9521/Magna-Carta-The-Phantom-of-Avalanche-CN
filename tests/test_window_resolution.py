from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
class WindowResolutionTests(unittest.TestCase):
 def test_window_size_defaults_and_validation(self):
  code="""$ErrorActionPreference='Stop';Import-Module './src/configuration/EnhancementSettings.psm1' -Force;
$s=New-EnhancementSettings
if($s.window_resolution -ne '1280x720'){throw 'Missing independent window size; renderer resolution does not size the window'}
foreach($size in @('960x540','1280x720','1600x900','1920x1080','2560x1440')){
$s.window_mode='windowed';$s.window_resolution=$size
$r=Get-EnhancementRuntimeSettings $s
if($r.window_resolution -ne $size){throw 'Window size lost before launch'}
}
$s.window_resolution='1x1';try{Test-EnhancementSettings $s|Out-Null}catch{'WINDOW_RESOLUTION PASS sizes=5 invalid=rejected';exit 0};throw 'Tiny window accepted'
"""
  p=subprocess.run(['powershell.exe','-NoProfile','-Command',code],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_old_schema_two_gets_default_without_mutating_input(self):
  code="""$ErrorActionPreference='Stop';Import-Module './src/configuration/EnhancementSettings.psm1' -Force;
$old=[pscustomobject]@{schema=2;resolution='auto';window_mode='windowed';frame_rate=30;native_gamepad=$false;free_view=$false}
$new=Convert-EnhancementSettings $old
if($new.window_resolution -ne '1280x720' -or $old.PSObject.Properties['window_resolution']){throw 'Legacy settings changed'}
if((Get-EnhancementRuntimeSettings $old).window_resolution -ne '1280x720'){throw 'Legacy launch default missing'}
"""
  p=subprocess.run(['powershell.exe','-NoProfile','-Command',code],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_dropdown_is_available_in_windowed_mode(self):
  xaml=(ROOT/'src/configuration/Configure.xaml').read_text(encoding='utf8')
  self.assertIn('Name="WindowResolutionChoices"',xaml)
  script=(ROOT/'src/configuration/Configure.ps1').read_text(encoding='utf8')
  self.assertIn('ENHANCEMENT_WINDOW_SIZE_SELFTEST PASS',script)
if __name__=='__main__':unittest.main()
