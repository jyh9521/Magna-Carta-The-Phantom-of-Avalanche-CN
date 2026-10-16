from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT/'src/configuration/EnhancementSettings.psm1'


class ConfigurationLaunchRouteTests(unittest.TestCase):
    def spec(self, directory, settings, verify):
        code = ("$ErrorActionPreference='Stop'; Import-Module '"+str(MODULE)+"' -Force; "
                "Get-EnhancementLaunchSpec '"+str(directory)+"' '"+str(settings)+"' $"+str(verify).lower()+
                " | ConvertTo-Json -Compress")
        return subprocess.run(['powershell.exe', '-NoProfile', '-Command', code], capture_output=True, text=True, timeout=20)

    def test_shared_route_uses_current_entry_and_explicit_settings(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='config-route-') as d:
            root = Path(d); config = root/'config'; config.mkdir()
            (root/'runtime.json').write_text('{}')
            (root/'Start.ps1').write_text('# owned entry')
            # A stale legacy file must not win over the shared layout.
            (config/'StartEnhanced.ps1').write_text('# stale owned entry')
            result = self.spec(config, config/'custom settings.json', True)
            self.assertEqual(result.returncode, 0, result.stderr)
            spec = json.loads(result.stdout)
            self.assertEqual(Path(spec['Entry']), root/'Start.ps1')
            self.assertEqual(spec['Arguments'], ['-Recipe', 'configured', '-SettingsFile', str(config/'custom settings.json'), '-VerifyOnly'])
            self.assertEqual(spec['Layout'], 'shared')

    def test_legacy_route_remains_supported_without_verify_flag(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='config-route-') as d:
            config = Path(d)/'legacy'; config.mkdir()
            (config/'StartEnhanced.ps1').write_text('# owned entry')
            result = self.spec(config, config/'settings.json', False)
            self.assertEqual(result.returncode, 0, result.stderr)
            spec = json.loads(result.stdout)
            self.assertEqual(Path(spec['Entry']), config/'StartEnhanced.ps1')
            self.assertNotIn('-VerifyOnly', spec['Arguments'])
            self.assertEqual(spec['Layout'], 'legacy')

    def test_missing_shared_entry_rejected_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='config-route-') as d:
            root = Path(d); config = root/'config'; config.mkdir()
            (root/'runtime.json').write_text('{}')
            (config/'StartEnhanced.ps1').write_text('# stale owned entry')
            result = self.spec(config, config/'settings.json', True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Configuration entry is missing', result.stderr)
            self.assertFalse((config/'settings.json').exists())

    def test_gui_verify_button_path_reaches_owned_shared_script(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='config-route-') as d:
            root = Path(d)/'space 路径'; config = root/'config'; config.mkdir(parents=True)
            for name in ['Configure.ps1', 'Configure.xaml', 'EnhancementSettings.psm1']:
                shutil.copyfile(ROOT/'src/configuration'/name, config/name)
            shutil.copyfile(ROOT/'locales/zh-CN/configuration-ui.json', config/'configuration-ui.json')
            shutil.copyfile(ROOT/'locales/zh-CN/art/title-wordmark.png', config/'configuration-logo.png')
            (root/'runtime.json').write_text('{}')
            (root/'Start.ps1').write_text("""param([string]$Recipe,[string]$SettingsFile,[switch]$VerifyOnly)
$ErrorActionPreference='Stop'
if($Recipe -ne 'configured' -or -not $VerifyOnly){exit 81}
$s=Get-Content -LiteralPath $SettingsFile -Raw|ConvertFrom-Json
if($s.resolution -ne '4k' -or -not $s.native_gamepad){exit 82}
@{recipe=$Recipe;verify_only=[bool]$VerifyOnly;settings_read=$true}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $PSScriptRoot 'invoked.json') -Encoding UTF8
""", encoding='utf-8-sig')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA', '-File',
                                     str(config/'Configure.ps1'), '-SelfTest', '-VerifyEntry', '-SettingsFile',
                                     str(config/'fixture settings.json')], capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('ENHANCEMENT_GUI_ENTRY_SELFTEST PASS verify_only=true visible=false game_started=false', result.stdout)
            self.assertTrue(json.loads((root/'invoked.json').read_text(encoding='utf-8-sig'))['verify_only'])
            self.assertFalse((config/'enhancements.json').exists())
