param([ValidateSet('Install','Verify','CheckInstalled','Rollback')][string]$Action='Install',[Parameter(Mandatory=$true)][string]$Runtime)
$ErrorActionPreference='Stop'
function Digest([byte[]]$bytes){$s=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($s.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}finally{$s.Dispose()}}
function ReadBytes([string]$p){return ,([IO.File]::ReadAllBytes($p))}
function Allowed([string]$name){return $name -cmatch '^(?i:runtime\.json|modules/(?:[A-Za-z0-9_-]+\.dll|workspace_launcher\.exe)|data/BGR/[A-Za-z0-9_-]+\.bgr|data/Fpb/[A-Za-z0-9_-]+\.fpb|data/(?:Itm/0000\.itm|Abi/0000\.abi|Sgi/0000\.sgi|CharData/0000\.cha|MCAlpha\.dll))$'}
function Located([string]$root,[string]$name){
 if([IO.Path]::IsPathRooted($name) -or $name.Contains(':') -or $name.Contains('\') -or $name -match '(^|/)\.\.?(/|$)' -or $name.Contains('//')){throw 'Invalid relative path'}
 $full=[IO.Path]::GetFullPath((Join-Path $root $name))
 if(-not $full.StartsWith($root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Escaping path'}
 $p=$full
 while($p -and $p.Length -ge $root.Length){if(Test-Path -LiteralPath $p){if((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Linked path rejected'}};$p=Split-Path $p -Parent}
 return $full
}
function Check([byte[]]$raw,[string]$expected){if((Digest $raw) -cne $expected){throw 'Hash mismatch'}}
function ApplyDelta([byte[]]$before,[byte[]]$patch,[long]$size){
 if($size -lt 0 -or $size -gt 268435456){throw 'Invalid delta size'}
 $stream=[IO.MemoryStream]::new($patch,$false);$reader=[IO.BinaryReader]::new($stream)
 try{
  if([Text.Encoding]::ASCII.GetString($reader.ReadBytes(4)) -ne 'MCD1' -or $reader.ReadUInt64() -ne $size){throw 'Invalid delta header'}
  $after=[byte[]]::new($size);[Array]::Copy($before,$after,[Math]::Min($before.Length,$after.Length));$last=0L
  while($stream.Position -lt $stream.Length){
   $off=$reader.ReadUInt64();$len=$reader.ReadUInt32()
   if($off -lt $last -or $len -eq 0 -or $len -gt 4096 -or $off -gt $size -or $len -gt $size-$off){throw 'Invalid delta bounds'}
   $block=$reader.ReadBytes($len);if($block.Length -ne $len){throw 'Truncated delta'}
   [Array]::Copy($block,0,$after,[long]$off,$len);$last=[long]($off+$len)
  }
  return ,$after
 }finally{$reader.Dispose();$stream.Dispose()}
}
function WriteAtomic([string]$path,[byte[]]$raw){
 [IO.Directory]::CreateDirectory((Split-Path $path -Parent))|Out-Null
 $tmp=$path+'.text-update-tmp';if(Test-Path -LiteralPath $tmp){throw 'Unexpected update temporary file'}
 [IO.File]::WriteAllBytes($tmp,$raw)
 try{if(Test-Path -LiteralPath $path){[IO.File]::Replace($tmp,$path,[NullString]::Value)}else{[IO.File]::Move($tmp,$path)}}finally{if(Test-Path -LiteralPath $tmp){Remove-Item -LiteralPath $tmp}}
}
$Runtime=(Resolve-Path -LiteralPath $Runtime).Path.TrimEnd('\')
if(Get-Process MagnaCarta -ErrorAction SilentlyContinue){throw 'Exit the game first'}
$manifest=ReadBytes (Join-Path $PSScriptRoot 'package.json');$m=[Text.Encoding]::UTF8.GetString($manifest)|ConvertFrom-Json
if($m.schema -ne 1 -or $m.kind -ne 'text_runtime_update' -or @($m.files).Count -eq 0){throw 'Unsupported package'}
$backup=Located $Runtime '.text-runtime-update';$marker=Join-Path $backup 'state.json'
$seen=@{};$prepared=@{};$before=@{}
foreach($r in $m.files){
 if(-not (Allowed $r.path) -or $seen.ContainsKey($r.path)){throw 'Unsupported or duplicate update path'};$seen[$r.path]=$true
 if($r.after -cnotmatch '^[0-9a-f]{64}$' -or ($null -ne $r.before -and $r.before -cnotmatch '^[0-9a-f]{64}$')){throw 'Invalid digest'}
 if(($r.path -like 'data/*') -ne [bool]$r.delta -or ($r.delta -and $null -eq $r.before)){throw 'Game data must be source-locked deltas'}
 $dest=Located $Runtime $r.path
 if($Action -in @('Verify','Install')){
  if($null -eq $r.before){if(Test-Path -LiteralPath $dest){throw 'Unexpected existing file'};$old=$null}else{$old=ReadBytes $dest;Check $old $r.before}
  $payload=ReadBytes (Located $PSScriptRoot $r.payload);Check $payload $r.payload_sha256
  if($r.delta){$new=ApplyDelta $old $payload $r.size}else{$new=$payload}
  if($new.Length -ne $r.size){throw 'Output size mismatch'};Check $new $r.after
  $prepared[$r.path]=$new;$before[$r.path]=$old
 }else{
  Check (ReadBytes $dest) $r.after
  if($Action -eq 'Rollback' -and $null -ne $r.before){$old=ReadBytes (Located $backup ('original/'+$r.path));Check $old $r.before;$prepared[$r.path]=$old}
 }
}
if($Action -eq 'Verify'){Write-Output ('BASELINE PASS files='+$seen.Count+' writes=0');exit 0}
if($Action -in @('Rollback','CheckInstalled')){
 $state=Get-Content -LiteralPath $marker -Raw -Encoding UTF8|ConvertFrom-Json
 if($state.package_sha256 -cne (Digest $manifest) -or $state.state -ne 'installed'){throw 'Installation marker mismatch'}
}
if($Action -eq 'Install'){
 if(Test-Path -LiteralPath $backup){
  $previous=Get-Content -LiteralPath $marker -Raw -Encoding UTF8|ConvertFrom-Json
  if($previous.package_sha256 -cne (Digest $manifest) -or $previous.state -ne 'rolled_back'){throw 'Existing update backup; rollback first'}
  foreach($r in $m.files){if($null -ne $r.before){Check (ReadBytes (Located $backup ('original/'+$r.path))) $r.before}}
 }
 [IO.Directory]::CreateDirectory($backup)|Out-Null
 foreach($r in $m.files){if($null -ne $before[$r.path]){WriteAtomic (Located $backup ('original/'+$r.path)) $before[$r.path]}}
 $applied=@()
 try{
  foreach($r in $m.files){WriteAtomic (Located $Runtime $r.path) $prepared[$r.path];$applied+=,$r;Check (ReadBytes (Located $Runtime $r.path)) $r.after}
  WriteAtomic $marker ([Text.Encoding]::UTF8.GetBytes((@{package_sha256=(Digest $manifest);state='installed'}|ConvertTo-Json)))
 }catch{
  foreach($r in $applied){$dest=Located $Runtime $r.path;if($null -eq $r.before){Remove-Item -LiteralPath $dest}else{WriteAtomic $dest $before[$r.path]}}
  throw
 }
}
if($Action -eq 'Rollback'){
 $restored=@();$installed=@{}
 foreach($r in $m.files){$installed[$r.path]=ReadBytes (Located $Runtime $r.path)}
 try{
  foreach($r in $m.files){$dest=Located $Runtime $r.path;if($null -eq $r.before){Remove-Item -LiteralPath $dest;$restored+=,$r}else{WriteAtomic $dest $prepared[$r.path];$restored+=,$r;Check (ReadBytes $dest) $r.before}}
 }catch{foreach($r in $restored){WriteAtomic (Located $Runtime $r.path) $installed[$r.path]};throw}
 # Keep exact backup evidence; a different subsequent package may reuse a fresh name.
 $state.state='rolled_back';WriteAtomic $marker ([Text.Encoding]::UTF8.GetBytes(($state|ConvertTo-Json)))
 Write-Output ('ROLLBACK PASS files='+$seen.Count+' original_hashes=exact saves_preserved=true settings_preserved=true');exit 0
}
Write-Output ('MODIFIED PASS files='+$seen.Count+' saves_preserved=true settings_preserved=true')
