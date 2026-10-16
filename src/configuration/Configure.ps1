param([switch]$SelfTest,[string]$SettingsFile='',[string]$PreviewPath='',[switch]$VerifyEntry,[double]$PreviewScale=1)
$ErrorActionPreference='Stop'
if($VerifyEntry -and -not $SelfTest){throw 'VerifyEntry is only supported with SelfTest'}
if($VerifyEntry -and (-not $SettingsFile -or [IO.Path]::GetFullPath($SettingsFile) -eq [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'enhancements.json')))){throw 'VerifyEntry requires a separate explicit fixture settings path'}
Import-Module (Join-Path $PSScriptRoot 'EnhancementSettings.psm1') -Force
Add-Type -AssemblyName PresentationFramework,PresentationCore,WindowsBase
if(-not $SettingsFile){$SettingsFile=Join-Path $PSScriptRoot 'enhancements.json'}
$text=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'configuration-ui.json') -Raw -Encoding UTF8|ConvertFrom-Json
$settings=Read-EnhancementSettings $SettingsFile
$markup=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'Configure.xaml') -Raw -Encoding UTF8
if(-not [Windows.SystemParameters]::ClientAreaAnimation){$markup=[regex]::Replace($markup,'Duration="[^"]+"','Duration="0:0:0"')}
[xml]$xaml=$markup
$form=[Windows.Markup.XamlReader]::Load([Xml.XmlNodeReader]::new($xaml))
$form.Title=$text.title
if(-not $SelfTest){$form.Width=[Math]::Min($form.Width,[Windows.SystemParameters]::WorkArea.Width-32);$form.Height=[Math]::Min($form.Height,[Windows.SystemParameters]::WorkArea.Height-48)}
$labels=@{Eyebrow='eyebrow';Subtitle='subtitle';Quality='quality';DisplayTitle='display';ResolutionLabel='resolution';ResolutionNote='resolution_note';WindowLabel='window_mode';FrameLabel='frame_rate';FrameNote='frame_note';InputTitle='input_title';GamepadLabel='gamepad';GamepadNote='gamepad_note';CameraLabel='free_view';CameraNote='free_view_note';Pending='pending'}
foreach($name in $labels.Keys){$form.FindName($name).Text=$text.($labels[$name])}
$logo=Join-Path $PSScriptRoot 'configuration-logo.png'
if(-not (Test-Path -LiteralPath $logo -PathType Leaf)){throw 'Configuration logo is missing'}
$bitmap=[Windows.Media.Imaging.BitmapImage]::new();$bitmap.BeginInit();$bitmap.CacheOption='OnLoad';$bitmap.UriSource=[Uri]::new($logo);$bitmap.EndInit();$bitmap.Freeze()
$form.FindName('LogoImage').Source=$bitmap
$author=$form.FindName('AuthorLink');$author.Inlines.Add([string]$text.author);$author.NavigateUri=[Uri]$text.author_url
$author.ToolTip=$text.author_url
$author.add_RequestNavigate({param($sender,$event);if($event.Uri.AbsoluteUri -eq $text.author_url){Start-Process $event.Uri.AbsoluteUri};$event.Handled=$true})
$script:groups=[ordered]@{}
$script:loading=$true
$panels=[ordered]@{resolution='ResolutionChoices';window_mode='WindowChoices';frame_rate='FrameChoices';native_gamepad='GamepadChoices';free_view='CameraChoices'}
$status=$form.FindName('Status')
foreach($field in $panels.Keys){
 $buttons=[ordered]@{}
 foreach($option in $text.choices.$field.PSObject.Properties){
  $radio=[Windows.Controls.RadioButton]::new();$radio.Style=$form.Resources['Segment']
  $radio.GroupName=$field;$radio.Tag=$option.Name;$radio.Content=$option.Value
  [Windows.Automation.AutomationProperties]::SetName($radio,($text.choices.$field.($option.Name)))
  $radio.add_Checked({if(-not $script:loading){$status.Text=$text.dirty}})
  $null=$form.FindName($panels[$field]).Children.Add($radio);$buttons[$option.Name]=$radio
 }
 $script:groups[$field]=$buttons
}
$save=$form.FindName('Save');$defaults=$form.FindName('Defaults');$verify=$form.FindName('Verify');$play=$form.FindName('Play')
$save.Content=$text.save;$defaults.Content=$text.defaults;$verify.Content=$text.verify;$play.Content=$text.play
function Set-Controls($s){
 $s=Convert-EnhancementSettings $s;$script:loading=$true
 try{foreach($field in $script:groups.Keys){$key=([string]$s.$field).ToLowerInvariant();$script:groups[$field][$key].IsChecked=$true}}finally{$script:loading=$false}
}
function Get-Controls{
 $value=[ordered]@{schema=2}
 foreach($field in $script:groups.Keys){
  $selected=@($script:groups[$field].Values|Where-Object {$_.IsChecked})
  if($selected.Count -ne 1){throw ('Exactly one choice is required: '+$field)}
  $raw=[string]$selected[0].Tag
  $value[$field]=switch($field){'frame_rate'{[int]$raw};'native_gamepad'{[bool]::Parse($raw)};'free_view'{[bool]::Parse($raw)};default{$raw}}
 }
 Test-EnhancementSettings ([pscustomobject]$value)
}
function Notify([string]$message){
 $status.Text=$message
 if([Windows.SystemParameters]::ClientAreaAnimation){
  $animation=[Windows.Media.Animation.DoubleAnimation]::new(0.35,1,[TimeSpan]::FromMilliseconds(220));$status.BeginAnimation([Windows.UIElement]::OpacityProperty,$animation)
 }
}
Set-Controls $settings;$status.Text=$text.ready
function Report-Error($error){Notify ($text.error+': '+$error.Exception.Message)}
$save.add_Click({try{$null=Write-EnhancementSettings $SettingsFile (Get-Controls);Notify $text.saved}catch{Report-Error $_}})
$defaults.add_Click({try{$s=New-EnhancementSettings;$null=Write-EnhancementSettings $SettingsFile $s;Set-Controls $s;Notify $text.default_note}catch{Report-Error $_}})
$script:child=$null
function Set-Busy([bool]$busy){foreach($b in @($save,$defaults,$verify,$play)+@($script:groups.Values|ForEach-Object {$_.Values})){$b.IsEnabled=-not $busy}}
function Run-Entry([bool]$Check){
 $launch=Get-EnhancementLaunchSpec $PSScriptRoot $SettingsFile $Check
 $null=Write-EnhancementSettings $SettingsFile (Get-Controls)
 $arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$launch.Entry)+$launch.Arguments
 $arguments=@($arguments|ForEach-Object {'"'+$_+'"'})
 $script:launchLogPath=$launch.LogPath
 $script:child=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru
 Set-Busy $true;Notify $text.running
}
$verify.add_Click({try{Run-Entry $true}catch{Report-Error $_}})
$play.add_Click({try{Run-Entry $false}catch{Report-Error $_}})
$timer=[Windows.Threading.DispatcherTimer]::new();$timer.Interval=[TimeSpan]::FromMilliseconds(400)
$timer.add_Tick({if($script:child -and $script:child.HasExited){
 Notify $(if($script:child.ExitCode -eq 0){[string]::Format($text.finished,$script:launchLogPath)}else{[string]::Format($text.failed,$script:child.ExitCode,$script:launchLogPath)})
 Set-Busy $false;$script:child.Dispose();$script:child=$null
}})
$form.add_Closing({param($sender,$event);if($script:child -and -not $script:child.HasExited){$event.Cancel=$true;Notify $text.running}})
$form.add_Loaded({
 if([Windows.SystemParameters]::ClientAreaAnimation){
  $root=$form.FindName('ContentRoot');$fade=[Windows.Media.Animation.DoubleAnimation]::new(0,1,[TimeSpan]::FromMilliseconds(320));$root.BeginAnimation([Windows.UIElement]::OpacityProperty,$fade)
  $slide=[Windows.Media.Animation.DoubleAnimation]::new(16,0,[TimeSpan]::FromMilliseconds(360));$ease=[Windows.Media.Animation.CubicEase]::new();$ease.EasingMode='EaseOut';$slide.EasingFunction=$ease
  $root.RenderTransform.BeginAnimation([Windows.Media.TranslateTransform]::YProperty,$slide)
 }
})
if($SelfTest){
 $checks=0
 $surface=$form.Content;$surface.Measure([Windows.Size]::new($form.Width-48,$form.Height-32));$surface.Arrange([Windows.Rect]::new(0,0,$form.Width-48,$form.Height-32));$surface.UpdateLayout()
 foreach($field in $script:groups.Keys){
  foreach($key in $script:groups[$field].Keys){
   $script:groups[$field][$key].IsChecked=$true;$v=Get-Controls
   if(([string]$v.$field).ToLowerInvariant() -ne $key){throw ('Selection mismatch: '+$field)};$checks++
  }
 }
 # 使用真实模板与Dispatcher验证选择态颜色过渡，不创建可见窗口。
 $radio=$script:groups.resolution['1080p'];$radio.ApplyTemplate()|Out-Null
 $radio.IsChecked=$false
 $clock=[Diagnostics.Stopwatch]::StartNew();while($clock.ElapsedMilliseconds -lt 250){$form.Dispatcher.Invoke([Windows.Threading.DispatcherPriority]::Background,[Action]{});Start-Sleep -Milliseconds 10}
 $shell=$radio.Template.FindName('Shell',$radio);$before=$shell.Background.Color.ToString();$radio.IsChecked=$true
 $clock.Restart();while($clock.ElapsedMilliseconds -lt 100){$form.Dispatcher.Invoke([Windows.Threading.DispatcherPriority]::Background,[Action]{});Start-Sleep -Milliseconds 10}
 $middle=$shell.Background.Color.ToString()
 $clock.Restart();while($clock.ElapsedMilliseconds -lt 260){$form.Dispatcher.Invoke([Windows.Threading.DispatcherPriority]::Background,[Action]{});Start-Sleep -Milliseconds 10}
 $after=$shell.Background.Color.ToString()
 if($before -eq $after){throw 'Selection state did not change template color'}
 if([Windows.SystemParameters]::ClientAreaAnimation -and ($middle -eq $before -or $middle -eq $after)){throw 'Selection animation has no intermediate state'}
 Write-Output ('ENHANCEMENT_MOTION_SELFTEST PASS before='+$before+' middle='+$middle+' after='+$after+' reduced_motion='+(-not [Windows.SystemParameters]::ClientAreaAnimation))
 Set-Controls $settings
 if($form.IsVisible){throw 'Self-test must not show a window'}
 Set-Busy $true;foreach($b in $script:groups.resolution.Values){if($b.IsEnabled){throw 'Busy selection remains enabled'}};Set-Busy $false
 if($author.NavigateUri.AbsoluteUri -ne $text.author_url -or $bitmap.PixelWidth -lt 100){throw 'Brand assets mismatch'}
 if($VerifyEntry){
  $script:groups.resolution['4k'].IsChecked=$true;$script:groups.frame_rate['30'].IsChecked=$true;$script:groups.native_gamepad['true'].IsChecked=$true
  Run-Entry $true
  if(-not $script:child.WaitForExit(30000)){throw 'Verify-only entry timed out'}
  $script:child.Refresh();if($script:child.ExitCode -ne 0){throw ('Verify-only entry failed: '+$script:child.ExitCode)}
  $script:child.Dispose();$script:child=$null;Set-Busy $false
  Write-Output 'ENHANCEMENT_GUI_ENTRY_SELFTEST PASS verify_only=true visible=false game_started=false'
 }
 if($PreviewPath){
  if($PreviewScale -lt 1 -or $PreviewScale -gt 2){throw 'Preview scale out of range'}
  Set-Controls $settings;$status.Text=$text.ready;$surface=$form.Content;$surface.Margin=0;$surface.Background=$form.Background
  $width=$form.Width-48;$height=$form.Height-32
  $surface.Measure([Windows.Size]::new($width,$height));$surface.Arrange([Windows.Rect]::new(0,0,$width,$height));$surface.UpdateLayout()
  # 离屏布局等待选择态动画收敛；不显示窗口或改变桌面。
  $clock=[Diagnostics.Stopwatch]::StartNew()
  while($clock.ElapsedMilliseconds -lt 400){$form.Dispatcher.Invoke([Windows.Threading.DispatcherPriority]::Background,[Action]{});Start-Sleep -Milliseconds 20}
  $render=[Windows.Media.Imaging.RenderTargetBitmap]::new([int]($form.Width*$PreviewScale),[int]($form.Height*$PreviewScale),96*$PreviewScale,96*$PreviewScale,[Windows.Media.PixelFormats]::Pbgra32)
  $visual=[Windows.Media.DrawingVisual]::new();$draw=$visual.RenderOpen()
  $draw.DrawRectangle($form.Background,$null,[Windows.Rect]::new(0,0,$form.Width,$form.Height))
  $draw.DrawRectangle([Windows.Media.VisualBrush]::new($surface),$null,[Windows.Rect]::new(24,18,$width,$height));$draw.Close()
  $render.Render($visual);$encoder=[Windows.Media.Imaging.PngBitmapEncoder]::new();$encoder.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($render))
  $stream=[IO.File]::Create([IO.Path]::GetFullPath($PreviewPath));try{$encoder.Save($stream)}finally{$stream.Dispose()}
 }
 Write-Output ('ENHANCEMENT_GUI_SELFTEST PASS choices='+$checks+' groups=5 framework=WPF visible=false game_started=false')
 $form.Close();exit 0
}
$timer.Start();try{$null=$form.ShowDialog()}finally{$timer.Stop();if($script:child){$script:child.Dispose()}}
