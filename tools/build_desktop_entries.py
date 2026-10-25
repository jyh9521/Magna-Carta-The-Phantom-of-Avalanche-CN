"""Build small .NET Framework desktop entries with external PowerShell/WPF dependencies."""
import argparse,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build(output):
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
 csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework/v4.0.30319/csc.exe'
 for name,define in [('Configure',True),('Game',False)]:
  args=[str(csc),'/nologo','/target:winexe','/platform:anycpu','/optimize+','/reference:System.Windows.Forms.dll','/out:'+str(output/(name+'.exe'))]
  if define:args+=['/define:CONFIGURE']
  subprocess.run(args+[str(ROOT/'src/desktop/Entry.cs')],check=True)
  p=output/(name+'.exe')
  if p.stat().st_size>32768:raise ValueError('Desktop entry size exceeded 32 KiB')
  print(f'DESKTOP_BUILD PASS name={p.name} bytes={p.stat().st_size}')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);build(p.parse_args().output)
