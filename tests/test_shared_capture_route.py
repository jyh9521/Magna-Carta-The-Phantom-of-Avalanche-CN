"""Execute the real argument builder only: no display, launcher or game calls."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SharedCaptureRouteTests(unittest.TestCase):
    def route(self, capture=False, verify=False):
        shell = shutil.which('pwsh') or shutil.which('powershell')
        if not shell:
            self.skipTest('PowerShell required for argument-routing execution')
        source = (ROOT/'src/configuration/StartShared.ps1').read_text('utf8')
        # Execute the actual source block with owned values. The following
        # launcher call and the display transaction are deliberately excluded.
        start = source.index(" $args=@('--workspace'")
        end = source.index(" & (Join-Path $runtimeRoot 'modules/workspace_launcher.exe')", start)
        script = r'''
$runtimeRoot=$PSScriptRoot
$game=Join-Path $PSScriptRoot 'owned-data'
$cache=Join-Path $PSScriptRoot 'owned-cache'
$module='owned-module'
$log=Join-Path $cache 'owned.log'
$settings=[pscustomobject]@{native_gamepad=$false;display_profile='wide4k'}
$selected=[pscustomobject]@{maps=$false;texture=$false}
$cameraEnabled=$false
'''
        script += f'$CaptureException=${str(capture).lower()};$VerifyOnly=${str(verify).lower()}\n'
        script += source[start:end] + '\nConvertTo-Json -InputObject @($args) -Compress\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'owned-route.ps1'
            path.write_text(script, encoding='utf8')
            result = subprocess.run([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(path)], capture_output=True, text=True,
                                    timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_capture_is_explicit_only_and_verify_only_is_retained(self):
        for capture in (False, True):
            for verify in (False, True):
                with self.subTest(capture=capture, verify=verify):
                    args = self.route(capture, verify)
                    self.assertEqual(args.count('--capture-exception'), int(capture))
                    self.assertEqual(args.count('--verify-only'), int(verify))
                    self.assertIn('--workspace', args)
                    self.assertNotIn('--native-gamepad', args)

    def test_switch_and_manual_entry_route_to_configured(self):
        source = (ROOT/'src/configuration/StartShared.ps1').read_text('utf8')
        self.assertIn('[switch]$CaptureException', source.splitlines()[0])
        entry = (ROOT/'assets/shared-runtime/Play-diagnostic.cmd').read_text('ascii')
        self.assertIn('-Recipe configured -CaptureException', entry)
        self.assertNotIn('-VerifyOnly', entry)


if __name__ == '__main__':
    unittest.main()
