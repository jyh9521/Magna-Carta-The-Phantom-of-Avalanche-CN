#define NOUSER
#include <windows.h>
// A fixture sink, not a Windows dialog. No visible window is created.
extern "C" __declspec(dllexport) int WINAPI MessageBoxA(HWND, LPCSTR, LPCSTR, UINT) {
    return 42;
}
