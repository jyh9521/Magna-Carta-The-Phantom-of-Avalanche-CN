#include "modern_gamepad.h"
#include <cstring>
#include <iostream>
#include <stdexcept>
static bool connected=true,keyboardOK=true;
static WORD buttons=0;
static BOOL WINAPI keyboard(PBYTE keys){if(!keyboardOK)return FALSE;memset(keys,0,256);keys[32]=1;keys[65]=0x80;return TRUE;}
static DWORD WINAPI poll(DWORD slot,XINPUT_STATE* state){if(slot||!connected)return ERROR_DEVICE_NOT_CONNECTED;*state={};state->Gamepad.wButtons=buttons;return ERROR_SUCCESS;}
static void check(bool b){if(!b)throw std::runtime_error("gamepad IAT fixture failed");}
int main(){
    try {
        auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));check(image!=nullptr);
        auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
        auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
        image[0x2fca]=0x68;*reinterpret_cast<DWORD*>(image+0x2fcb)=reinterpret_cast<DWORD>(image+0xf1b94);
        image[0x2fcf]=0xff;image[0x2fd0]=0x15;*reinterpret_cast<DWORD*>(image+0x2fd1)=reinterpret_cast<DWORD>(image+0xbd3dc);image[0x2fd5]=0xc3;
        auto slot=reinterpret_cast<DWORD*>(image+0xbd3dc);
        DWORD system=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetKeyboardState"));*slot=system;
        DWORD previous;check(VirtualProtect(image+0x2000,0x1000,PAGE_EXECUTE_READ,&previous)!=FALSE);
        check(VirtualProtect(image+0xbd000,0x1000,PAGE_READONLY,&previous)!=FALSE);
        nt->OptionalHeader.SizeOfImage=1;check(!installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==system);nt->OptionalHeader.SizeOfImage=0x10b000;
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));DWORD modified=*slot;check(modified!=system);
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==modified);
        MEMORY_BASIC_INFORMATION info{};VirtualQuery(slot,&info,sizeof(info));check(info.Protect==PAGE_READONLY);
        configureModernGamepadFixture(keyboard,poll,true);
        using Call=BOOL(WINAPI*)();auto call=reinterpret_cast<Call>(image+0x2fca);auto keys=image+0xf1b94;
        check(call());check(call());buttons=0x1000;check(call());check(keys[32]==0x81&&keys[65]==0x80);
        configureModernGamepadFixture(keyboard,poll,false);check(call());check(keys[32]==1);
        configureModernGamepadFixture(keyboard,poll,true);check(call());check(call());check(keys[32]==1);
        buttons=0;check(call());buttons=0x1000;check(call());check(keys[32]==0x81);
        connected=false;check(call());check(keys[32]==1);connected=true;check(call());check(keys[32]==1);
        keyboardOK=false;check(!call());check(keys[32]==1);keyboardOK=true;
        check(VirtualProtect(slot,sizeof(DWORD),PAGE_READWRITE,&previous)!=FALSE);*slot=system;DWORD ignored;check(VirtualProtect(slot,sizeof(DWORD),previous,&ignored)!=FALSE);check(*slot==system);
        VirtualFree(image,0,MEM_RELEASE);
        std::cout<<"MODERN_GAMEPAD_IAT PASS synthetic_image=true installed=true mismatch_rejected=true idempotent=true physical_keys=preserved focus_rearm=true failure_passthrough=true page_protection=restored rollback=exact game_started=false\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
