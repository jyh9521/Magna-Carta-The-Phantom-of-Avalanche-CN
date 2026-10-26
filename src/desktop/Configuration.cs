using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;
using System.Windows.Markup;
using System.Windows.Threading;
namespace DesktopRuntime {
 internal sealed class Configuration {
  readonly Window window;readonly Dictionary<string,object> text;readonly string root,settingsFile;
  readonly Dictionary<string,Dictionary<string,RadioButton>> groups=new Dictionary<string,Dictionary<string,RadioButton>>();
  readonly ComboBox windowSize;readonly TextBlock status;readonly Button save,defaults,verify,play;readonly DispatcherTimer timer;
  bool loading;Process child;DateTime childStartedUtc;
  T Find<T>(string name) where T:class {var control=window.FindName(name) as T;if(control==null)throw new InvalidDataException("Missing UI component: "+name);return control;}
  string Text(string key){return Data.Text(text,key);}
  BitmapImage Image(string resource){var b=new BitmapImage();using(var s=new MemoryStream(Data.Bytes(resource))){b.BeginInit();b.CacheOption=BitmapCacheOption.OnLoad;b.StreamSource=s;b.EndInit();b.Freeze();}return b;}
  Configuration(string installation,string settings,bool self) {
   root=installation;text=Data.Resource("config/configuration-ui.json");settingsFile=settings??(self?Settings.PathFor(root):Settings.Initialize(root));
   string markup=Encoding.UTF8.GetString(Data.Bytes("config/Configure.xaml")).TrimStart('\ufeff');if(!SystemParameters.ClientAreaAnimation)markup=Regex.Replace(markup,"Duration=\"[^\"]+\"","Duration=\"0:0:0\"");
   using(var s=new MemoryStream(Encoding.UTF8.GetBytes(markup)))window=(Window)XamlReader.Load(s);
   window.Title=Text("title");using(var s=new MemoryStream(Data.Bytes("MC.ico")))window.Icon=BitmapFrame.Create(s,BitmapCreateOptions.None,BitmapCacheOption.OnLoad);
   if(!self){window.Width=Math.Max(window.MinWidth,Math.Min(window.Width,SystemParameters.WorkArea.Width-32));window.Height=Math.Max(window.MinHeight,Math.Min(window.Height,SystemParameters.WorkArea.Height-48));}
   string[] names={"Eyebrow","Subtitle","DisplayTitle","ResolutionLabel","ResolutionNote","WindowLabel","WindowResolutionLabel","WindowResolutionNote","FrameLabel","FrameNote","Pending"};
   string[] keys={"eyebrow","subtitle","display","resolution","resolution_note","window_mode","window_resolution","window_resolution_note","frame_rate","frame_note","pending"};
   for(int i=0;i<names.Length;i++)Find<TextBlock>(names[i]).Text=Text(keys[i]);Find<Image>("LogoImage").Source=Image("config/configuration-logo.png");
   var author=Find<Hyperlink>("AuthorLink");author.Inlines.Add(Text("author"));var uri=new Uri(Text("author_url"));if(uri.Scheme!="https")throw new InvalidDataException("Author link must use HTTPS");author.NavigateUri=uri;author.ToolTip=uri.AbsoluteUri;author.RequestNavigate+=(s,e)=>{if(e.Uri==uri)Process.Start(new ProcessStartInfo(uri.AbsoluteUri){UseShellExecute=true});e.Handled=true;};
   status=Find<TextBlock>("Status");loading=true;var choices=Data.Object(text["choices"]);
   string[] fields={"resolution","window_mode","frame_rate"};string[] panels={"ResolutionChoices","WindowChoices","FrameChoices"};
   for(int i=0;i<fields.Length;i++){string field=fields[i];var buttons=new Dictionary<string,RadioButton>();foreach(var option in Data.Object(choices[field])){
     var radio=new RadioButton{Style=(Style)window.Resources["Segment"],GroupName=field,Tag=option.Key,Content=option.Value};System.Windows.Automation.AutomationProperties.SetName(radio,(string)option.Value);
     radio.Checked+=(s,e)=>{if(!loading){Notify(Text("dirty"));WindowVisibility();}};Find<Panel>(panels[i]).Children.Add(radio);buttons.Add(option.Key,radio);
    }groups.Add(field,buttons);}
   windowSize=Find<ComboBox>("WindowResolutionChoices");foreach(var option in Data.Object(choices["window_resolution"]))windowSize.Items.Add(new ComboBoxItem{Tag=option.Key,Content=option.Value});
   System.Windows.Automation.AutomationProperties.SetName(windowSize,Text("window_resolution"));windowSize.SelectionChanged+=(s,e)=>{if(!loading)Notify(Text("dirty"));};
   save=Find<Button>("Save");defaults=Find<Button>("Defaults");verify=Find<Button>("Verify");play=Find<Button>("Play");save.Content=Text("save");defaults.Content=Text("defaults");verify.Content=Text("verify");play.Content=Text("play");
   save.Click+=(s,e)=>Guard(()=>{Settings.Write(settingsFile,Controls());Notify(Text("saved"));});
   defaults.Click+=(s,e)=>Guard(()=>{var d=Settings.Defaults();Settings.Write(settingsFile,d);SetControls(d);Notify(Text("default_note"));});
   verify.Click+=(s,e)=>Guard(()=>Launch(true));play.Click+=(s,e)=>Guard(()=>Launch(false));
   timer=new DispatcherTimer{Interval=TimeSpan.FromMilliseconds(400)};timer.Tick+=(s,e)=>{if(child!=null&&child.HasExited){Notify(child.ExitCode==0?String.Format(Text("finished"),new UserPaths(root).Cache):LaunchDiagnostics.Failure(new UserPaths(root).Cache,child.ExitCode,childStartedUtc));child.Dispose();child=null;Busy(false);}};
   window.Closing+=(s,e)=>{if(child!=null&&!child.HasExited){e.Cancel=true;Notify(Text("running"));}};
   window.Loaded+=(s,e)=>{if(SystemParameters.ClientAreaAnimation){var content=Find<FrameworkElement>("ContentRoot");content.BeginAnimation(UIElement.OpacityProperty,new DoubleAnimation(0,1,TimeSpan.FromMilliseconds(320)));var slide=new DoubleAnimation(16,0,TimeSpan.FromMilliseconds(360)){EasingFunction=new CubicEase{EasingMode=EasingMode.EaseOut}};content.RenderTransform.BeginAnimation(TranslateTransform.YProperty,slide);}};
   SetControls(Settings.Read(settingsFile));Notify(Text("ready"));
  }
  void WindowVisibility(){Find<StackPanel>("WindowResolutionPanel").Visibility=groups["window_mode"]["windowed"].IsChecked==true?Visibility.Visible:Visibility.Collapsed;}
  void SetControls(Dictionary<string,object> source){var s=Settings.Convert(source);loading=true;try{foreach(var field in groups.Keys)groups[field][s[field].ToString().ToLowerInvariant()].IsChecked=true;windowSize.SelectedItem=windowSize.Items.Cast<ComboBoxItem>().Single(x=>(string)x.Tag==Data.Text(s,"window_resolution"));WindowVisibility();}finally{loading=false;}}
  Dictionary<string,object> Controls(){var d=new Dictionary<string,object>{{"schema",2},{"native_gamepad",false},{"free_view",false}};foreach(var group in groups){var choice=group.Value.Values.Single(x=>x.IsChecked==true);string value=(string)choice.Tag;d[group.Key]=group.Key=="frame_rate"?(object)Int32.Parse(value):value;}d["window_resolution"]=(string)((ComboBoxItem)windowSize.SelectedItem).Tag;return Settings.Validate(d);}
  void Notify(string message){status.Text=message;if(SystemParameters.ClientAreaAnimation)status.BeginAnimation(UIElement.OpacityProperty,new DoubleAnimation(.35,1,TimeSpan.FromMilliseconds(220)));}
  void Guard(Action action){try{action();}catch(Exception e){Notify(Text("error")+": "+e.Message);}}
  void Busy(bool value){foreach(var button in new Control[]{save,defaults,verify,play,windowSize})button.IsEnabled=!value;foreach(var group in groups.Values)foreach(var radio in group.Values)radio.IsEnabled=!value;}
  void Launch(bool check){Settings.Write(settingsFile,Controls());var args=new List<string>{"--settings-file",settingsFile};if(check)args.Add("--verify-only");
   childStartedUtc=DateTime.UtcNow;child=Process.Start(new ProcessStartInfo(Data.Located(root,"Game.exe"),String.Join(" ",args.Select(Data.Quote))){UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden,WorkingDirectory=root});Busy(true);Notify(Text("running"));}
  void WaitAnimation(int milliseconds){var watch=Stopwatch.StartNew();while(watch.ElapsedMilliseconds<milliseconds){window.Dispatcher.Invoke(DispatcherPriority.Background,new Action(()=>{}));System.Threading.Thread.Sleep(10);}}
  void Render(string path){var surface=(FrameworkElement)window.Content;surface.Margin=new Thickness(0);double w=window.Width-48,h=window.Height-32;surface.Measure(new Size(w,h));surface.Arrange(new Rect(0,0,w,h));surface.UpdateLayout();WaitAnimation(400);
   var scroll=((Grid)window.Content).Children.OfType<ScrollViewer>().Single();if(Data.Text(Controls(),"window_mode")!="windowed"&&scroll.ScrollableHeight>.5)throw new Exception("Default layout requires scrolling");
   var bitmap=new RenderTargetBitmap((int)window.Width,(int)window.Height,96,96,PixelFormats.Pbgra32);var visual=new DrawingVisual();using(var draw=visual.RenderOpen()){draw.DrawRectangle(window.Background,null,new Rect(0,0,window.Width,window.Height));draw.DrawRectangle(new VisualBrush(surface),null,new Rect(24,18,w,h));}bitmap.Render(visual);var encoder=new PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap));using(var file=File.Create(path))encoder.Save(file);
  }
  void CheckHeader(){
   var header=Find<Grid>("HeaderGrid");var logo=Find<Image>("LogoImage");
   var center=logo.TransformToAncestor(header).Transform(new Point(logo.ActualWidth/2,logo.ActualHeight/2));
   if(header.ActualWidth<=0||Math.Abs(center.X-header.ActualWidth/2)>.5||Math.Abs(center.Y-header.ActualHeight/2)>.5||window.FindName("Quality")!=null)throw new Exception("Header logo alignment or obsolete note mismatch");
   Console.WriteLine("COMPILED_HEADER PASS centered=true quality_note=absent");
  }
  void SelfTest(string preview){window.RaiseEvent(new RoutedEventArgs(FrameworkElement.LoadedEvent));int count=0;var original=Controls();foreach(var group in groups)foreach(var option in group.Value){option.Value.IsChecked=true;if(Controls()[group.Key].ToString()!=option.Key)throw new Exception("Selection roundtrip failed");count++;}
   groups["window_mode"]["windowed"].IsChecked=true;if(Find<StackPanel>("WindowResolutionPanel").Visibility!=Visibility.Visible)throw new Exception("Window size hidden");foreach(ComboBoxItem option in windowSize.Items){windowSize.SelectedItem=option;if(Data.Text(Controls(),"window_resolution")!=(string)option.Tag)throw new Exception("Window size roundtrip failed");count++;}
   groups["window_mode"]["borderless"].IsChecked=true;if(Find<StackPanel>("WindowResolutionPanel").Visibility!=Visibility.Collapsed)throw new Exception("Window size not hidden");Busy(true);if(windowSize.IsEnabled||groups["resolution"].Values.Any(x=>x.IsEnabled))throw new Exception("Busy controls active");Busy(false);SetControls(original);
   var surface=(FrameworkElement)window.Content;surface.Measure(new Size(window.Width-48,window.Height-32));surface.Arrange(new Rect(0,0,window.Width-48,window.Height-32));surface.UpdateLayout();
   var radio=groups["resolution"]["1080p"];radio.ApplyTemplate();radio.IsChecked=false;WaitAnimation(250);var shell=(Border)radio.Template.FindName("Shell",radio);var before=((SolidColorBrush)shell.Background).Color;radio.IsChecked=true;WaitAnimation(350);var after=((SolidColorBrush)shell.Background).Color;if(before==after)throw new Exception("Selection color transition missing");SetControls(original);Notify(Text("ready"));
   if(window.IsVisible||window.Icon==null||Find<Image>("LogoImage").Source==null)throw new Exception("Headless UI / branding mismatch");if(preview!=null)Render(preview);CheckHeader();
   Console.WriteLine("COMPILED_CONFIGURE PASS choices="+count+" icon=embedded resources=embedded visible=false game_started=false");
  }
  public static int Run(string root,string settings,bool self,string preview){var ui=new Configuration(root,settings,self);if(self){ui.SelfTest(preview);ui.window.Close();return 0;}ui.timer.Start();try{ui.window.ShowDialog();return 0;}finally{ui.timer.Stop();if(ui.child!=null)ui.child.Dispose();}}
 }
}
