"""Prepare isolated, source-locked advanced-display trials; never launches a game."""
import argparse
import json
from pathlib import Path
import shutil
import render_candidate as render
import prepare_workspace

SCRIPT = r'''[CmdletBinding()]
param([ValidateSet('baseline','render4k','wide4k','fps60','combined')][string]$Mode='baseline', [switch]$PrepareOnly, [switch]$Rollback, [string]$SettingsFile='')
$ErrorActionPreference='Stop'
$Mode=$Mode.ToLowerInvariant()
$workspace=Split-Path -Parent $PSScriptRoot
$expected=ConvertFrom-Json @'
__LOCK__
'@
function Hash($p) { $h=[Security.Cryptography.SHA256]::Create(); try { ([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($p)))).Replace('-','').ToLowerInvariant() } finally { $h.Dispose() } }
function Check($p,$h) { if ((Hash $p) -ne $h) { throw ('Changed input: '+$p) } }
function AtomicIni($p) {
  $temp=Join-Path $workspace ('advanced-'+[guid]::NewGuid().ToString('N')+'.tmp')
  [IO.File]::WriteAllBytes($temp,[IO.File]::ReadAllBytes($p))
  $backup=$temp+'.previous'
  try { [IO.File]::Replace($temp,(Join-Path $workspace $expected.config),$backup) }
  finally {
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp }
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup }
  }
}
if ($workspace -ne $expected.workspace) { throw 'Candidate moved; rebuild trial.' }
Check (Join-Path $PSScriptRoot 'manifest.json') '__MANIFEST_HASH__'
$mutex=New-Object Threading.Mutex($false,('__MUTEX__'))
if (-not $mutex.WaitOne(0)) { throw 'Another trial entry is active.' }
$session=$null
try {
  foreach ($p in $expected.source_hashes.PSObject.Properties) {
    Check (Join-Path $expected.source $p.Name) $p.Value
    if ($p.Name -ne $expected.config) { Check (Join-Path $workspace $p.Name) $p.Value }
  }
  foreach ($p in $expected.locked_files.PSObject.Properties) {
    Check (Join-Path $workspace $p.Name) $p.Value
    Check (Join-Path $expected.source $p.Name) $p.Value
  }
  foreach ($p in $expected.runtime_hashes.PSObject.Properties) { Check (Join-Path $PSScriptRoot $p.Name) $p.Value }
  foreach ($p in $expected.profiles.PSObject.Properties) { Check (Join-Path $PSScriptRoot ($p.Name+'.ini')) $p.Value }
  $ini=Hash (Join-Path $workspace $expected.config)
  if ($ini -notin @($expected.profiles.PSObject.Properties.Value)) { throw 'Unknown active INI; stopped.' }
  Import-Module (Join-Path $PSHOME 'Modules\CimCmdlets\CimCmdlets.psd1') -ErrorAction Stop
  foreach ($p in (Get-CimInstance Win32_Process -Filter "Name='MagnaCarta.exe'")) {
    if (-not $p.ExecutablePath) { throw 'Game process path unavailable; stopped.' }
    if ([IO.Path]::GetFullPath($p.ExecutablePath) -eq (Join-Path $workspace 'MagnaCarta.exe')) { throw 'Exit candidate game before switching.' }
  }
  $session=Join-Path $PSScriptRoot ('session-'+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $session | Out-Null
  if ($Rollback) {
    AtomicIni (Join-Path $PSScriptRoot 'baseline.ini')
    @{mode='baseline';rollback=$true;game_started=$false;exit_code=0} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $session 'result.json') -Encoding UTF8
    Write-Output ('ADVANCED_ROLLBACK PASS game_started=false session='+$session)
  } else {
    # Original preparer requires baseline graphics; restore it for preparation.
    AtomicIni (Join-Path $PSScriptRoot 'baseline.ini')
    $prepArgs=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $workspace '.locale-runtime\Start.ps1'),'-PrepareOnly')
    if ($SettingsFile) { $prepArgs+=@('-SettingsFile',$SettingsFile) }
    try {
      $prep=& powershell.exe @prepArgs 2> (Join-Path $session 'prepare.stderr.txt')
      $prepCode=$LASTEXITCODE
      $prep | Set-Content -LiteralPath (Join-Path $session 'prepare.stdout.txt') -Encoding UTF8
      if ($prepCode -ne 0) { throw ('Locale preparation exit='+$prepCode) }
      $line=@($prep | Where-Object { $_ -match '^LOCALE_START_PREPARED.*session=' })
      if ($line.Count -ne 1) { throw 'Missing preparation result.' }
      $resolved=[IO.Path]::GetFullPath(($line[0] -replace '^.*session=','').Trim())
      $allowed=(Join-Path $workspace '.locale-runtime\session-')
      if (-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid locale session path.' }
      Copy-Item -LiteralPath (Join-Path $resolved 'profile.bin') -Destination (Join-Path $session 'profile.bin')
    } catch { AtomicIni (Join-Path $PSScriptRoot 'baseline.ini'); throw }
    AtomicIni (Join-Path $PSScriptRoot ($Mode+'.ini'))
    @{mode=$Mode;ini_sha256=(Hash (Join-Path $workspace $expected.config));prepared_only=[bool]$PrepareOnly;game_started=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $session 'selection.json') -Encoding UTF8
    if ($PrepareOnly) {
      @{exit_code=0;game_started=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $session 'result.json') -Encoding UTF8
      Write-Output ('ADVANCED_PREPARED PASS mode='+$Mode+' game_started=false session='+$session)
    } else {
      $arguments=@('--workspace',$workspace,'--shim',(Join-Path $PSScriptRoot 'workspace_profile.dll'),'--profile',(Join-Path $session 'profile.bin'),'--log',(Join-Path $session 'profile.log'),'--native-text-step','--system-messages','--focus-guard','--display-profile',$Mode)
      & (Join-Path $PSScriptRoot 'workspace_launcher.exe') @arguments 1> (Join-Path $session 'launcher.stdout.txt') 2> (Join-Path $session 'launcher.stderr.txt')
      $code=$LASTEXITCODE
      @{mode=$Mode;exit_code=$code;launcher_invoked=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $session 'result.json') -Encoding UTF8
      if ($code -ne 0) { throw ('Launcher exit='+$code+'; see '+$session) }
    }
  }
} catch {
  if ($session) {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $session 'failure.txt') -Encoding UTF8
    $restored=$false
    try {
      $current=Hash (Join-Path $workspace $expected.config)
      if ($current -in @($expected.profiles.PSObject.Properties.Value)) { AtomicIni (Join-Path $PSScriptRoot 'baseline.ini'); $restored=$true }
    } catch { $_ | Out-String | Set-Content -LiteralPath (Join-Path $session 'rollback-failure.txt') -Encoding UTF8 }
    $failureCode=1; if ($null -ne $code -and $code -ne 0) { $failureCode=$code }
    @{mode=$Mode;exit_code=$failureCode;restored_baseline=$restored;failed=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $session 'result.json') -Encoding UTF8
  }
  Write-Error $_
  exit 1
} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
'''


