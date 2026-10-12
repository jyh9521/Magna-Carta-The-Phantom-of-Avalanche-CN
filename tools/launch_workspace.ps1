[CmdletBinding()]
param(
    [string]$Workspace = '',
    [string]$Profile = '',
    [int]$Timeout = 0,
    [switch]$CaptureException,
    [switch]$TextureLifetime
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $Workspace) { $Workspace = Join-Path $root 'build\runtime\game' }
if (-not $Profile) { $Profile = Join-Path $root 'build\runtime\MCSetting.direct3d.bin' }
$native = Join-Path $root 'build\runtime-native\Release'
$launcher = Join-Path $native 'workspace_launcher.exe'
$shim = Join-Path $native 'workspace_profile.dll'
foreach ($path in @($Workspace, $Profile, $launcher, $shim)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required input missing: $path" }
}
if (Get-Process -Name MagnaCarta,MCSetup -ErrorAction SilentlyContinue) {
    throw 'An existing game or settings process must be closed before testing'
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$output = Join-Path $root "build\runtime-launch\session-$stamp"
New-Item -ItemType Directory -Path $output | Out-Null
$graphicsInputs = @()
foreach ($name in @('DDraw.dll','D3DImm.dll','dgVoodoo.conf','DDrawCompat-MagnaCarta.ini','.graphics-compat.json','.dgvoodoo-candidate.json')) {
    $file = Join-Path $Workspace $name
    if (Test-Path -LiteralPath $file -PathType Leaf) {
        $graphicsInputs += @{ name = $name; sha256 = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
}
ConvertTo-Json -InputObject @($graphicsInputs) -Depth 4 | Set-Content -LiteralPath (Join-Path $output 'graphics-inputs.json') -Encoding UTF8
$arguments = @(
    '--workspace', ('"' + (Resolve-Path -LiteralPath $Workspace).Path + '"'),
    '--shim', ('"' + $shim + '"'),
    '--profile', ('"' + (Resolve-Path -LiteralPath $Profile).Path + '"'),
    '--log', ('"' + (Join-Path $output 'profile.log') + '"')
)
if ($Timeout -gt 0) { $arguments += @('--timeout', $Timeout) }
if ($CaptureException) { $arguments += '--capture-exception' }
if ($TextureLifetime) { $arguments += '--texture-lifetime' }
$process = Start-Process -FilePath $launcher -ArgumentList ($arguments -join ' ') -WorkingDirectory $root `
    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $output 'stdout.log') `
    -RedirectStandardError (Join-Path $output 'stderr.log') -PassThru
$process.Id | Set-Content -LiteralPath (Join-Path $output 'launcher.pid')
Write-Output "WORKSPACE_LAUNCH_STARTED pid=$($process.Id) logs=$output"
