#pragma once
#include <windows.h>
bool installFocusGuard(HMODULE module, void(*logger)(const wchar_t*));
bool suppressFocusMinimize(ULONG_PTR caller, ULONG_PTR expected, int command, bool owned);
#ifdef FOCUS_GUARD_TEST
using ShowWindowFn = BOOL(WINAPI*)(HWND,int);
void configureFocusFixture(ShowWindowFn original, ULONG_PTR expected);
BOOL dispatchFocusFixture(HWND window, int command, ULONG_PTR caller);
#endif
