#include "focus_guard.h"
#include <iostream>
#include <cstring>
#include <stdexcept>
namespace {
unsigned calls = 0;
BOOL WINAPI mockShow(HWND, int) { ++calls; return 77; }
void check(bool test) { if (!test) throw std::runtime_error("focus fixture failed"); }
}
int main() {
    HWND window = nullptr; BYTE* image = nullptr;
    try {
        window = CreateWindowExW(0,L"STATIC",L"hidden focus fixture",WS_POPUP,0,0,640,480,nullptr,nullptr,nullptr,nullptr);
        check(window != nullptr && !IsWindowVisible(window));
        configureFocusFixture(mockShow,0);
        check(dispatchFocusFixture(window,SW_MINIMIZE,0x1234)==77 && calls==1);
        std::cout << "FOCUS_BASELINE_PASS automatic_minimize_call_forwarded=true" << std::endl;
        configureFocusFixture(mockShow,0x1234);
        check(dispatchFocusFixture(window,SW_MINIMIZE,0x1234)==FALSE && calls==1);
        check(dispatchFocusFixture(window,SW_RESTORE,0x1234)==77 && calls==2);
        check(dispatchFocusFixture(window,SW_MINIMIZE,0x9999)==77 && calls==3);
        check(dispatchFocusFixture(nullptr,SW_MINIMIZE,0x1234)==77 && calls==4);
        check(!suppressFocusMinimize(1,0,SW_MINIMIZE,true));
        image = static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
        check(image != nullptr && !installFocusGuard(reinterpret_cast<HMODULE>(image),nullptr));
        auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
        auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;
        nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
        auto slot=reinterpret_cast<DWORD*>(image+0xbd420);
        DWORD original=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"ShowWindow"));*slot=original;
        check(!installFocusGuard(reinterpret_cast<HMODULE>(image),nullptr));
        const BYTE sequence[]={0x6a,0x06,0xe8,0x9d,0x5a,0xff,0xff,0x50,0xff,0x15};
        memcpy(image+0xbf46,sequence,sizeof(sequence));*reinterpret_cast<DWORD*>(image+0xbf50)=reinterpret_cast<DWORD>(slot);
        DWORD previous;check(VirtualProtect(slot,4,PAGE_READONLY,&previous));
        check(installFocusGuard(reinterpret_cast<HMODULE>(image),nullptr) && *slot!=original);
        check(installFocusGuard(reinterpret_cast<HMODULE>(image),nullptr));
        MEMORY_BASIC_INFORMATION info{};VirtualQuery(slot,&info,sizeof(info));check(info.Protect==PAGE_READONLY);
        check(VirtualProtect(slot,4,PAGE_READWRITE,&previous));*slot=original;check(*slot==original);
        VirtualFree(image,0,MEM_RELEASE);image=nullptr;DestroyWindow(window);window=nullptr;
        std::cout << "FOCUS_FIXTURE_PASS branch_minimize_suppressed=true unrelated_calls_preserved=true returns_preserved=true invalid_image_rejected=true install_idempotent=true protection_restored=true isolated_rollback=true hidden=true game_started=false" << std::endl;
        return 0;
    } catch(const std::exception& error) {
        if(image)VirtualFree(image,0,MEM_RELEASE);if(window)DestroyWindow(window);
        std::cerr<<error.what()<<std::endl;return 1;
    }
}
