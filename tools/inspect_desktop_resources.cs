// Developer-only metadata reader. Reflection-only loading never invokes package code.
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Reflection;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
class InspectDesktopResources {
 static int Main(string[] args) {
  if(args.Length!=1)return 2;Console.OutputEncoding=new UTF8Encoding(false);
  var assembly=Assembly.ReflectionOnlyLoadFrom(Path.GetFullPath(args[0]));
  var hashes=new Dictionary<string,string>();var result=new Dictionary<string,object>();
  var json=new JavaScriptSerializer{MaxJsonLength=32*1024*1024};
  foreach(string name in assembly.GetManifestResourceNames())using(var stream=assembly.GetManifestResourceStream(name))using(var m=new MemoryStream()) {
   stream.CopyTo(m);byte[] b=m.ToArray();using(var h=SHA256.Create())hashes[name]=BitConverter.ToString(h.ComputeHash(b)).Replace("-","").ToLowerInvariant();
   if(name=="mc/runtime.json"||name=="mc/Overlay-Manifest.json")result[name.Substring(3)]=json.DeserializeObject(Encoding.UTF8.GetString(b).TrimStart('\ufeff'));
  }
  result["resources"]=hashes;Console.WriteLine(json.Serialize(result));return 0;
 }
}
