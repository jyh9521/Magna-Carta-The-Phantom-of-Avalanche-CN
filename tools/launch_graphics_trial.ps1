param(
    [Parameter(Mandatory=$true)][string]$Python,
    [ValidateSet('standard','hal')][string]$DevicePath = 'hal'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$workspace = Join-Path $root 'build\runtime\diagnostic-game'
& $Python (Join-Path $PSScriptRoot 'graphics_compat.py') select-profile --workspace $workspace --profile $DevicePath
if ($LASTEXITCODE -ne 0) { throw 'Graphics profile validation failed; game not started' }
& (Join-Path $PSScriptRoot 'launch_workspace.ps1') -Workspace $workspace -CaptureException -TextureLifetime
