using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Reflection;
[assembly: AssemblyTitle("Magna Carta Desktop Launcher")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]
internal static class Entry {
 [STAThread] private static int Main(string[] args) {
  string root=AppDomain.CurrentDomain.BaseDirectory;
#if CONFIGURE
  string script=Path.Combine(root,"config","Configure.ps1");
  string suffix="";
#else
  string script=Path.Combine(root,"Start.ps1");
  string suffix=" -Recipe configured";
#endif
  try {
   if(args.Length==2 && args[0]=="--self-test") {
    File.WriteAllText(args[1],"DESKTOP_ENTRY PASS script="+script.Substring(root.Length));
    return 0;
   }
   if(args.Length==1 && args[0]=="--verify-only") {
#if CONFIGURE
    suffix=" -SelfTest";
#else
    suffix+=" -VerifyOnly";
#endif
   } else if(args.Length!=0) { return 2; }
   if(!File.Exists(script)) throw new FileNotFoundException("Required launcher script is missing",script);
   string ps=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows),"System32","WindowsPowerShell","v1.0","powershell.exe");
   var info=new ProcessStartInfo(ps,"-NoLogo -NoProfile -NonInteractive -STA -ExecutionPolicy Bypass -File \""+script+"\""+suffix);
   info.WorkingDirectory=root; info.UseShellExecute=false; info.CreateNoWindow=true; info.WindowStyle=ProcessWindowStyle.Hidden;
   info.RedirectStandardOutput=true;info.RedirectStandardError=true;
   using(var child=new Process()) {
    child.StartInfo=info;
    string log=Path.Combine(root,"cache");Directory.CreateDirectory(log);
    string name=Path.GetFileNameWithoutExtension(Application.ExecutablePath);
    using(var output=new StreamWriter(Path.Combine(log,name+".log"),false,System.Text.Encoding.UTF8)) {
     object sync=new object();DataReceivedEventHandler receive=(s,e)=>{if(e.Data!=null)lock(sync){output.WriteLine(e.Data);output.Flush();}};
     child.OutputDataReceived+=receive;child.ErrorDataReceived+=receive;
     child.Start();child.BeginOutputReadLine();child.BeginErrorReadLine();child.WaitForExit();
     if(child.ExitCode!=0 && args.Length==0) MessageBox.Show("Launcher exited with status "+child.ExitCode+".\n"+Path.Combine(log,name+".log"),"Magna Carta",MessageBoxButtons.OK,MessageBoxIcon.Error);
     return child.ExitCode;
    }
   }
  } catch(Exception e) {
   if(args.Length==0) MessageBox.Show(e.Message,"Magna Carta",MessageBoxButtons.OK,MessageBoxIcon.Error);
   return 1;
  }
 }
}
