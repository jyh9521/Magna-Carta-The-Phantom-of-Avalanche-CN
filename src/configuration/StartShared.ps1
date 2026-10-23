param([ValidateSet('configured','baseline','render4k','wide4k','fps60','combined','motion','gamepad','motion-gamepad','texture','camera','camera-gamepad','maps','maps-gamepad')][string]$Recipe='configured',[switch]$VerifyOnly,[string]$DataRoot='',[string]$SettingsFile='',[switch]$WithoutFieldReturnHeight,[switch]$WithoutGuiParentGuard,[switch]$WithoutSceneLoading,[switch]$WithoutNativeLoading,[switch]$WithoutScaledFont,[switch]$CaptureException)
$ErrorActionPreference='Stop'
if($Recipe -in @('gamepad','motion-gamepad','camera','camera-gamepad','maps-gamepad')){throw 'This research recipe is archived; use Play.cmd'}
$runtimeRoot=$PSScriptRoot
$manifest=Get-Content -LiteralPath (Join-Path $runtimeRoot 'runtime.json') -Raw | ConvertFrom-Json
if($manifest.schema -ne 1){throw 'Unsupported shared runtime'}
if($DataRoot -and -not $VerifyOnly){throw 'Data override is only supported for migration preflight'}
$layout='data'
if($manifest.PSObject.Properties['data_root']){$layout=[string]$manifest.data_root}
if($layout -notin @('data','.')){throw 'Unsupported shared data layout'}
if(-not $DataRoot){$DataRoot=Join-Path $runtimeRoot $layout}
$game=(Resolve-Path -LiteralPath $DataRoot).Path
function Hash($p){$s=[IO.File]::OpenRead($p);$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash($s))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose();$s.Dispose()}}
foreach($p in $manifest.data.PSObject.Properties){if((Hash (Join-Path $game $p.Name)) -ne $p.Value){throw ('Game input changed: '+$p.Name)}}
foreach($p in $manifest.files.PSObject.Properties){if((Hash (Join-Path $runtimeRoot $p.Name)) -ne $p.Value){throw ('Runtime input changed: '+$p.Name)}}
Import-Module (Join-Path $runtimeRoot 'config/EnhancementSettings.psm1') -Force
if(-not $SettingsFile){$SettingsFile=Join-Path $runtimeRoot 'config/enhancements.json'}
$settings=Read-EnhancementSettings $SettingsFile
$selected=$manifest.recipes.$Recipe
if($selected.settings){$settings=Test-EnhancementSettings $selected.settings}
$schema=$settings.schema
$settings=Get-EnhancementRuntimeSettings $settings
$settings.native_gamepad=$false;$settings.free_view=$false
$cameraEnabled=$false
$module=$selected.module
if($module -eq 'configured'){
 $key=if($settings.motion60 -and $settings.native_gamepad){'combined'}elseif($settings.motion60 -or $settings.free_view){'motion'}elseif($settings.native_gamepad){'gamepad'}else{'display'}
 if($manifest.PSObject.Properties['configured_modules']){$module=$manifest.configured_modules.$key}else{$module=if($key -eq 'display'){'display'}else{'modern'}}
}
if($Recipe -eq 'configured' -and $schema -eq 2){$module='configuration'}
# FIELD_RETURN_DEFAULT_ROUTE: normal entries include the scoped fix; baseline retains its original module.
$fieldReturnEnabled=$false
if($manifest.PSObject.Properties['field_return_height']){
 $fix=$manifest.field_return_height
 if($fix.schema -ne 1 -or $fix.enabled -isnot [bool] -or $fix.module -ne 'field-return-height'){throw 'Invalid field return-height integration'}
 $fieldReturnEnabled=$fix.enabled -and $Recipe -ne 'baseline' -and -not $WithoutFieldReturnHeight
 if($fieldReturnEnabled){$module=$fix.module}
}
# GUI_PARENT_DEFAULT_ROUTE: startup bounds guard; not a scene-transition fix.
$guiParentEnabled=$false
if($manifest.PSObject.Properties['gui_parent_guard']){
 $fix=$manifest.gui_parent_guard
 if($fix.schema -ne 1 -or $fix.enabled -isnot [bool] -or $fix.module -ne 'gui-parent-guard'){throw 'Invalid GUI parent-guard integration'}
 $guiParentEnabled=$fix.enabled -and $Recipe -ne 'baseline' -and -not $WithoutGuiParentGuard
 if($guiParentEnabled){$module=$fix.module}
}
# SCENE_LOADING_DEFAULT_ROUTE: owned loading prelude before field cleanup; not a crash fix.
$sceneLoadingEnabled=$false
if($manifest.PSObject.Properties['scene_loading']){
 $fix=$manifest.scene_loading
 if($fix.schema -ne 1 -or $fix.enabled -isnot [bool] -or $fix.module -ne 'scene-loading'){throw 'Invalid scene-loading integration'}
 $sceneLoadingEnabled=$fix.enabled -and $Recipe -ne 'baseline' -and -not $WithoutSceneLoading
 if($sceneLoadingEnabled){$module=$fix.module}
}
# NATIVE_SCENE_LOADING_DEFAULT_ROUTE: reuse original FDI 0204 and native rendering, no replacement art.
$nativeLoadingEnabled=$false
if($manifest.PSObject.Properties['native_scene_loading']){
 $fix=$manifest.native_scene_loading
 if($fix.schema -ne 1 -or $fix.enabled -isnot [bool] -or $fix.module -ne 'native-loading' -or $sceneLoadingEnabled){throw 'Invalid native scene-loading integration'}
 $nativeLoadingEnabled=$fix.enabled -and $guiParentEnabled -and $Recipe -ne 'baseline' -and -not $WithoutNativeLoading
 if($nativeLoadingEnabled){$module=$fix.module}
}
# SCALED_FONT_DEFAULT_ROUTE: private 4x glyph textures; native measurements and pools retained.
$scaledFontEnabled=$false
if($manifest.PSObject.Properties['scaled_font']){
 $fix=$manifest.scaled_font
 if($fix.schema -isnot [int] -or $fix.schema -ne 1 -or $fix.enabled -isnot [bool] -or $fix.module -ne 'scaled-font' -or $fix.scale -isnot [int] -or $fix.scale -ne 4){throw 'Invalid scaled font integration'}
 $scaledFontEnabled=$fix.enabled -and $Recipe -ne 'baseline' -and -not $WithoutScaledFont
 if($scaledFontEnabled){$module=$fix.module}
}
$ini=Join-Path $game 'DDrawCompat-MagnaCarta.ini'
$known=@($manifest.profiles.PSObject.Properties.Value)
if((Hash $ini) -notin $known){throw 'Unknown active display configuration'}
$mutex=New-Object Threading.Mutex($false,('Local\MagnaCartaShared_'+(Hash (Join-Path $runtimeRoot 'runtime.json')).Substring(0,24)))
if(-not $mutex.WaitOne(0)){throw 'Another shared runtime entry is active'}
$environment=@{}
foreach($key in @('MC_ENCOUNTER_ON','MC_ENCOUNTER_OFF','MC_MOTION60_COMPLETE','MC_TITLE_BACKGROUND4K','MC_FREE_VIEW','MC_MAP_OVERLAY','MC_MAP_ASSETS','MC_WINDOWED','MC_WINDOW_RESOLUTION','MC_FIELD_RETURN_HEIGHT','MC_GUI_PARENT_GUARD','MC_SCENE_LOADING','MC_NATIVE_SCENE_LOADING','MC_SCALED_FONT','MC_SCALED_FONT_ASSETS')){$environment[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
try{
 foreach($p in (Get-CimInstance Win32_Process -Filter "Name='MagnaCarta.exe'")){
  if(-not $p.ExecutablePath -or [IO.Path]::GetFullPath($p.ExecutablePath) -eq (Join-Path $game 'MagnaCarta.exe')){throw 'Exit game before changing shared settings'}
 }
 $profile=[IO.File]::ReadAllBytes((Join-Path $runtimeRoot 'config/profile-base.bin'))
 . (Join-Path $runtimeRoot 'config/PrepareProfile.ps1')
 $profile=Convert-CompatibilityProfile $profile

 $cache=Join-Path $runtimeRoot 'cache'
 if(-not (Test-Path -LiteralPath $cache)){New-Item -ItemType Directory -Path $cache | Out-Null}
 # The native launcher requires a fresh log; the shared mutex owns this cache.
 # Verify-only must not destroy the previous session's diagnostic log.
 $log=Join-Path $cache 'profile.log'
 if(-not $VerifyOnly -and (Test-Path -LiteralPath $log)){
  $item=Get-Item -LiteralPath $log -Force
  if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unexpected shared log path type'}
  Remove-Item -LiteralPath $log -Force -ErrorAction Stop
 }
 [IO.File]::WriteAllBytes((Join-Path $cache 'profile.bin'),$profile)
 Invoke-EnhancementDisplayTransaction $ini ([IO.File]::ReadAllBytes((Join-Path $runtimeRoot ('config/profiles/'+$settings.display_profile+'.ini')))) ([bool]$VerifyOnly) {
 $labelsPath=Join-Path $runtimeRoot 'config/encounter-ui.json'
 if(Test-Path -LiteralPath $labelsPath){
  $labels=Get-Content -LiteralPath $labelsPath -Raw -Encoding UTF8|ConvertFrom-Json
  foreach($value in @($labels.on,$labels.off)){if($value -isnot [string] -or $value.Length -lt 1 -or $value.Length -ge 128){throw 'Invalid encounter status label'}}
  $env:MC_ENCOUNTER_ON=$labels.on;$env:MC_ENCOUNTER_OFF=$labels.off
 }else{$env:MC_ENCOUNTER_ON='Random encounters: ON [F5]';$env:MC_ENCOUNTER_OFF='Random encounters: OFF [F5]'}
 $env:MC_SCALED_FONT=if($scaledFontEnabled){'1'}else{'0'}
 $env:MC_SCALED_FONT_ASSETS=if($scaledFontEnabled){Join-Path $runtimeRoot 'fonts'}else{''}
 $env:MC_NATIVE_SCENE_LOADING=if($nativeLoadingEnabled){'1'}else{'0'}
 $env:MC_SCENE_LOADING=if($sceneLoadingEnabled){'1'}else{'0'}
 $env:MC_GUI_PARENT_GUARD=if($guiParentEnabled){'1'}else{'0'}
 $env:MC_FIELD_RETURN_HEIGHT=if($fieldReturnEnabled){'1'}else{'0'}
 $env:MC_WINDOW_RESOLUTION=if($schema -eq 2 -and $settings.window_mode -eq 'windowed'){$settings.window_resolution}else{''}
 $env:MC_WINDOWED=if($settings.window_mode -eq 'windowed'){'1'}else{'0'}
 $env:MC_MOTION60_COMPLETE=if($settings.motion60 -or $cameraEnabled){'1'}else{'0'}
 $env:MC_TITLE_BACKGROUND4K='1'
 $env:MC_FREE_VIEW=if($cameraEnabled){'1'}else{'0'}
 $env:MC_MAP_OVERLAY=if($selected.maps){'1'}else{'0'}
 $env:MC_MAP_ASSETS=if($selected.maps){Join-Path $runtimeRoot 'maps'}else{''}
 $args=@('--workspace',$game,'--shim',(Join-Path $runtimeRoot ('modules/'+$module+'.dll')),'--profile',(Join-Path $cache 'profile.bin'),'--log',$log,'--native-text-step','--system-messages','--focus-guard','--display-profile',$settings.display_profile)
 if($settings.native_gamepad){$args+='--native-gamepad'}elseif($selected.maps -or $cameraEnabled){$args+='--input-passthrough'}
 if($selected.texture){$args+='--texture-lifetime'}
 if($CaptureException){$args+='--capture-exception'}
 if($VerifyOnly){$args+='--verify-only'}
 & (Join-Path $runtimeRoot 'modules/workspace_launcher.exe') @args 1>(Join-Path $cache 'launcher.stdout.txt') 2>(Join-Path $cache 'launcher.stderr.txt')
 $code=$LASTEXITCODE
 if($code -ne 0){throw ('Shared launcher exit='+$code+'; see runtime/cache')}
 Write-Output ('SHARED_RUNTIME PASS recipe='+$Recipe+' module='+$module+' verify_only='+[bool]$VerifyOnly+' data='+$game+' field_return_height='+[bool]$fieldReturnEnabled+' gui_parent_guard='+[bool]$guiParentEnabled+' scaled_font='+[bool]$scaledFontEnabled)
 }
}finally{
 foreach($key in $environment.Keys){[Environment]::SetEnvironmentVariable($key,$environment[$key],'Process')}
 $mutex.ReleaseMutex();$mutex.Dispose()
}
