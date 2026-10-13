#include "modern_gamepad.h"
#include "modern_input.h"
#include <Xinput.h>
#include <intrin.h>
#include <cstring>

namespace {
using Keyboard=BOOL(WINAPI*)(PBYTE);
using Poll=DWORD(WINAPI*)(DWORD,XINPUT_STATE*);
Keyboard original=nullptr;
Poll poll=nullptr;
ULONG_PTR caller=0;
HWND* gameWindow=nullptr;
modern_input::Router router;
SRWLOCK lock=SRWLOCK_INIT;
DWORD selected=0xffffffff;
bool backendTried=false;
#ifdef MODERN_INPUT_TEST
bool fixtureForeground=false;
#endif
const uint8_t bindings[7]={VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,VK_SPACE,VK_ESCAPE,0};
BOOL WINAPI keyboardHook(PBYTE keys) {
    auto returnAddress=reinterpret_cast<ULONG_PTR>(_ReturnAddress());
    BOOL ok=original(keys);
    if(returnAddress!=caller)return ok;
    AcquireSRWLockExclusive(&lock);
    // The profile attaches under the loader lock. Load XInput only at the verified
    // per-frame input call, not from DllMain or a LoadLibrary interception.
    if(!backendTried) {
        backendTried=true;
        auto backend=LoadLibraryExW(L"xinput1_4.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
        if(backend) {
            poll=reinterpret_cast<Poll>(GetProcAddress(backend,"XInputGetState"));
            if(!poll)FreeLibrary(backend);
        }
    }
    if(!poll){router.update({},false,false);ReleaseSRWLockExclusive(&lock);return ok;}
    DWORD owner=0;HWND front=GetForegroundWindow();
    if(front)GetWindowThreadProcessId(front,&owner);
    bool focused=gameWindow && front==*gameWindow && owner==GetCurrentProcessId() && !IsIconic(front);
#ifdef MODERN_INPUT_TEST
    focused=fixtureForeground;
#endif
    modern_input::Sample sample{};XINPUT_STATE state{};
    if(selected!=0xffffffff && poll(selected,&state)==ERROR_SUCCESS) {
        sample.connected=true;sample.device=selected;
    }else {
        selected=0xffffffff;
        for(DWORD i=0;i<4;++i)if(poll(i,&state)==ERROR_SUCCESS){selected=i;sample.connected=true;sample.device=i;break;}
    }
    if(sample.connected){sample.buttons=state.Gamepad.wButtons;sample.x=state.Gamepad.sThumbLX;sample.y=state.Gamepad.sThumbLY;}
    auto frame=router.update(sample,ok!=FALSE,focused);
    if(ok)modern_input::mergeKeyboard(keys,frame,bindings);
    ReleaseSRWLockExclusive(&lock);
    return ok;
}
}

#ifdef MODERN_INPUT_TEST
void configureModernGamepadFixture(BOOL(WINAPI* keyboard)(PBYTE),DWORD(WINAPI* controller)(DWORD,XINPUT_STATE*),bool front) {
    original=keyboard;poll=controller;backendTried=true;fixtureForeground=front;
}
#endif

bool installModernGamepad(HMODULE module,void(*logger)(const wchar_t*)) {
    auto bytes=reinterpret_cast<BYTE*>(module);
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(bytes);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<=0 || dos->e_lfanew>4096)return false;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(bytes+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC || nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
    if(bytes[0x2fca]!=0x68 || *reinterpret_cast<DWORD*>(bytes+0x2fcb)!=reinterpret_cast<DWORD>(bytes+0xf1b94) ||
       bytes[0x2fcf]!=0xff || bytes[0x2fd0]!=0x15 || *reinterpret_cast<DWORD*>(bytes+0x2fd1)!=reinterpret_cast<DWORD>(bytes+0xbd3dc))return false;
    auto slot=reinterpret_cast<DWORD*>(bytes+0xbd3dc);
    if(*slot==reinterpret_cast<DWORD>(&keyboardHook))return true;
    auto systemKeyboard=reinterpret_cast<Keyboard>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetKeyboardState"));
    if(!systemKeyboard || *slot!=reinterpret_cast<DWORD>(systemKeyboard))return false;
    DWORD previous;
    if(!VirtualProtect(slot,sizeof(DWORD),PAGE_READWRITE,&previous))return false;
    original=systemKeyboard;caller=reinterpret_cast<ULONG_PTR>(bytes+0x2fd5);
    gameWindow=reinterpret_cast<HWND*>(bytes+0xf1b44);
    InterlockedExchange(reinterpret_cast<LONG*>(slot),reinterpret_cast<LONG>(&keyboardHook));
    DWORD ignored;
    if(!VirtualProtect(slot,sizeof(DWORD),previous,&ignored)) {
        InterlockedExchange(reinterpret_cast<LONG*>(slot),reinterpret_cast<LONG>(systemKeyboard));
        VirtualProtect(slot,sizeof(DWORD),previous,&ignored);return false;
    }
    if(logger)logger(L"MODERN_INPUT_READY backend=xinput1_4 route=keyboard_poll menu=unmapped");
    return true;
}
