import json,shutil,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PS=shutil.which('powershell.exe')

@unittest.skipUnless(PS,'PowerShell profile conversion fixture requires Windows')
class LocaleProfileTests(unittest.TestCase):
    def convert(self,values):
        script=ROOT/'assets/locale-package/PrepareProfile.ps1'
        cmd=f"$ErrorActionPreference='Stop'; . '{script}'; [byte[]]$source=@({','.join(map(str,values))}); $r=Convert-CompatibilityProfile -Settings $source; ConvertTo-Json -Compress @($r); ConvertTo-Json -Compress @($source)"
        return subprocess.run([PS,'-NoProfile','-Command',cmd],capture_output=True,text=True)
    def test_real_powershell_changes_only_renderer_and_keeps_source(self):
        original=[1,1]+list(range(50));r=self.convert(original)
        self.assertEqual(r.returncode,0,r.stderr)
        changed,source=[json.loads(s) for s in r.stdout.splitlines() if s.strip()]
        self.assertEqual(source,original)
        expected=original[:];expected[1]=0;self.assertEqual(changed,expected)
    def test_unknown_layout_and_renderer_are_rejected(self):
        for values in [[1,1]+[0]*49,[1,3]+[0]*50]:
            self.assertNotEqual(self.convert(values).returncode,0)
    def test_start_defaults_and_preparation_guard(self):
        script=(ROOT/'assets/locale-package/Start.ps1').read_text(encoding='utf8')
        self.assertIn('[switch]$FocusGuard = $true',script)
        self.assertIn('Convert-CompatibilityProfile -Settings $settings',script)
        self.assertLess(script.index('if ($PrepareOnly)'),script.index("& (Join-Path $PSScriptRoot 'workspace_launcher.exe')"))