def prepare(source, native, output):
    source = render.checked_source(source)
    native = render.plain_path(native)
    output = render.plain_path(output, strict=False)
    build = render.plain_path(Path(__file__).resolve().parents[1] / 'build', strict=False)
    if output == build or not output.is_relative_to(build):
        raise ValueError('Output must be a new directory below repository build')
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Output must be a new independent directory')
    if output.is_relative_to(native) or native.is_relative_to(output):
        raise ValueError('Native directory must be separate')
    runtime_hashes = {name: prepare_workspace.digest(render.plain_path(native / name))
                      for name in ('workspace_launcher.exe', 'workspace_profile.dll')}
    required = ['.locale-runtime/Start.ps1', '.locale-runtime/PrepareProfile.ps1',
                '.locale-install.json', render.graphics.STATE_NAME]
    locked = {name: prepare_workspace.digest(render.plain_path(source / name)) for name in required}
    if (source / '.advanced-runtime').exists():
        raise ValueError('Source already has an advanced runtime')
    prepare_workspace.prepare(source, output, output / '.advanced-runtime/copy-manifest.json')
    runtime = output / '.advanced-runtime'
    for name in runtime_hashes:
        shutil.copy2(native / name, runtime / name)
        if prepare_workspace.digest(runtime / name) != runtime_hashes[name]:
            raise ValueError('Runtime copy mismatch: ' + name)
    for mode, data in render.PROFILES.items():
        (runtime / (mode + '.ini')).write_bytes(data)
    lock = dict(schema=1, source=str(source), workspace=str(output), config=render.CONFIG_NAME,
                source_hashes=render.SOURCE_HASHES, runtime_hashes=runtime_hashes,
                locked_files=locked, profiles={m:render.graphics.sha(d) for m,d in render.PROFILES.items()})
    manifest = runtime / 'manifest.json'
    manifest.write_text(json.dumps(lock, ensure_ascii=True, indent=2), encoding='utf-8')
    script = SCRIPT.replace('__LOCK__', json.dumps(lock, ensure_ascii=True)).replace(
        '__MANIFEST_HASH__', prepare_workspace.digest(manifest)).replace(
        '__MUTEX__', 'Local\\MagnaCartaAdvanced_' + render.graphics.sha(str(output).encode())[:24])
    (runtime / 'StartAdvanced.ps1').write_text(script, encoding='utf-8-sig')
    for mode in render.PROFILES:
        cmd = '@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\StartAdvanced.ps1" -Mode ' + mode + '\r\nif errorlevel 1 pause\r\n'
        (output / ('Play-' + mode + '.cmd')).write_bytes(cmd.encode('ascii'))
    (output / 'Rollback.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\StartAdvanced.ps1" -Rollback\r\nif errorlevel 1 pause\r\n')
    render.checked_source(source)
    return lock


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    prepare(args.source,args.native,args.output)
    print('ADVANCED_TRIAL PASS profiles=5 source_unchanged=true game_started=false output='+str(args.output.absolute()))

if __name__ == '__main__':
    main()
