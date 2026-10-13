[CmdletBinding()]
param([switch]$FocusGuard)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$state = Get-Content -LiteralPath (Join-Path $workspace '.locale-install.json') -Raw | ConvertFrom-Json
if ($state.state -ne 'candidate') { throw 'This copy is not an active locale candidate.' }
$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry32)
try {
    $key = $base.OpenSubKey('SOFTWARE\Softmax\MagnaCarta')
    if (-not $key) { throw 'Installed settings are missing.' }
    try { $settings = $key.GetValue('MCSetting') } finally { $key.Dispose() }
} finally { $base.Dispose() }
$user = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Registry64)
try {
    $key = $user.OpenSubKey('Software\Classes\VirtualStore\MACHINE\SOFTWARE\WOW6432Node\SOFTMAX\MagnaCarta')
    if ($key) {
        try { $value = $key.GetValue('MCSetting'); if ($value) { $settings = $value } } finally { $key.Dispose() }
    }
} finally { $user.Dispose() }
if ($settings -isnot [byte[]] -or $settings.Length -ne 52) { throw 'Unsupported settings layout.' }
$session = Join-Path $PSScriptRoot ('session-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $session | Out-Null
$profile = Join-Path $session 'profile.bin'
[IO.File]::WriteAllBytes($profile, $settings)
$arguments = @('--workspace', $workspace, '--shim', (Join-Path $PSScriptRoot 'workspace_profile.dll'), '--profile', $profile,
    '--log', (Join-Path $session 'profile.log'), '--native-text-step', '--system-messages')
if ($FocusGuard) { $arguments += '--focus-guard' }
# Explicit manual entry point only. Installation and verification never call it.
& (Join-Path $PSScriptRoot 'workspace_launcher.exe') @arguments
exit $LASTEXITCODE
