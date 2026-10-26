using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.Threading;
using System.Web.Script.Serialization;
namespace DesktopRuntime {
 public static class Data {
  public static readonly JavaScriptSerializer Json=new JavaScriptSerializer{MaxJsonLength=32*1024*1024};
  public static Dictionary<string,object> Object(object value) {var d=value as Dictionary<string,object>;if(d==null)throw new InvalidDataException("Expected JSON object");return d;}
  public static Dictionary<string,object> Parse(byte[] bytes) {return Object(Json.DeserializeObject(Encoding.UTF8.GetString(bytes).TrimStart('\ufeff')));}
  public static byte[] Bytes(string name) {using(var s=typeof(Data).Assembly.GetManifestResourceStream("mc/"+name)){if(s==null)throw new FileNotFoundException("Embedded resource missing: "+name);using(var m=new MemoryStream()){s.CopyTo(m);return m.ToArray();}}}
  public static Dictionary<string,object> Resource(string name) {return Parse(Bytes(name));}
  public static string Text(Dictionary<string,object> d,string name) {object v;if(!d.TryGetValue(name,out v)||!(v is string))throw new InvalidDataException("Expected string: "+name);return (string)v;}
  public static bool Flag(Dictionary<string,object> d,string name,bool fallback=false) {object v;if(!d.TryGetValue(name,out v))return fallback;if(!(v is bool))throw new InvalidDataException("Expected boolean: "+name);return (bool)v;}
  public static int Number(Dictionary<string,object> d,string name) {object v;if(!d.TryGetValue(name,out v)||!(v is int))throw new InvalidDataException("Expected integer: "+name);return (int)v;}
  public static string Hash(byte[] bytes) {using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();}
  public static string HashFile(string path) {using(var s=File.OpenRead(path))using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(s)).Replace("-","").ToLowerInvariant();}
  public static void NoLinks(string path) {var p=Path.GetFullPath(path);while(!String.IsNullOrEmpty(p)){if((File.Exists(p)||Directory.Exists(p))&&(File.GetAttributes(p)&FileAttributes.ReparsePoint)!=0)throw new IOException("Linked path rejected: "+p);p=Path.GetDirectoryName(p);}}
  public static string Located(string root,string name) {
   if(String.IsNullOrEmpty(name)||Path.IsPathRooted(name)||name.IndexOfAny(new[]{'\\',':','\0'})>=0||name.Split('/').Any(p=>p==""||p=="."||p==".."))throw new InvalidDataException("Invalid relative path");
   root=Path.GetFullPath(root).TrimEnd('\\','/');var full=Path.GetFullPath(Path.Combine(root,name));
   if(!full.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException("Escaping path");NoLinks(full);return full;
  }
  public static void Check(string root,string name,string hash) {if(hash.Length!=64||hash.Any(c=>!"0123456789abcdef".Contains(c)))throw new InvalidDataException("Invalid digest");string actual=HashFile(Located(root,name));if(actual!=hash)throw new InvalidDataException("Hash mismatch: "+name+" (expected="+hash+", actual="+actual+")");}
  public static void Atomic(string path,byte[] bytes,bool existingFallback=false) {
   NoLinks(path);var tmp=Path.Combine(Path.GetDirectoryName(Path.GetFullPath(path)),"write-"+Guid.NewGuid().ToString("N")+".tmp");
   try {try {File.WriteAllBytes(tmp,bytes);if(File.Exists(path))File.Replace(tmp,path,null);else File.Move(tmp,path);}
    catch(UnauthorizedAccessException) {if(!existingFallback||!File.Exists(path))throw;
     using(var s=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.Read)){var m=new MemoryStream();s.CopyTo(m);var old=m.ToArray();try{s.Position=0;s.Write(bytes,0,bytes.Length);s.SetLength(bytes.Length);s.Flush(true);s.Position=0;var check=new MemoryStream();s.CopyTo(check);if(Hash(check.ToArray())!=Hash(bytes))throw new IOException("Write readback mismatch");}catch{s.Position=0;s.Write(old,0,old.Length);s.SetLength(old.Length);s.Flush(true);throw;}}
    }
   }finally{if(File.Exists(tmp))File.Delete(tmp);}
  }
  public static string Quote(string s) {var b=new StringBuilder("\"");int slash=0;foreach(char c in s){if(c=='\\'){slash++;continue;}if(c=='"'){b.Append('\\',slash*2+1);b.Append(c);slash=0;continue;}b.Append('\\',slash);slash=0;b.Append(c);}b.Append('\\',slash*2);return b.Append('"').ToString();}
 }
 public static class LaunchDiagnostics {
  public static string Failure(string cache,int code,DateTime startedUtc) {
   var text=Data.Resource("config/configuration-ui.json");string fallback=String.Format(Data.Text(text,"failed"),code,cache);
   try {
    string path=Path.Combine(cache,"Game.log");Data.NoLinks(path);
    if(!File.Exists(path)||File.GetLastWriteTimeUtc(path)<startedUtc)return fallback;
    string line;using(var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite))using(var reader=new StreamReader(stream,Encoding.UTF8,true)){
     var chars=new char[1024];int count=reader.ReadBlock(chars,0,chars.Length);line=new string(chars,0,count).Split(new[]{'\r','\n'},2)[0];
    }
    const string prefix="COMPILED_DESKTOP FAIL ";if(!line.StartsWith(prefix,StringComparison.Ordinal))return fallback;
    string reason=line.Substring(prefix.Length);int separator=reason.IndexOf(": ",StringComparison.Ordinal);if(separator>=0)reason=reason.Substring(separator+2);
    const string mismatch="Hash mismatch: ";if(reason.StartsWith(mismatch,StringComparison.Ordinal)){
     string name=reason.Substring(mismatch.Length);int digest=name.IndexOf(" (expected=",StringComparison.Ordinal);if(digest>=0)name=name.Substring(0,digest);
     reason=String.Format(Data.Text(text,"file_mismatch"),name);
    }
    return String.Format(Data.Text(text,"failed_detail"),code,reason,cache);
   }catch(IOException){return fallback;}catch(UnauthorizedAccessException){return fallback;}
  }
 }
 public sealed class UserPaths {
  public readonly string Root,Settings,Cache,Id;
  public UserPaths(string installation) {
   string local=Environment.GetEnvironmentVariable("LOCALAPPDATA");if(String.IsNullOrEmpty(local)||!Path.IsPathRooted(local))throw new IOException("LOCALAPPDATA must identify an absolute user directory");
   Id=Data.Hash(Encoding.UTF8.GetBytes(Path.GetFullPath(installation).TrimEnd('\\','/').ToUpperInvariant())).Substring(0,16);
   Root=Path.Combine(Path.GetFullPath(local),"MagnaCarta","Installations",Id);Settings=Path.Combine(Root,"enhancements.json");Cache=Path.Combine(Root,"cache");Data.NoLinks(Root);
  }
 }
 public static class Settings {
  public static readonly string[] Sizes={"960x540","1280x720","1600x900","1920x1080","2560x1440"};
  public static Dictionary<string,object> Defaults(){return Validate(Data.Resource("config/enhancements.json"));}
  public static Dictionary<string,object> Validate(Dictionary<string,object> d) {
   int schema=Data.Number(d,"schema");string keys=String.Join(",",d.Keys.OrderBy(x=>x,StringComparer.Ordinal));
   if(schema==1){
    if(keys!="display_profile,motion60,native_gamepad,schema"||!new[]{"baseline","render4k","wide4k","fps60","combined"}.Contains(Data.Text(d,"display_profile")))throw new InvalidDataException("Invalid legacy settings");
    if(Data.Flag(d,"motion60")&&!new[]{"fps60","combined"}.Contains(Data.Text(d,"display_profile")))throw new InvalidDataException("Motion interpolation requires 60Hz profile");Data.Flag(d,"native_gamepad");
   }else if(schema==2){
    if(keys!="frame_rate,free_view,native_gamepad,resolution,schema,window_mode"&&keys!="frame_rate,free_view,native_gamepad,resolution,schema,window_mode,window_resolution")throw new InvalidDataException("Unknown or missing settings fields");
    if(!new[]{"1080p","2k","4k","auto"}.Contains(Data.Text(d,"resolution"))||!new[]{"fullscreen","windowed","borderless"}.Contains(Data.Text(d,"window_mode"))||!new[]{30,60}.Contains(Data.Number(d,"frame_rate")))throw new InvalidDataException("Unsupported display setting");
    Data.Flag(d,"native_gamepad");Data.Flag(d,"free_view");if(d.ContainsKey("window_resolution")&&!Sizes.Contains(Data.Text(d,"window_resolution")))throw new InvalidDataException("Unsupported window resolution");
   }else throw new InvalidDataException("Unsupported settings schema");return d;
  }
  public static Dictionary<string,object> Read(string path) {Data.NoLinks(path);if(!File.Exists(path))return Defaults();if(new FileInfo(path).Length>4096)throw new InvalidDataException("Settings file too large");return Validate(Data.Parse(File.ReadAllBytes(path)));}
  public static Dictionary<string,object> Convert(Dictionary<string,object> source) {
   var d=new Dictionary<string,object>(Validate(source));if(Data.Number(d,"schema")==1){var p=Data.Text(d,"display_profile");d=Defaults();d["resolution"]=new[]{"baseline","fps60"}.Contains(p)?"1080p":"4k";d["frame_rate"]=new[]{"fps60","combined"}.Contains(p)?60:30;}
   if(!d.ContainsKey("window_resolution"))d["window_resolution"]="1280x720";d["native_gamepad"]=false;d["free_view"]=false;return d;
  }
  public static void Write(string path,Dictionary<string,object> value) {Validate(value);if(File.Exists(path))Read(path);if(File.Exists(path+".previous"))throw new IOException("Previous settings backup exists");Data.Atomic(path,Encoding.UTF8.GetBytes(Data.Json.Serialize(value)));Read(path);}
  public static string Initialize(string installation) {
   var p=new UserPaths(installation);Directory.CreateDirectory(p.Root);using(var m=new Mutex(false,"Local\\MagnaCartaSettings_"+p.Id)){
    bool held=false;try{try{held=m.WaitOne(15000);}catch(AbandonedMutexException){held=true;}if(!held)throw new IOException("Settings migration is busy");
     if(File.Exists(p.Settings))Read(p.Settings);else{string old=Data.Located(installation,"config/enhancements.json");Write(p.Settings,File.Exists(old)?Read(old):Defaults());Data.Atomic(Path.Combine(p.Root,"installation.json"),Encoding.UTF8.GetBytes(Data.Json.Serialize(new {schema=1,installation=Path.GetFullPath(installation),legacy_settings=old})));}return p.Settings;
    }finally{if(held)m.ReleaseMutex();}
   }
  }
 }
 public static class Overlay {
  public static Dictionary<string,object> Manifest(){var m=Data.Resource("Overlay-Manifest.json");if(Data.Number(m,"schema")!=1||Data.Text(m,"kind")!="clean_game_overlay"||Data.Text(m,"layout")!="flat")throw new InvalidDataException("Unsupported overlay manifest");return m;}
  public static void Check(string root,bool baseline) {
   var m=Manifest();var files=Data.Object(m[baseline?"source_files":"files"]);foreach(var p in files){if(!baseline&&p.Key=="DDrawCompat-MagnaCarta.ini")continue;Data.Check(root,p.Key,(string)p.Value);}
   if(!baseline){var runtime=Data.Resource("runtime.json");if(Data.Text(runtime,"data_root")!=".")throw new InvalidDataException("Overlay requires flat runtime inputs");foreach(var p in Data.Object(runtime["data"]))Data.Check(root,p.Key,(string)p.Value);}
   Console.WriteLine("OVERLAY_"+(baseline?"BASELINE":"MODIFIED")+" PASS files="+files.Count+" writes=0 game_started=false");
  }
  public static void Idle(){if(Process.GetProcessesByName("MagnaCarta").Length!=0||Process.GetProcessesByName("workspace_launcher").Length!=0)throw new IOException("Exit game and native launcher first");}
  public static void Rollback(string root,string original) {
   Idle();root=Path.GetFullPath(root).TrimEnd('\\','/');original=Path.GetFullPath(original).TrimEnd('\\','/');
   if(root.Equals(original,StringComparison.OrdinalIgnoreCase)||root.StartsWith(original+"\\",StringComparison.OrdinalIgnoreCase)||original.StartsWith(root+"\\",StringComparison.OrdinalIgnoreCase))throw new IOException("Independent original backup required");
   Check(root,false);var m=Manifest();var source=Data.Object(m["source_files"]);var files=Data.Object(m["files"]);var restore=new List<string>();var remove=new List<string>();
   foreach(var f in files){if(f.Key=="DDrawCompat-MagnaCarta.ini"||f.Key=="Game.exe"||f.Key=="Configure.exe"||f.Key=="README-Overlay.txt")continue;
    if(source.ContainsKey(f.Key)){Data.Check(original,f.Key,(string)source[f.Key]);restore.Add(f.Key);}else remove.Add(f.Key);
   }
   // All destinations and originals are checked before any replacement; only listed payload paths are touched.
   foreach(var name in restore){var p=Data.Located(root,name);var attrs=File.GetAttributes(p);try{File.SetAttributes(p,attrs&~FileAttributes.ReadOnly);Data.Atomic(p,File.ReadAllBytes(Data.Located(original,name)),true);Data.Check(root,name,(string)source[name]);}finally{File.SetAttributes(p,attrs);}}
   foreach(var name in remove)File.Delete(Data.Located(root,name));
   Console.WriteLine("OVERLAY_ROLLBACK PASS restored="+restore.Count+" added_removed="+remove.Count+" saves_preserved=true settings_preserved=true");
  }
 }
 public sealed class LaunchPlan {
  public string Game,Module,Profile,Mode,WindowSize;public bool Motion,Field,Gui,Scene,Native,Font,Map,Texture,Flat;
  public Dictionary<string,string> Environment=new Dictionary<string,string>();public List<string> Arguments=new List<string>();
 }
 public static class Launcher {
  static bool Fix(Dictionary<string,object> r,string name,string module,bool baseline) {
   if(!r.ContainsKey(name))return false;var f=Data.Object(r[name]);if(Data.Number(f,"schema")!=1||Data.Text(f,"module")!=module)throw new InvalidDataException("Invalid integration: "+name);return Data.Flag(f,"enabled")&&!baseline;
  }
  public static LaunchPlan Plan(string root,Dictionary<string,object> s,string recipe,bool stable) {
   var r=Data.Resource("runtime.json");if(Data.Number(r,"schema")!=1)throw new InvalidDataException("Unsupported runtime");var recipes=Data.Object(r["recipes"]);
   if(!new[]{"configured","baseline","render4k","wide4k","fps60","combined","motion","texture","maps"}.Contains(recipe)||!recipes.ContainsKey(recipe))throw new InvalidDataException("Unsupported or archived recipe");
   var selected=Data.Object(recipes[recipe]);if(selected.ContainsKey("settings")&&selected["settings"]!=null)s=Settings.Validate(Data.Object(selected["settings"]));
   bool baseline=recipe=="baseline";int schema=Data.Number(s,"schema");var p=new LaunchPlan();string layout=Data.Text(r,"data_root");if(layout!="."&&layout!="data")throw new InvalidDataException("Unsupported data layout");p.Flat=layout==".";p.Game=p.Flat?Path.GetFullPath(root):Data.Located(root,"data");
   p.Mode=schema==1?"borderless":Data.Text(s,"window_mode");p.WindowSize=schema==2&&s.ContainsKey("window_resolution")?Data.Text(s,"window_resolution"):"1280x720";
   p.Motion=schema==1?Data.Flag(s,"motion60"):Data.Number(s,"frame_rate")==60;p.Profile=schema==1?Data.Text(s,"display_profile"):"md3-"+Data.Text(s,"resolution")+"-"+p.Mode+"-"+Data.Number(s,"frame_rate");
   p.Module=Data.Text(selected,"module");if(p.Module=="configured"){string key=p.Motion?"motion":"display";p.Module=r.ContainsKey("configured_modules")?Data.Text(Data.Object(r["configured_modules"]),key):(key=="display"?"display":"modern");}
   if(recipe=="configured"&&schema==2)p.Module="configuration";
   p.Field=Fix(r,"field_return_height","field-return-height",baseline);if(p.Field)p.Module="field-return-height";
   p.Gui=Fix(r,"gui_parent_guard","gui-parent-guard",baseline);if(p.Gui)p.Module="gui-parent-guard";
   p.Scene=Fix(r,"scene_loading","scene-loading",baseline);if(p.Scene)p.Module="scene-loading";
   p.Native=Fix(r,"native_scene_loading","native-loading",baseline)&&p.Gui;if(p.Scene&&p.Native)throw new InvalidDataException("Conflicting scene-loading modes");if(p.Native)p.Module="native-loading";
   p.Font=Fix(r,"scaled_font","scaled-font",baseline);if(r.ContainsKey("scaled_font")&&Data.Number(Data.Object(r["scaled_font"]),"scale")!=4)throw new InvalidDataException("Invalid glyph scale");if(p.Font)p.Module="scaled-font";
   p.Map=Data.Flag(selected,"maps");if(r.ContainsKey("map_overlay"))p.Map=Fix(r,"map_overlay","minimap",baseline)&&(recipe=="configured"||recipe=="maps");if(p.Map&&r.ContainsKey("map_overlay"))p.Module="minimap";
   p.Texture=Data.Flag(selected,"texture");var env=p.Environment;var labels=Data.Resource("config/encounter-ui.json");
   foreach(string name in new[]{"on","off"}){string value=Data.Text(labels,name);if(value.Length<1||value.Length>=128)throw new InvalidDataException("Invalid encounter label");env["MC_ENCOUNTER_"+name.ToUpperInvariant()]=value;}
   env["MC_FIELD_RETURN_HEIGHT"]=p.Field?"1":"0";env["MC_GUI_PARENT_GUARD"]=p.Gui?"1":"0";env["MC_SCENE_LOADING"]=p.Scene?"1":"0";env["MC_NATIVE_SCENE_LOADING"]=p.Native?"1":"0";
   env["MC_SCALED_FONT"]=p.Font?"1":"0";env["MC_SCALED_FONT_ASSETS"]=p.Font?Data.Located(root,"fonts"):"";env["MC_MOTION60_COMPLETE"]=p.Motion?"1":"0";env["MC_TITLE_BACKGROUND4K"]="1";env["MC_FREE_VIEW"]="0";
   env["MC_MAP_OVERLAY"]=p.Map?"1":"0";env["MC_MAP_ASSETS"]=p.Map?Data.Located(root,"maps"):"";env["MC_WINDOWED"]=p.Mode=="windowed"?"1":"0";env["MC_WINDOW_RESOLUTION"]=p.Mode=="windowed"?p.WindowSize:"";
   foreach(var key in new[]{"collision_guard","audio_provider_policy","contact_audio_trace"}){bool enabled=false;if(r.ContainsKey("test_candidates")){var c=Data.Object(r["test_candidates"]);if(Data.Number(c,"schema")!=1)throw new InvalidDataException("Invalid candidate defaults");enabled=!baseline&&!stable&&Data.Flag(c,key);}env["MC_"+key.ToUpperInvariant()]=enabled?"1":"0";}
   return p;
  }
  public static int Run(string root,string settingsFile,string recipe,bool verify,bool stable) {
   var r=Data.Resource("runtime.json");var settings=Settings.Read(settingsFile??Settings.Initialize(root));var p=Plan(root,settings,recipe,stable);
   foreach(var f in Data.Object(r["files"]))Data.Check(root,f.Key,(string)f.Value);foreach(var f in Data.Object(r["data"]))Data.Check(p.Game,f.Key,(string)f.Value);
   if(p.Map){var atlas=Data.Parse(File.ReadAllBytes(Data.Located(root,"maps/manifest.json")));if(Data.Number(atlas,"schema")!=1||Data.Flag(atlas,"navigation_verified")||((object[])atlas["accepted"]).Length==0)throw new InvalidDataException("Unsupported map atlas");var seen=new HashSet<int>();var files=Data.Object(r["files"]);
    foreach(var value in (object[])atlas["accepted"]){var row=Data.Object(value);int id=Data.Number(row,"id");if(id<0||id>9999||!seen.Add(id))throw new InvalidDataException("Invalid atlas identifier");foreach(var ext in new[]{"png","map"}){string name="maps/"+id.ToString("D4")+"."+ext;string expected=Data.Text(row,ext=="png"?"png_sha256":"metadata_sha256");if(!files.ContainsKey(name)||(string)files[name]!=expected)throw new InvalidDataException("Map manifest mismatch");}}
   }
   var paths=new UserPaths(root);Directory.CreateDirectory(paths.Cache);string ini=Data.Located(p.Game,"DDrawCompat-MagnaCarta.ini");byte[] original=File.ReadAllBytes(ini);string originalHash=Data.Hash(original);var profiles=Data.Object(r["profiles"]);if(!profiles.Values.Contains(originalHash))throw new InvalidDataException("Unknown active display configuration");
   byte[] candidate=Data.Bytes("config/profiles/"+p.Profile+".ini");if(Data.Text(profiles,p.Profile)!=Data.Hash(candidate))throw new InvalidDataException("Embedded display profile mismatch");
   using(var mutex=new Mutex(false,"Local\\MagnaCartaShared_"+paths.Id)){bool held=false;try{try{held=mutex.WaitOne(0);}catch(AbandonedMutexException){held=true;}if(!held)throw new IOException("Another runtime entry is active");Overlay.Idle();
    byte[] profile=Data.Bytes("config/profile-base.bin");if(profile.Length!=52||profile[1]>1)throw new InvalidDataException("Unsupported profile layout");profile[1]=0;Data.Atomic(Path.Combine(paths.Cache,"profile.bin"),profile);
    string log=Path.Combine(paths.Cache,"profile.log");Data.NoLinks(log);if(!verify&&File.Exists(log))File.Delete(log);
    Data.Atomic(ini,candidate,true);try {
     var args=p.Arguments;args.AddRange(new[]{"--workspace",p.Game,"--shim",Data.Located(root,"modules/"+p.Module+".dll"),"--profile",Path.Combine(paths.Cache,"profile.bin"),"--log",log,"--native-text-step","--system-messages","--focus-guard","--display-profile",p.Profile});
     if(p.Map)args.Add("--input-passthrough");if(p.Texture)args.Add("--texture-lifetime");if(p.Flat)args.Add("--in-place-overlay");if(verify)args.Add("--verify-only");
     var info=new ProcessStartInfo(Data.Located(root,"modules/workspace_launcher.exe"),String.Join(" ",args.Select(Data.Quote))){WorkingDirectory=p.Game,UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8};foreach(var pair in p.Environment)info.EnvironmentVariables[pair.Key]=pair.Value;
     int code;using(var child=new Process()){child.StartInfo=info;using(var stdout=new StreamWriter(Path.Combine(paths.Cache,"launcher.stdout.txt"),false,Encoding.UTF8))using(var stderr=new StreamWriter(Path.Combine(paths.Cache,"launcher.stderr.txt"),false,Encoding.UTF8)){child.OutputDataReceived+=(s,e)=>{if(e.Data!=null)stdout.WriteLine(e.Data);};child.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)stderr.WriteLine(e.Data);};child.Start();child.BeginOutputReadLine();child.BeginErrorReadLine();child.WaitForExit();code=child.ExitCode;}}
     if(code!=0)throw new IOException("Native launcher exit="+code+"; see "+paths.Cache);Console.WriteLine("COMPILED_RUNTIME PASS recipe="+recipe+" module="+p.Module+" verify_only="+verify+" map_overlay="+p.Map+" game_started="+(!verify));return 0;
    }finally{if(verify){string now=Data.HashFile(ini);if(now!=originalHash){if(now!=Data.Hash(candidate))throw new IOException("External display edit preserved");Data.Atomic(ini,original,true);}}}
   }finally{if(held)mutex.ReleaseMutex();}}
  }
 }
 public static class Entry {
  public static int Run(string root,bool configure,string[] args) {
   string settings=null,preview=null,recipe="configured",action="",original=null;bool verify=false,self=false,stable=false;
   for(int i=0;i<args.Length;i++){string a=args[i];switch(a){case "--verify-only":verify=true;break;case "--self-test":self=true;break;case "--without-test-candidates":stable=true;break;case "--check-installed":action="check";break;case "--check-baseline":action="baseline";if(++i>=args.Length)return 2;original=args[i];break;case "--rollback":action="rollback";if(++i>=args.Length)return 2;original=args[i];break;case "--settings-file":if(++i>=args.Length)return 2;settings=Path.GetFullPath(args[i]);break;case "--recipe":if(++i>=args.Length)return 2;recipe=args[i];break;case "--preview":if(++i>=args.Length)return 2;preview=Path.GetFullPath(args[i]);break;default:return 2;}}
   if((preview!=null&&!self)||(!configure&&self)||(!configure&&preview!=null)||(configure&&action!="")||(action!=""&&(verify||self||stable||settings!=null||recipe!="configured")))return 2;
   var paths=new UserPaths(root);Directory.CreateDirectory(paths.Cache);string name=configure?"Configure":"Game";
   using(var log=new StreamWriter(Path.Combine(paths.Cache,name+".log"),false,Encoding.UTF8)){var old=Console.Out;Console.SetOut(log);try{
    if(action=="check"){Overlay.Check(root,false);return 0;}if(action=="baseline"){Overlay.Check(original,true);return 0;}if(action=="rollback"){Overlay.Rollback(root,original);return 0;}
    if(configure){return Configuration.Run(root,settings,self||verify,preview);}return Launcher.Run(root,settings,recipe,verify,stable);
   }catch(Exception e){log.WriteLine("COMPILED_DESKTOP FAIL "+e);if(args.Length==0)System.Windows.MessageBox.Show(e.Message,"Magna Carta");return 1;}finally{Console.SetOut(old);}}
  }
 }
}
