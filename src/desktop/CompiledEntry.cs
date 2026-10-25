using System;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
[assembly: AssemblyTitle("Magna Carta Desktop")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]
internal static class CompiledEntry {
 [STAThread] private static int Main(string[] args) {
  try {
   string root=AppDomain.CurrentDomain.BaseDirectory;
   var core=Assembly.LoadFrom(Path.Combine(root,"modules","DesktopRuntime.dll"));
#if CONFIGURE
   const bool configure=true;
#else
   const bool configure=false;
#endif
   return (int)core.GetType("DesktopRuntime.Entry",true).GetMethod("Run").Invoke(null,new object[]{root,configure,args});
  } catch(Exception e) {
   while(e is TargetInvocationException && e.InnerException!=null)e=e.InnerException;
   Console.Error.WriteLine(e.Message);
   if(args.Length==0)MessageBox.Show(e.Message,"Magna Carta",MessageBoxButtons.OK,MessageBoxIcon.Error);
   return 1;
  }
 }
}
