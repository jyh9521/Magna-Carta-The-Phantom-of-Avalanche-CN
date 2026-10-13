"""Read-only audit of recorded/prepared locale startup settings, never a launch."""
import argparse,json,sys
from pathlib import Path
from runtime_settings import renderer

def check(session):
    session=Path(session);mode=renderer((session/'profile.bin').read_bytes())
    p=session/'preparation.json';report=json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}
    log=(session/'profile.log').read_text(encoding='utf8') if (session/'profile.log').exists() else ''
    focus=report.get('focus_guard',False) or 'FOCUS_GUARD_READY' in log
    return mode=='direct3d' and focus,mode,focus,'recorded_launch' if log else 'preparation_only'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);a=p.parse_args()
    ok,mode,focus,evidence=check(a.session)
    print(f'START_PROFILE {"PASS" if ok else "FAIL"} renderer={mode} focus_guard={str(focus).lower()} evidence={evidence} game_started_by_audit=false')
    sys.exit(0 if ok else 1)
