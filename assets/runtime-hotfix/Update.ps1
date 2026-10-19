param([ValidateSet('Install','Verify','CheckInstalled','Rollback')][string]$Action='Install',[string]$Target='')
$ErrorActionPreference='Stop'
function Hash([string]$Path){
 $stream=[IO.File]::OpenRead($Path);$algorithm=[Security.Cryptography.SHA256]::Create()
 try{return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
 finally{$algorithm.Dispose();$stream.Dispose()}
}
function Located([string]$Root,[string]$Name){
 if([IO.Path]::IsPathRooted($Name) -or $Name -match '(^|[\\/])\.\.([\\/]|$)' -or $Name.Contains(':')){throw 'Invalid relative path'}
 $p=[IO.Path]::GetFullPath((Join-Path $Root $Name))
 if(-not $p.StartsWith($Root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Escaping path'}
 return $p
}
if(-not $Target){$Target=Read-Host 'Installed game folder (contains runtime.json and Play.cmd)'}
$Target=(Resolve-Path -LiteralPath $Target).Path.TrimEnd('\')
$m=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'hotfix.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($m.schema -ne 1 -or $m.id -notmatch '^[a-z0-9-]+$'){throw 'Unsupported hotfix'}
$rows=@($m.files.PSObject.Properties)
foreach($r in $rows){if((Hash (Located (Join-Path $PSScriptRoot 'payload') $r.Name)) -ne $r.Value.after){throw ('Payload drift: '+$r.Name)}}
$before=$true;$after=$true
foreach($r in $rows){$h=Hash (Located $Target $r.Name);if($h -ne $r.Value.before){$before=$false};if($h -ne $r.Value.after){$after=$false}}
if(-not $before -and -not $after){throw 'Mixed or unknown installed version; no files changed'}
if($Action -eq 'CheckInstalled'){if(-not $after){throw 'Hotfix is not installed'};Write-Output 'HOTFIX_CHECK PASS hashes=exact game_started=false';exit 0}
foreach($r in $m.required_data.PSObject.Properties){if((Hash (Located (Join-Path $Target 'data') $r.Name)) -ne $r.Value){throw ('Game resource drift: '+$r.Name)}}
if($Action -eq 'Verify'){Write-Output 'HOTFIX_VERIFY PASS version=known resources=exact game_started=false';exit 0}
if(Get-Process MagnaCarta -ErrorAction SilentlyContinue){throw 'Exit game before updating'}
$record=Join-Path $Target ('.runtime-updates\'+$m.id)
if($Action -eq 'Install'){
 if($after){Write-Output 'HOTFIX_INSTALL PASS already_installed=true game_started=false';exit 0}
 if(Test-Path -LiteralPath $record){throw 'Existing hotfix record; no files changed'}
 New-Item -ItemType Directory -Path $record | Out-Null
 foreach($r in $rows){$p=Located $record $r.Name;[IO.Directory]::CreateDirectory((Split-Path $p -Parent))|Out-Null;Copy-Item -LiteralPath (Located $Target $r.Name) -Destination $p; if((Hash $p) -ne $r.Value.before){throw 'Backup readback mismatch'}}
 $done=@()
 try{
  foreach($r in $rows){$done+=,$r;Copy-Item -LiteralPath (Located (Join-Path $PSScriptRoot 'payload') $r.Name) -Destination (Located $Target $r.Name) -Force;if((Hash (Located $Target $r.Name)) -ne $r.Value.after){throw 'Update readback mismatch'}}
 }catch{foreach($r in $done){Copy-Item -LiteralPath (Located $record $r.Name) -Destination (Located $Target $r.Name) -Force};throw}
 Write-Output 'HOTFIX_INSTALL PASS hashes=exact saves_settings_preserved=true game_started=false';exit 0
}
if(-not $after){throw 'Rollback requires installed hotfix'}
foreach($r in $rows){if((Hash (Located $record $r.Name)) -ne $r.Value.before){throw 'Rollback source drift; no files changed'}}
foreach($r in $rows){Copy-Item -LiteralPath (Located $record $r.Name) -Destination (Located $Target $r.Name) -Force;if((Hash (Located $Target $r.Name)) -ne $r.Value.before){throw 'Rollback readback mismatch'}}
Write-Output 'HOTFIX_ROLLBACK PASS original_hashes=exact saves_settings_preserved=true game_started=false'
