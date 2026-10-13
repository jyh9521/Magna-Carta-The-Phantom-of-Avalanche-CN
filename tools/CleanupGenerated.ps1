$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$runtime=Join-Path $root 'runtime'
$manifest=Get-Content -LiteralPath (Join-Path $runtime 'runtime.json') -Raw | ConvertFrom-Json
function Hash($p){$s=[IO.File]::OpenRead($p);$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash($s))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose();$s.Dispose()}}
$local=(& git -C $root rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0){throw 'Git identity failed'}
$remote=& git -C $root ls-remote origin refs/heads/main
if($LASTEXITCODE -ne 0 -or -not $remote -or ($remote -split '\s+')[0] -ne $local){throw 'Local source is not synchronized with GitHub'}
& git -C $root diff --quiet HEAD --
if($LASTEXITCODE -ne 0){throw 'Uncommitted tracked source changes'}
if(Get-Process MagnaCarta,workspace_launcher -ErrorAction SilentlyContinue){throw 'Exit game and launcher before cleanup'}
foreach($p in $manifest.data.PSObject.Properties){if((Hash (Join-Path $runtime ('data/'+$p.Name))) -ne $p.Value){throw 'Migrated game input mismatch'}}
foreach($p in $manifest.files.PSObject.Properties){if((Hash (Join-Path $runtime $p.Name)) -ne $p.Value){throw ('Migrated runtime input mismatch: '+$p.Name)}}
$saves=Get-Content -LiteralPath (Join-Path $runtime 'saves-import/index.json') -Raw | ConvertFrom-Json
foreach($s in $saves){if((Hash (Join-Path $runtime ('saves-import/'+$s.Hash+'.sav'))) -ne $s.Hash){throw 'Saved-game preservation mismatch'}}
$relative=@('build','dist','runtime/data/.advanced-runtime','runtime/data/.locale-runtime','runtime/data/.disc-gate','runtime/data/.driver-trial-original')
$targets=@();$bytes=0L;$files=0L
foreach($name in $relative){
 $path=Join-Path $root $name
 if(-not (Test-Path -LiteralPath $path)){continue}
 $resolved=(Resolve-Path -LiteralPath $path).Path
 if(-not $resolved.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase) -or $resolved -ne $path){throw 'Unexpected cleanup absolute path'}
 if((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Linked target'}
 if(@(& git -C $root ls-files -- $name).Count){throw 'Tracked source in cleanup target'}
 foreach($item in (Get-ChildItem -LiteralPath $path -Recurse -Force)){
  if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Linked descendant'}
  if(-not $item.PSIsContainer){$bytes+=$item.Length;$files++}
 }
 $targets += $path
}
$freeBefore=(Get-PSDrive C).Free
foreach($path in $targets){Remove-Item -LiteralPath $path -Recurse -Force;if(Test-Path -LiteralPath $path){throw 'Deletion incomplete'};Write-Output ('REMOVED '+$path)}
# Remove stale launch/debug files at the data root, never resource subdirectories or saves.
$stale=@(Get-ChildItem -LiteralPath (Join-Path $runtime 'data') -File -Force | Where-Object {$_.Extension -in '.cmd','.ps1','.log','.dmp'})
foreach($file in $stale){$bytes+=$file.Length;$files++;Remove-Item -LiteralPath $file.FullName -Force}
$result=[pscustomobject]@{state='deleted';commit=$local;removed_bytes=$bytes;removed_files=$files;free_before=$freeBefore;free_after=(Get-PSDrive C).Free;game_data='runtime/data';source_pushed=$true;preserved_saves=(@($saves.Hash|Sort-Object -Unique)).Count}
$result|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $runtime 'maintenance/cleanup-result.json') -Encoding utf8
Write-Output ('CLEANUP PASS removed_gib='+[math]::Round($bytes/1GB,2)+' files='+$files+' source_pushed=true saves=preserved')
