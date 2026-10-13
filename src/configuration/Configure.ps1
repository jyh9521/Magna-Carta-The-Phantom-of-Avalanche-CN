param([switch]$SelfTest,[string]$SettingsFile='',[string]$PreviewPath='')
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'EnhancementSettings.psm1') -Force
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
if(-not $SettingsFile){$SettingsFile=Join-Path $PSScriptRoot 'enhancements.json'}
$text=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'configuration-ui.json') -Raw -Encoding UTF8|ConvertFrom-Json
$settings=Read-EnhancementSettings $SettingsFile
$keys=@('baseline','render4k','wide4k','fps60','combined')
$form=New-Object Windows.Forms.Form
$form.Text=$text.title;$form.ClientSize=New-Object Drawing.Size(630,450)
$form.StartPosition='CenterScreen';$form.FormBorderStyle='FixedDialog';$form.MaximizeBox=$false
$form.Font=New-Object Drawing.Font('Segoe UI',10);$form.AutoScaleMode='Dpi'
function Label($value,$x,$y,$width,$height){$l=New-Object Windows.Forms.Label;$l.Text=$value;$l.SetBounds($x,$y,$width,$height);$form.Controls.Add($l);$l}
$null=Label $text.display 22 22 120 28
$profile=New-Object Windows.Forms.ComboBox;$profile.DropDownStyle='DropDownList';$profile.SetBounds(22,55,580,32)
foreach($key in $keys){$null=$profile.Items.Add($text.$key)};$form.Controls.Add($profile)
$motion=New-Object Windows.Forms.CheckBox;$motion.Text=$text.motion;$motion.SetBounds(22,108,580,30);$form.Controls.Add($motion)
$gamepad=New-Object Windows.Forms.CheckBox;$gamepad.Text=$text.gamepad;$gamepad.SetBounds(22,145,580,30);$form.Controls.Add($gamepad)
$null=Label $text.quality 22 190 580 28
$warning=Label $text.pending 22 224 580 42;$warning.ForeColor=[Drawing.Color]::DarkOrange
$null=Label ($text.controls.Replace('\n',"`n")) 22 270 580 85
$status=Label $text.default_note 22 407 580 30
function Button($label,$x){$b=New-Object Windows.Forms.Button;$b.Text=$label;$b.SetBounds($x,365,138,34);$form.Controls.Add($b);$b}
$save=Button $text.save 22;$defaults=Button $text.defaults 169;$verify=Button $text.verify 316;$play=Button $text.play 463
function Set-Controls($s){$profile.SelectedIndex=[array]::IndexOf($keys,$s.display_profile);$motion.Checked=$s.motion60;$gamepad.Checked=$s.native_gamepad}
function Get-Controls{Test-EnhancementSettings ([pscustomobject]@{schema=1;display_profile=$keys[$profile.SelectedIndex];motion60=[bool]$motion.Checked;native_gamepad=[bool]$gamepad.Checked})}
$profile.add_SelectedIndexChanged({$motion.Enabled=$profile.SelectedIndex -in @(3,4);if(-not $motion.Enabled){$motion.Checked=$false}})
Set-Controls $settings
function Report-Error($error){[Windows.Forms.MessageBox]::Show($error.Exception.Message,$text.error,'OK','Error')|Out-Null}
$save.add_Click({try{$null=Write-EnhancementSettings $SettingsFile (Get-Controls);$status.Text=$text.saved}catch{Report-Error $_}})
$defaults.add_Click({try{$s=New-EnhancementSettings;$null=Write-EnhancementSettings $SettingsFile $s;Set-Controls $s;$status.Text=$text.default_note}catch{Report-Error $_}})
$script:child=$null
function Run-Entry([bool]$Check){
 $null=Write-EnhancementSettings $SettingsFile (Get-Controls)
 $entry=Join-Path $PSScriptRoot 'StartEnhanced.ps1'
 $args=@('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$entry+'"'),'-SettingsFile',('"'+$SettingsFile+'"'))
 if($Check){$args+='-VerifyOnly'}
 $script:child=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList $args -WindowStyle Hidden -PassThru
 $save.Enabled=$defaults.Enabled=$verify.Enabled=$play.Enabled=$profile.Enabled=$motion.Enabled=$gamepad.Enabled=$false
 $status.Text=$text.running
}
$verify.add_Click({try{Run-Entry $true}catch{Report-Error $_}})
$play.add_Click({try{Run-Entry $false}catch{Report-Error $_}})
$timer=New-Object Windows.Forms.Timer;$timer.Interval=1000
$timer.add_Tick({if($script:child -and $script:child.HasExited){$status.Text=if($script:child.ExitCode -eq 0){$text.finished}else{[string]::Format($text.failed,$script:child.ExitCode)};$save.Enabled=$defaults.Enabled=$verify.Enabled=$play.Enabled=$profile.Enabled=$gamepad.Enabled=$true;$motion.Enabled=$profile.SelectedIndex -in @(3,4);$script:child.Dispose();$script:child=$null}})
if($SelfTest){
 if($profile.SelectedIndex -ne [array]::IndexOf($keys,$settings.display_profile)){throw 'GUI selection mismatch'}
 $profile.SelectedIndex=4;$motion.Checked=$true;$gamepad.Checked=$true;$v=Get-Controls
 if($v.display_profile -ne 'combined' -or -not $v.motion60 -or -not $v.native_gamepad){throw 'GUI values mismatch'}
 $profile.SelectedIndex=2;if($motion.Enabled -or $motion.Checked){throw 'Unsupported motion switch remains enabled'}
 if($form.Visible){throw 'Self-test must not show a window'}
 if($PreviewPath){
  Set-Controls $settings;$form.CreateControl();$bitmap=New-Object Drawing.Bitmap($form.ClientSize.Width,$form.ClientSize.Height);$graphics=[Drawing.Graphics]::FromImage($bitmap)
  try {
   $graphics.Clear($form.BackColor)
   foreach($control in $form.Controls){$tile=New-Object Drawing.Bitmap($control.Width,$control.Height);try{$control.DrawToBitmap($tile,(New-Object Drawing.Rectangle(0,0,$control.Width,$control.Height)));$graphics.DrawImageUnscaled($tile,$control.Left,$control.Top)}finally{$tile.Dispose()}}
   $bitmap.Save([IO.Path]::GetFullPath($PreviewPath),[Drawing.Imaging.ImageFormat]::Png)
  }finally{$graphics.Dispose();$bitmap.Dispose()}
 }
 Write-Output ('ENHANCEMENT_GUI_SELFTEST PASS controls='+$form.Controls.Count+' display_choices=5 feature_gating=true visible=false game_started=false')
 $form.Dispose();exit 0
}
$timer.Start();try{[Windows.Forms.Application]::EnableVisualStyles();[void]$form.ShowDialog()}finally{$timer.Stop();$timer.Dispose();$form.Dispose()}
