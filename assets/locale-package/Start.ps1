[CmdletBinding()]
param([switch]$FocusGuard = $true, [string]$SettingsFile = '', [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$state = Get-Content -LiteralPath (Join-Path $workspace '.locale-install.json') -Raw | ConvertFrom-Json
if ($state.state -ne 'candidate') { throw 'This copy is not an active locale candidate.' }
. (Join-Path $PSScriptRoot 'PrepareProfile.ps1')
# Fail before launch if the accepted graphics layer/config/driver is absent.
$graphics = @{
    'ddraw.dll' = 'f75f0ac48d2782f225c483dc2f1142303a513e8dd8a60793891ade89f64755ea'
    'DDrawCompat-MagnaCarta.ini' = '0c49061b62b51e4e4dc91458d8c09650d3233895528aea80fafff06ff6b64ea3'
    'Drv/AsrD3DDrv.dll' = '00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29'
}
foreach ($name in $graphics.Keys) {
    if ((Get-CompatibilityHash -Path (Join-Path $workspace $name)) -ne $graphics[$name]) {
        throw ('Unsupported compatibility input: ' + $name)
    }
}
if ($SettingsFile) {
    $settings = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $SettingsFile).Path)
} else {
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
}
if ($settings -isnot [byte[]]) { throw 'Unsupported settings type.' }
$settings = Convert-CompatibilityProfile -Settings $settings
$session = Join-Path $PSScriptRoot ('session-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $session | Out-Null
$profile = Join-Path $session 'profile.bin'
[IO.File]::WriteAllBytes($profile, $settings)
$arguments = @('--workspace', $workspace, '--shim', (Join-Path $PSScriptRoot 'workspace_profile.dll'), '--profile', $profile,
    '--log', (Join-Path $session 'profile.log'), '--native-text-step', '--system-messages')
if ($FocusGuard) { $arguments += '--focus-guard' }
$preparation = @{
    renderer = 'direct3d'; renderer_byte = [int]$settings[1]; focus_guard = [bool]$FocusGuard
    graphics = $graphics; prepared_only = [bool]$PrepareOnly; game_started = $false
}
$preparation | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $session 'preparation.json') -Encoding UTF8
if ($PrepareOnly) {
    Write-Output ('LOCALE_START_PREPARED renderer=direct3d focus_guard=' + ([bool]$FocusGuard).ToString().ToLowerInvariant() + ' game_started=false session=' + $session)
    exit 0
}
# Explicit manual entry point only. Installation and verification never call it.
& (Join-Path $PSScriptRoot 'workspace_launcher.exe') @arguments
exit $LASTEXITCODE
