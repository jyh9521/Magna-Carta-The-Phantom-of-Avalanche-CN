param([ValidateSet('Install','Verify','CheckInstalled','Rollback')][string]$Action='Install',[string]$Source='',[string]$Target='')
$ErrorActionPreference='Stop'
function Hash([string]$p){
 $stream=[IO.File]::OpenRead($p);$algorithm=[Security.Cryptography.SHA256]::Create()
 try{return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
 finally{$algorithm.Dispose();$stream.Dispose()}
}
function Located([string]$root,[string]$name){
 if([IO.Path]::IsPathRooted($name) -or $name -match '(^|[\\/])\.\.([\\/]|$)' -or $name.Contains(':')){throw 'Invalid relative path'}
 $full=[IO.Path]::GetFullPath((Join-Path $root $name))
 if(-not $full.StartsWith($root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Escaping path'}
 return $full
}
function CheckHash([string]$p,[string]$expected){if((Hash $p) -ne $expected){throw ('Hash mismatch: '+$p)}}
$package=$PSScriptRoot
$manifest=Join-Path $package 'package.json'
$m=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($m.schema -ne 1){throw 'Unsupported package'}
if(-not $Target){$Target=Join-Path (Split-Path $package -Parent) 'MagnaCarta-PlayerTest'}
$Target=[IO.Path]::GetFullPath($Target)
if($Action -in @('Install','Verify','Rollback')){
 if(-not $Source){$Source=Read-Host 'Original game folder (contains MagnaCarta.exe)'}
 $Source=(Resolve-Path -LiteralPath $Source).Path.TrimEnd('\')
 if($Target -eq $Source -or $Target.StartsWith($Source+'\',[StringComparison]::OrdinalIgnoreCase) -or $Source.StartsWith($Target.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Separate target required'}
 foreach($f in $m.source_files.PSObject.Properties){CheckHash (Located $Source $f.Name) $f.Value}
}
foreach($f in $m.payload.PSObject.Properties){CheckHash (Located (Join-Path $package 'payload') $f.Name) $f.Value}
foreach($r in $m.changes){CheckHash (Located $package $r.patch) $r.patch_sha256}
if($Action -eq 'Verify'){Write-Output ('BASELINE PASS originals='+@($m.source_files.PSObject.Properties).Count+' deltas='+$m.changes.Count+' game_started=false');exit 0}
if($Action -eq 'Install'){
 if(Test-Path -LiteralPath $Target){throw 'Target must not exist'}
 foreach($f in Get-ChildItem -LiteralPath $Source -Force -Recurse){if($f.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Linked original rejected'}}
 $stage=$Target+'.assembling'
 if(Test-Path -LiteralPath $stage){throw 'Assembly directory already exists'}
 New-Item -ItemType Directory -Path $stage | Out-Null
 Copy-Item -LiteralPath $Source -Destination (Join-Path $stage 'data') -Recurse
 foreach($r in $m.changes){
  $dest=Located (Join-Path $stage 'data') $r.resource
  CheckHash $dest $r.source_sha256
  (Get-Item -LiteralPath $dest).IsReadOnly=$false
  $input=[IO.BinaryReader]::new([IO.File]::OpenRead((Located $package $r.patch)))
  $file=[IO.File]::Open($dest,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite)
  try{
   if([Text.Encoding]::ASCII.GetString($input.ReadBytes(4)) -ne 'MCD1'){throw 'Bad delta magic'}
   $size=$input.ReadUInt64()
   if($size -ne $r.target_size){throw 'Delta size mismatch'}
   $file.SetLength([long]$size)
   $last=0L
   while($input.BaseStream.Position -lt $input.BaseStream.Length){
    $offset=$input.ReadUInt64();$length=$input.ReadUInt32()
    if($offset -lt $last -or $length -eq 0 -or $length -gt 4096 -or $offset+$length -gt $size){throw 'Invalid delta bounds'}
    $bytes=$input.ReadBytes($length)
    if($bytes.Length -ne $length){throw 'Truncated delta'}
    $file.Position=[long]$offset;$file.Write($bytes,0,$length);$last=[long]($offset+$length)
   }
  }finally{$input.Dispose();$file.Dispose()}
  CheckHash $dest $r.target_sha256
 }
 foreach($f in $m.payload.PSObject.Properties){
  $dst=Located $stage $f.Name
  [IO.Directory]::CreateDirectory((Split-Path $dst -Parent)) | Out-Null
  Copy-Item -LiteralPath (Located (Join-Path $package 'payload') $f.Name) -Destination $dst -Force
 }
 @{package_sha256=(Hash $manifest);state='installed'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $stage '.player-package.json') -Encoding UTF8
 Move-Item -LiteralPath $stage -Destination $Target
}
$marker=Join-Path $Target '.player-package.json'
$state=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
if($state.package_sha256 -ne (Hash $manifest) -or $state.state -ne 'installed'){throw 'Installation marker mismatch'}
foreach($r in $m.changes){CheckHash (Located (Join-Path $Target 'data') $r.resource) $r.target_sha256}
if($Action -eq 'Rollback'){
 # Preflight all files before restoring anything. Saves and settings stay untouched.
 foreach($r in $m.changes){Copy-Item -LiteralPath (Located $Source $r.resource) -Destination (Located (Join-Path $Target 'data') $r.resource) -Force;CheckHash (Located (Join-Path $Target 'data') $r.resource) $r.source_sha256}
 $state.state='rolled_back';$state | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
 Write-Output ('ROLLBACK PASS restored='+$m.changes.Count+' original_hashes=exact saves_preserved=true game_started=false');exit 0
}
foreach($f in $m.payload.PSObject.Properties){if($f.Name -ne 'config/enhancements.json' -and $f.Name -ne 'data/DDrawCompat-MagnaCarta.ini'){CheckHash (Located $Target $f.Name) $f.Value}}
Write-Output ('MODIFIED PASS changes='+$m.changes.Count+' payload='+@($m.payload.PSObject.Properties).Count+' game_started=false')
