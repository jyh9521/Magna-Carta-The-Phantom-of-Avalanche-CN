param([ValidateSet('Baseline','CheckInstalled','Rollback')][string]$Action='CheckInstalled',[string]$Root=$PSScriptRoot,[string]$Original='')
$ErrorActionPreference='Stop'
function Hash([string]$p){$s=[IO.File]::OpenRead($p);$h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash($s))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose();$s.Dispose()}}
function Located([string]$root,[string]$name){
 if([IO.Path]::IsPathRooted($name) -or $name.Contains(':') -or $name.Contains('\') -or $name -match '(^|/)\.\.?(/|$)' -or $name.Contains('//')){throw 'Invalid relative path'}
 $p=[IO.Path]::GetFullPath((Join-Path $root $name))
 if(-not $p.StartsWith($root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Escaping path'}
 $q=$p
 while($q -and $q.Length -ge $root.Length){if(Test-Path -LiteralPath $q){if((Get-Item -LiteralPath $q -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Linked path rejected'}};$q=Split-Path $q -Parent}
 return $p
}
function Check([string]$p,[string]$h){if((Hash $p) -cne $h){throw ('Hash mismatch: '+$p)}}
$Root=(Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
$m=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'Overlay-Manifest.json') -Raw -Encoding UTF8|ConvertFrom-Json
if($m.schema -ne 1 -or $m.kind -ne 'clean_game_overlay' -or $m.layout -ne 'flat'){throw 'Unsupported overlay manifest'}
if($Action -eq 'Baseline'){
 foreach($p in $m.source_files.PSObject.Properties){Check (Located $Root $p.Name) $p.Value}
 Write-Output ('OVERLAY_BASELINE PASS files='+@($m.source_files.PSObject.Properties).Count+' writes=0');exit 0
}
$mutable=@('config/enhancements.json','DDrawCompat-MagnaCarta.ini')
foreach($p in $m.files.PSObject.Properties){if($p.Name -notin $mutable){Check (Located $Root $p.Name) $p.Value}}
if($Action -eq 'CheckInstalled'){Write-Output ('OVERLAY_MODIFIED PASS files='+@($m.files.PSObject.Properties).Count+' game_started=false');exit 0}
if(Get-Process MagnaCarta -ErrorAction SilentlyContinue){throw 'Exit the game first'}
if(-not $Original){$Original=Read-Host 'Pristine backup folder (contains MagnaCarta.exe)'}
$Original=(Resolve-Path -LiteralPath $Original).Path.TrimEnd('\')
if($Original -eq $Root -or $Original.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase) -or $Root.StartsWith($Original+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Independent pristine backup required'}
$restore=@();$remove=@()
foreach($p in $m.files.PSObject.Properties){
 if($p.Name -in $mutable -or $p.Name -in @('Verify-Overlay.ps1','Verify-Overlay.cmd','Restore-Original.cmd','README-Overlay.txt')){continue}
 $old=$m.source_files.PSObject.Properties[$p.Name]
 if($null -ne $old){Check (Located $Original $p.Name) $old.Value;$restore+=,$p.Name}else{$remove+=,$p.Name}
}
# All source and destination hashes have been checked before the first write.
foreach($name in $restore){$to=Located $Root $name;(Get-Item -LiteralPath $to).IsReadOnly=$false;Copy-Item -LiteralPath (Located $Original $name) -Destination $to -Force;Check $to $m.source_files.$name}
foreach($name in $remove){Remove-Item -LiteralPath (Located $Root $name)}
Write-Output ('OVERLAY_ROLLBACK PASS restored='+$restore.Count+' added_removed='+$remove.Count+' saves_preserved=true settings_preserved=true')
