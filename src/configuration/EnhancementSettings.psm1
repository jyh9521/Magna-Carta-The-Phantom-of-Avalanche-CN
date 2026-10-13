Set-StrictMode -Version Latest
$profiles=@('baseline','render4k','wide4k','fps60','combined')
function New-EnhancementSettings {
 [pscustomobject]@{schema=1;display_profile='wide4k';motion60=$false;native_gamepad=$false}
}
function Test-EnhancementSettings($Value) {
 if($null -eq $Value){throw 'Settings must be an object'}
 $names=@($Value.PSObject.Properties.Name|Sort-Object)
 if(($names -join ',') -ne 'display_profile,motion60,native_gamepad,schema'){throw 'Unknown or missing setting fields'}
 if($Value.schema -ne 1 -or $Value.schema -is [bool] -or $Value.schema -is [string]){throw 'Unsupported settings schema'}
 if($Value.display_profile -isnot [string] -or $Value.display_profile -notin $profiles){throw 'Unsupported display profile'}
 if($Value.motion60 -isnot [bool] -or $Value.native_gamepad -isnot [bool]){throw 'Feature switches must be boolean'}
 if($Value.motion60 -and $Value.display_profile -notin @('fps60','combined')){throw 'Motion interpolation requires a 60Hz profile'}
 $Value
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
Export-ModuleMember -Function New-EnhancementSettings,Test-EnhancementSettings,Read-EnhancementSettings,Write-EnhancementSettings
