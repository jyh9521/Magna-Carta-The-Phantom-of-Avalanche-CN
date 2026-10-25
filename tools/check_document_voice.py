"""Audit project documentation prose while preserving third-party license text and format tokens."""
import re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATTERN=re.compile(r'[我你您咱俺]|(?<!其)它|他们|她们|自己|(?<![A-Za-z0-9_/])(?:we|our|ours|ourselves|you|your|yours|yourself|my|mine|they|their|them)(?![A-Za-z0-9_/])',re.I)
def audit():
 paths=set(subprocess.check_output(['git','ls-files','*.md','*.txt','*.rst'],cwd=ROOT,text=True).splitlines())
 paths.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'docs').glob('*.md'))
 failures=[];excluded=[]
 for n in sorted(paths):
  if n.startswith('assets/licenses/') or n in ('LICENSE','LICENSE-translations.md'):
   excluded.append(n);continue
  for i,line in enumerate((ROOT/n).read_text(encoding='utf-8-sig').splitlines(),1):
   if PATTERN.search(line):failures.append(f'{n}:{i}: {line}')
 if failures:raise ValueError('\n'.join(failures))
 print(f'DOCUMENT_VOICE PASS scanned={len(paths)-len(excluded)} license_exclusions={len(excluded)} personal_pronouns=0')
if __name__=='__main__':audit()
