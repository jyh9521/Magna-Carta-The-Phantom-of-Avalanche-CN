using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security.Principal;

namespace DesktopRuntime {
 public static class Elevation {
  public static bool IsAdministrator() {
   using(var identity=WindowsIdentity.GetCurrent())return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
  }
  static void ProbeFile(string path) {
   Data.NoLinks(path);
   if(File.Exists(path))using(var file=new FileStream(path,FileMode.Open,FileAccess.ReadWrite,FileShare.Read)){}
  }
  static void ProbeDirectory(string directory) {
   string probe=Data.Located(directory,"access-"+Guid.NewGuid().ToString("N")+".tmp");
   using(var file=new FileStream(probe,FileMode.CreateNew,FileAccess.Write,FileShare.None,1,FileOptions.DeleteOnClose)){}
  }
  public static bool Required(string root,string settingsFile,bool display) {
   Data.NoLinks(root);
   try {
    // A new root-level JSON needs directory creation/rename rights as well as
    // access to existing files. No ACL is changed by this probe or by elevation.
    ProbeDirectory(root);
    string settings=String.IsNullOrEmpty(settingsFile)?Settings.PathFor(root):Path.GetFullPath(settingsFile);
    if(!display&&!String.Equals(Path.GetDirectoryName(settings).TrimEnd('\\'),Path.GetFullPath(root).TrimEnd('\\'),StringComparison.OrdinalIgnoreCase))ProbeDirectory(Path.GetDirectoryName(settings));
    ProbeFile(settings);
    if(display){string layout=Data.Text(Data.Resource("runtime.json"),"data_root");if(layout!="."&&layout!="data")throw new InvalidDataException("Unsupported data layout");ProbeFile(Data.Located(layout=="."?root:Data.Located(root,"data"),"DDrawCompat-MagnaCarta.ini"));}
    return false;
   }catch(UnauthorizedAccessException){return true;}
  }
  public static ProcessStartInfo StartInfo(string root,bool configure,string[] args) {
   var local=Environment.GetEnvironmentVariable("LOCALAPPDATA");
   if(String.IsNullOrEmpty(local)||!Path.IsPathRooted(local))throw new IOException("LOCALAPPDATA must identify an absolute user directory");
   Data.NoLinks(local);
   var normalized=(string[])args.Clone();
   // ShellExecute changes the working directory. Resolve caller-relative paths
   // before relaunch so explicit settings/backup/preview arguments stay bound.
   for(int i=0;i<normalized.Length;i++)if(new[]{"--settings-file","--preview","--check-baseline","--rollback"}.Contains(normalized[i])){if(++i>=normalized.Length)throw new ArgumentException("Missing path argument");normalized[i]=Path.GetFullPath(normalized[i]);}
   var forwarded=normalized.Concat(new[]{"--elevated","--user-local-data",Path.GetFullPath(local)});
   return new ProcessStartInfo(Data.Located(root,configure?"Configure.exe":"Game.exe"),String.Join(" ",forwarded.Select(Data.Quote))){UseShellExecute=true,Verb="runas",WorkingDirectory=root,WindowStyle=configure?ProcessWindowStyle.Normal:ProcessWindowStyle.Hidden};
  }
  public static int Start(ProcessStartInfo info) {
   try {using(var child=Process.Start(info)){if(child==null)throw new IOException("Elevated entry did not start");child.WaitForExit();return child.ExitCode;}}
   catch(Win32Exception e){if(e.NativeErrorCode==1223)return 1223;throw;}
  }
 }
}
