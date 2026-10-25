Set-StrictMode -Version Latest
$profiles=@('baseline','render4k','wide4k','fps60','combined')
$windowResolutions=@('960x540','1280x720','1600x900','1920x1080','2560x1440')
function Get-EnhancementUserPaths([string]$RuntimeRoot) {
 $root=[IO.Path]::GetFullPath($RuntimeRoot).TrimEnd([char[]]'\/').ToUpperInvariant()
 $base=[Environment]::GetEnvironmentVariable('LOCALAPPDATA')
 if(-not $base -or -not [IO.Path]::IsPathRooted($base)){throw 'LOCALAPPDATA must identify an absolute user directory'}
 $id=(Get-EnhancementByteHash ([Text.Encoding]::UTF8.GetBytes($root))).ToLowerInvariant().Substring(0,16)
 $directory=Join-Path ([IO.Path]::GetFullPath($base)) ('MagnaCarta/Installations/'+$id)
 [pscustomobject]@{Root=$directory;Settings=(Join-Path $directory 'enhancements.json');Cache=(Join-Path $directory 'cache');InstallationId=$id}
}
function Initialize-EnhancementUserSettings([string]$RuntimeRoot) {
 $paths=Get-EnhancementUserPaths $RuntimeRoot
 $null=[IO.Directory]::CreateDirectory($paths.Root)
 $lock=[Threading.Mutex]::new($false,('Local\MagnaCartaSettings_'+$paths.InstallationId))
 $held=$false
 try{
  $held=$lock.WaitOne(15000);if(-not $held){throw 'User settings migration is busy'}
  if(Test-Path -LiteralPath $paths.Settings){$null=Read-EnhancementSettings $paths.Settings}
  else{
   $legacy=Join-Path $RuntimeRoot 'config/enhancements.json'
   $value=if(Test-Path -LiteralPath $legacy){Read-EnhancementSettings $legacy}else{New-EnhancementSettings}
   $null=Write-EnhancementSettings $paths.Settings $value
   $info=[ordered]@{schema=1;installation=[IO.Path]::GetFullPath($RuntimeRoot);legacy_settings=$legacy}
   [IO.File]::WriteAllText((Join-Path $paths.Root 'installation.json'),($info|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
  }
  $paths.Settings
 }finally{if($held){$lock.ReleaseMutex()};$lock.Dispose()}
}
function New-EnhancementSettings {
 [pscustomobject]@{schema=2;resolution='4k';window_mode='borderless';window_resolution='1280x720';frame_rate=30;native_gamepad=$false;free_view=$false}
}
function Test-EnhancementSettings($Value) {
 if($null -eq $Value){throw 'Settings must be an object'}
 $names=@($Value.PSObject.Properties.Name|Sort-Object)
 if($Value.schema -is [bool] -or $Value.schema -is [string]){throw 'Unsupported settings schema'}
 if($Value.schema -eq 1){
  if(($names -join ',') -ne 'display_profile,motion60,native_gamepad,schema'){throw 'Unknown or missing setting fields'}
  if($Value.display_profile -isnot [string] -or $Value.display_profile -notin $profiles){throw 'Unsupported display profile'}
  if($Value.motion60 -isnot [bool] -or $Value.native_gamepad -isnot [bool]){throw 'Feature switches must be boolean'}
  if($Value.motion60 -and $Value.display_profile -notin @('fps60','combined')){throw 'Motion interpolation requires a 60Hz profile'}
 }elseif($Value.schema -eq 2){
  if(($names -join ',') -notin @('frame_rate,free_view,native_gamepad,resolution,schema,window_mode','frame_rate,free_view,native_gamepad,resolution,schema,window_mode,window_resolution')){throw 'Unknown or missing setting fields'}
  if($Value.PSObject.Properties['window_resolution'] -and ($Value.window_resolution -isnot [string] -or $Value.window_resolution -notin $windowResolutions)){throw 'Unsupported window resolution'}
  if($Value.resolution -isnot [string] -or $Value.resolution -notin @('1080p','2k','4k','auto')){throw 'Unsupported resolution'}
  if($Value.window_mode -isnot [string] -or $Value.window_mode -notin @('fullscreen','windowed','borderless')){throw 'Unsupported window mode'}
  if($Value.frame_rate -is [bool] -or $Value.frame_rate -is [string] -or $Value.frame_rate -notin @(30,60)){throw 'Unsupported frame rate'}
  if($Value.native_gamepad -isnot [bool] -or $Value.free_view -isnot [bool]){throw 'Feature switches must be boolean'}
 }else{throw 'Unsupported settings schema'}
 $Value
}
function Convert-EnhancementSettings($Value){
 $s=Test-EnhancementSettings $Value
 if($s.schema -eq 2){
  if(-not $s.PSObject.Properties['window_resolution']){$s=$s.PSObject.Copy();$s|Add-Member window_resolution '1280x720'}
  return $s
 }
 $v=New-EnhancementSettings
 $v.resolution=if($s.display_profile -in @('baseline','fps60')){'1080p'}else{'4k'}
 $v.frame_rate=if($s.display_profile -in @('fps60','combined')){60}else{30}
 $v.native_gamepad=$s.native_gamepad
 return $v
}
function Get-EnhancementRuntimeSettings($Value){
 $s=Test-EnhancementSettings $Value
 if($s.schema -eq 1){return [pscustomobject]@{display_profile=$s.display_profile;motion60=$s.motion60;native_gamepad=$false;free_view=$false;window_mode='borderless'}}
 $windowResolution=if($s.PSObject.Properties['window_resolution']){$s.window_resolution}else{'1280x720'}
 [pscustomobject]@{window_resolution=$windowResolution;display_profile=('md3-'+$s.resolution+'-'+$s.window_mode+'-'+$s.frame_rate);motion60=($s.frame_rate -eq 60);native_gamepad=$false;free_view=$false;window_mode=$s.window_mode}
}
function Read-EnhancementSettings([string]$Path) {
 if(-not (Test-Path -LiteralPath $Path)){return New-EnhancementSettings}
 if((Get-Item -LiteralPath $Path).Length -gt 4096){throw 'Settings file too large'}
 Test-EnhancementSettings (Get-Content -LiteralPath $Path -Raw -Encoding UTF8|ConvertFrom-Json)
}
function Write-EnhancementSettings([string]$Path,$Value) {
 $valid=Test-EnhancementSettings $Value
 if(Test-Path -LiteralPath $Path){$null=Read-EnhancementSettings $Path}
 $parent=Split-Path -Parent ([IO.Path]::GetFullPath($Path));if(-not (Test-Path -LiteralPath $parent)){throw 'Settings parent directory is missing'}
 $temp=Join-Path $parent ('enhancement-'+[guid]::NewGuid().ToString('N')+'.tmp')
 $backup=$Path+'.previous'
 if(Test-Path -LiteralPath $backup){throw 'Previous settings backup exists; preserve it before saving'}
 try {
  [IO.File]::WriteAllText($temp,($valid|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
  $null=Read-EnhancementSettings $temp
  if(Test-Path -LiteralPath $Path){[IO.File]::Replace($temp,$Path,$backup)}else{[IO.File]::Move($temp,$Path)}
  $result=Read-EnhancementSettings $Path
  if(Test-Path -LiteralPath $backup){Remove-Item -LiteralPath $backup}
  $result
 }finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp}}
}
function Get-EnhancementLaunchSpec([string]$ConfigDirectory,[string]$SettingsFile,[bool]$VerifyOnly=$false) {
 $directory=[IO.Path]::GetFullPath($ConfigDirectory)
 $root=Split-Path -Parent $directory
 if(-not $SettingsFile){
  if(Test-Path -LiteralPath (Join-Path $root 'runtime.json')){$SettingsFile=Initialize-EnhancementUserSettings $root}else{$SettingsFile=Join-Path $directory 'enhancements.json'}
 }
 $settings=[IO.Path]::GetFullPath($SettingsFile)
 if(Test-Path -LiteralPath (Join-Path $root 'runtime.json') -PathType Leaf){
  $entry=Join-Path $root 'Start.ps1';$parameters=@('-Recipe','configured','-SettingsFile',$settings)
  $layout='shared';$log=Join-Path (Get-EnhancementUserPaths $root).Cache 'profile.log'
 }else{
  $entry=Join-Path $directory 'StartEnhanced.ps1';$parameters=@('-SettingsFile',$settings)
  $layout='legacy';$log=Join-Path $directory 'session-*/profile.log'
 }
 if(-not (Test-Path -LiteralPath $entry -PathType Leaf)){throw ('Configuration entry is missing: '+$entry)}
 if($VerifyOnly){$parameters+='-VerifyOnly'}
 [pscustomobject]@{Entry=$entry;Arguments=$parameters;LogPath=$log;Layout=$layout}
}
function Get-EnhancementByteHash([byte[]]$Bytes) {
 $hash=[Security.Cryptography.SHA256]::Create()
 try{([BitConverter]::ToString($hash.ComputeHash($Bytes))).Replace('-','')}finally{$hash.Dispose()}
}
function Write-EnhancementBytesAtomic([string]$Path,[byte[]]$Bytes) {
 $item=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
 if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unexpected display configuration path type'}
 $temporary=Join-Path (Split-Path -Parent $Path) ('enhancement-'+[guid]::NewGuid().ToString('N')+'.tmp')
 try{
  try{
   [IO.File]::WriteAllBytes($temporary,$Bytes)
   [IO.File]::Replace($temporary,$Path,[NullString]::Value)
  }catch [UnauthorizedAccessException]{
   # Program Files can permit existing-file writes but deny parent FILE_ADD_FILE.
   # Keep directory ACLs intact; lock the existing file and compensate on failure.
   $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
   try{
    $saved=[IO.MemoryStream]::new()
    try{$stream.CopyTo($saved);$before=$saved.ToArray()}finally{$saved.Dispose()}
    try{
     $stream.Position=0;$stream.Write($Bytes,0,$Bytes.Length);$stream.SetLength($Bytes.Length);$stream.Flush($true)
     $stream.Position=0;$check=[IO.MemoryStream]::new()
     try{$stream.CopyTo($check);$written=$check.ToArray()}finally{$check.Dispose()}
     if((Get-EnhancementByteHash $written) -ne (Get-EnhancementByteHash $Bytes)){throw 'Display configuration write verification failed'}
    }catch{
     $failure=$_
     $stream.Position=0;$stream.Write($before,0,$before.Length);$stream.SetLength($before.Length);$stream.Flush($true)
     throw $failure
    }
   }finally{$stream.Dispose()}
  }
 }finally{if(Test-Path -LiteralPath $temporary){Remove-Item -LiteralPath $temporary -ErrorAction Stop}}
}
function Invoke-EnhancementDisplayTransaction([string]$Path,[byte[]]$Candidate,[bool]$Restore,[scriptblock]$Action) {
 $path=[IO.Path]::GetFullPath($Path)
 if($null -eq $Candidate -or $Candidate.Length -eq 0 -or $null -eq $Action){throw 'Display candidate and action are required'}
 $original=[IO.File]::ReadAllBytes($path);$originalHash=Get-EnhancementByteHash $original
 $candidateHash=Get-EnhancementByteHash $Candidate
 Write-EnhancementBytesAtomic $path $Candidate
 try{& $Action}finally{
  if($Restore){
   if(-not (Test-Path -LiteralPath $path -PathType Leaf)){throw 'Display configuration changed during verification'}
   $currentHash=Get-EnhancementByteHash ([IO.File]::ReadAllBytes($path))
   if($currentHash -ne $originalHash){
    if($currentHash -ne $candidateHash){throw 'Display configuration changed during verification; preserving external edit'}
    Write-EnhancementBytesAtomic $path $original
   }
  }
 }
}
Export-ModuleMember -Function Get-EnhancementUserPaths,Initialize-EnhancementUserSettings,New-EnhancementSettings,Test-EnhancementSettings,Convert-EnhancementSettings,Get-EnhancementRuntimeSettings,Read-EnhancementSettings,Write-EnhancementSettings,Get-EnhancementLaunchSpec,Invoke-EnhancementDisplayTransaction
