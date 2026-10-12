"""Read-only window telemetry for one verified isolated launch session."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import re
import time

CAPTION = 0x00C00000
FRAME = 0x00040000
POPUP = 0x80000000
VISIBLE = 0x10000000


def geometry(style, window, client, monitor):
    width, height = window[2] - window[0], window[3] - window[1]
    return dict(style=hex(style & 0xffffffff), window=list(window), client=list(client),
                window_size=[width, height], client_size=[client[2]-client[0], client[3]-client[1]],
                monitor=list(monitor), visible=bool(style & VISIBLE),
                borderless_style=bool(style & POPUP) and not bool(style & (CAPTION | FRAME)),
                covers_monitor=list(window) == list(monitor))


def target_status(running, query_ok, path_matches):
    if not running:
        return 'target_ended'
    if not query_ok:
        return 'identity_query_failed'
    if not path_matches:
        return 'identity_changed'
    return 'active'


def api():
    if os.name != 'nt':
        raise ValueError('Windows required')
    u, k = c.WinDLL('user32', use_last_error=True), c.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'GetWindowLongW': (c.c_long, [w.HWND, c.c_int]),
        'GetWindowRect': (w.BOOL, [w.HWND, c.POINTER(w.RECT)]),
        'GetClientRect': (w.BOOL, [w.HWND, c.POINTER(w.RECT)]),
        'GetWindowThreadProcessId': (w.DWORD, [w.HWND, c.POINTER(w.DWORD)]),
        'GetForegroundWindow': (w.HWND, []),
        'MonitorFromWindow': (w.HANDLE, [w.HWND, w.DWORD]),
        'GetDpiForWindow': (w.UINT, [w.HWND]),
        'IsIconic': (w.BOOL, [w.HWND]),
        'CreateWindowExW': (w.HWND, [w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,w.HWND,w.HMENU,w.HINSTANCE,w.LPVOID]),
        'DestroyWindow': (w.BOOL, [w.HWND]),
    }
    for name, (ret, args) in signatures.items():
        f = getattr(u, name); f.restype = ret; f.argtypes = args
    k.OpenProcess.restype = w.HANDLE; k.OpenProcess.argtypes = [w.DWORD,w.BOOL,w.DWORD]
    k.CloseHandle.argtypes = [w.HANDLE]
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
    k.QueryFullProcessImageNameW.restype = w.BOOL
    k.GetExitCodeProcess.argtypes = [w.HANDLE,c.POINTER(w.DWORD)]
    k.GetExitCodeProcess.restype = w.BOOL
    # Only affects this observer, never the game or desktop display mode.
    u.SetProcessDpiAwarenessContext.argtypes = [w.HANDLE]
    u.SetProcessDpiAwarenessContext(c.c_void_p(-4))
    return u, k


class MonitorInfo(c.Structure):
    _fields_ = [('cbSize',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD)]


def rect_tuple(rect):
    return [rect.left,rect.top,rect.right,rect.bottom]


def read_window(u, hwnd):
    outer, client = w.RECT(), w.RECT()
    if not u.GetWindowRect(hwnd,c.byref(outer)) or not u.GetClientRect(hwnd,c.byref(client)):
        raise OSError('Window disappeared during measurement')
    info = MonitorInfo(); info.cbSize = c.sizeof(info)
    u.GetMonitorInfoW.argtypes = [w.HANDLE,c.POINTER(MonitorInfo)]
    if not u.GetMonitorInfoW(u.MonitorFromWindow(hwnd,2),c.byref(info)):
        raise OSError('Monitor information unavailable')
    row = geometry(u.GetWindowLongW(hwnd,-16),rect_tuple(outer),rect_tuple(client),rect_tuple(info.monitor))
    row.update(hwnd=hex(hwnd),dpi=u.GetDpiForWindow(hwnd),foreground=u.GetForegroundWindow()==hwnd,
               minimized=bool(u.IsIconic(hwnd)))
    return row


def fixture():
    u, _ = api()
    hwnd = u.CreateWindowExW(0,'STATIC','window telemetry fixture',POPUP,10,10,640,480,None,None,None,None)
    if not hwnd: raise OSError('Fixture creation failed')
    try:
        row = read_window(u,hwnd)
        assert row['borderless_style'] and not row['visible'] and row['client_size']==[640,480]
    finally:
        u.DestroyWindow(hwnd)
    print('WINDOW_FIXTURE_PASS hidden=true client=640x480 borderless_style=true game_started=false display_mode_changed=false')


def observe(session, root, seconds):
    session = Path(session).resolve(strict=True)
    allowed = root/'build/runtime-launch'
    if not session.is_relative_to(allowed.resolve()) or session==allowed.resolve():
        raise ValueError('Session must be below runtime-launch')
    output = session/'window-observation.json'
    if output.exists(): raise ValueError('Observation already exists')
    u, k = api()
    started = time.monotonic(); pid = None; expected = None
    while time.monotonic()-started < 30:
        stdout = (session/'stdout.log').read_text(errors='replace') if (session/'stdout.log').exists() else ''
        match = re.search(r'ISOLATED_PROCESS_STARTED pid=(\d+)',stdout)
        if match:
            pid = int(match[1]); break
        if 'LAUNCH_FAILED' in (session/'stderr.log').read_text(errors='replace'): break
        time.sleep(.2)
    if not pid: raise ValueError('No isolated game process in session')
    trace = (session/'profile.log').read_text(errors='replace')
    match = re.search(r'IAT_READY[^\r\n]* module=([^\r\n]+MagnaCarta\.exe)',trace)
    if not match: raise ValueError('No verified game path in session')
    expected = Path(match[1]).resolve(strict=True)
    if not expected.is_relative_to((root/'build').resolve()): raise ValueError('Non-workspace target rejected')
    if hashlib.sha256(expected.read_bytes()).hexdigest()!='be2ae107373835defc6ec33643eaf435dcc5c882ea0b6e3c47032cd013690651':
        raise ValueError('Unknown game image rejected')
    callback_type = c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    u.EnumWindows.argtypes = [callback_type,w.LPARAM]
    rows=[]; status='duration_complete'
    end=time.monotonic()+seconds
    # Retain the process handle: a later process reusing the PID is not the target.
    handle=k.OpenProcess(0x1000,False,pid)
    try:
        while handle and time.monotonic()<end:
            exit_code=w.DWORD()
            if not k.GetExitCodeProcess(handle,c.byref(exit_code)):
                status='process_query_failed';break
            if exit_code.value!=259:
                status='target_ended';break
            path=c.create_unicode_buffer(32768);size=w.DWORD(32768)
            query_ok=bool(k.QueryFullProcessImageNameW(handle,0,path,c.byref(size)))
            # The target may exit between the running check and path query.
            if not k.GetExitCodeProcess(handle,c.byref(exit_code)):
                status='process_query_failed';break
            running=exit_code.value==259
            identity=target_status(running,query_ok,query_ok and Path(path.value).resolve()==expected)
            if identity!='active':
                status=identity;break
            frame=[]
            @callback_type
            def collect(hwnd, unused):
                owner=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(owner))
                if owner.value==pid:
                    try: frame.append(read_window(u,hwnd))
                    except OSError: pass
                return True
            u.EnumWindows(collect,0)
            rows.append(dict(elapsed=round(time.monotonic()-started,3),windows=frame));time.sleep(1)
        if not handle:
            status='target_ended'
    finally:
        if handle:k.CloseHandle(handle)
    report=dict(schema=1,pid=pid,game=str(expected),status=status,samples=rows,
                render_resolution='not measured; client dimensions are not render dimensions',
                read_only=True,observer_started_game=False,observer_changed_display_mode=False)
    with output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(f'WINDOW_OBSERVATION_SAVED samples={len(rows)} status={status} read_only=true')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fixture',action='store_true');p.add_argument('--session',type=Path)
    p.add_argument('--seconds',type=int,default=120);a=p.parse_args()
    if not 1<=a.seconds<=3600:p.error('seconds must be 1..3600')
    if a.fixture:fixture()
    elif a.session:observe(a.session,Path(__file__).resolve().parents[1],a.seconds)
    else:p.error('fixture or session required')
