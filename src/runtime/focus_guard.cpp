#include "focus_guard.h"
#include <intrin.h>
#include <cstring>

namespace {
using ShowFn = BOOL(WINAPI*)(HWND,int);
ShowFn originalShow = nullptr;
ULONG_PTR expectedCaller = 0;
void(*trace)(const wchar_t*) = nullptr;
BOOL dispatch(HWND window, int command, ULONG_PTR caller) {
    DWORD owner = 0;
    GetWindowThreadProcessId(window, &owner);
    if (suppressFocusMinimize(caller, expectedCaller, command, owner == GetCurrentProcessId())) {
        if (trace) trace(L"FOCUS_MINIMIZE_SUPPRESSED");
        // ShowWindow returns the prior visibility, not a success flag.
        return IsWindowVisible(window);
    }
    return originalShow(window, command);
}
BOOL WINAPI showHook(HWND window, int command) {
    return dispatch(window, command, reinterpret_cast<ULONG_PTR>(_ReturnAddress()));
}
}

bool suppressFocusMinimize(ULONG_PTR caller, ULONG_PTR expected, int command, bool owned) {
    return expected && caller == expected && command == SW_MINIMIZE && owned;
}

bool installFocusGuard(HMODULE module, void(*logger)(const wchar_t*)) {
    auto bytes = reinterpret_cast<BYTE*>(module);
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(bytes);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 || dos->e_lfanew > 4096) return false;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(bytes + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
        nt->OptionalHeader.SizeOfImage != 0x10b000) return false;
    const BYTE callBytes[] = {0x6a,0x06,0xe8,0x9d,0x5a,0xff,0xff,0x50,0xff,0x15};
    if (memcmp(bytes + 0xbf46, callBytes, sizeof(callBytes)) ||
        *reinterpret_cast<DWORD*>(bytes + 0xbf50) != reinterpret_cast<DWORD>(bytes + 0xbd420)) return false;
    auto slot = reinterpret_cast<DWORD*>(bytes + 0xbd420);
    if (*slot == reinterpret_cast<DWORD>(&showHook)) return true;
    auto original = reinterpret_cast<ShowFn>(GetProcAddress(GetModuleHandleW(L"user32.dll"), "ShowWindow"));
    if (!original || *slot != reinterpret_cast<DWORD>(original)) return false;
    DWORD previous;
    if (!VirtualProtect(slot, sizeof(DWORD), PAGE_READWRITE, &previous)) return false;
    originalShow = original;
    expectedCaller = reinterpret_cast<ULONG_PTR>(bytes + 0xbf54);
    trace = logger;
    InterlockedExchange(reinterpret_cast<LONG*>(slot), reinterpret_cast<LONG>(&showHook));
    DWORD ignored;
    if (!VirtualProtect(slot, sizeof(DWORD), previous, &ignored)) {
        InterlockedExchange(reinterpret_cast<LONG*>(slot), reinterpret_cast<LONG>(original));
        VirtualProtect(slot, sizeof(DWORD), previous, &ignored);
        expectedCaller = 0;
        return false;
    }
    return true;
}

#ifdef FOCUS_GUARD_TEST
void configureFocusFixture(ShowWindowFn original, ULONG_PTR expected) {
    originalShow = original; expectedCaller = expected; trace = nullptr;
}
BOOL dispatchFocusFixture(HWND window, int command, ULONG_PTR caller) {
    return dispatch(window, command, caller);
}
#endif
