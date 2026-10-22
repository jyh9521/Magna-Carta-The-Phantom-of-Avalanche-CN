#include "modern_gamepad.h"
#include <cstring>
#include <iostream>
#include <stdexcept>
static bool connected=true,keyboardOK=true,reserved=false;static int polls=0;
static WORD buttons=0;static bool physicalF10=false;
static BOOL WINAPI keyboard(PBYTE keys){if(!keyboardOK)return FALSE;memset(keys,0,256);keys[32]=1;keys[65]=0x80;if(physicalF10)keys[VK_F10]=0x80;if(reserved)keys[VK_F8]=keys[VK_F9]=0x80;return TRUE;}
static DWORD WINAPI poll(DWORD slot,XINPUT_STATE* state){++polls;if(slot||!connected)return ERROR_DEVICE_NOT_CONNECTED;*state={};state->Gamepad.wButtons=buttons;return ERROR_SUCCESS;}
static void check(bool b){if(!b)throw std::runtime_error("gamepad IAT fixture failed");}
int main(int argc,char** argv){
    bool battleTest=argc==2&&!strcmp(argv[1],"--battle-context");
    bool battleKeyboard=argc==2&&!strcmp(argv[1],"--battle-keyboard");
    try {
        auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));check(image!=nullptr);
        auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
        auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
        image[0x2fca]=0x68;*reinterpret_cast<DWORD*>(image+0x2fcb)=reinterpret_cast<DWORD>(image+0xf1b94);
        image[0x2fcf]=0xff;image[0x2fd0]=0x15;*reinterpret_cast<DWORD*>(image+0x2fd1)=reinterpret_cast<DWORD>(image+0xbd3dc);image[0x2fd5]=0xc3;
        BYTE battleCall[]={0xe8,0x03,0x24,0xf6,0xff,0x8b,0x45,0xfc};memcpy(image+0xa0b8d,battleCall,sizeof(battleCall));
        BYTE comboTimer[]={0x8b,0x88,0xe0,0x1d,0,0,0x83,0xc1,1};memcpy(image+0xa1711,comboTimer,sizeof(comboTimer));
        *reinterpret_cast<BYTE**>(image+0xc1964)=image+0xa0b7e;
        auto slot=reinterpret_cast<DWORD*>(image+0xbd3dc);
        DWORD system=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetKeyboardState"));*slot=system;
        DWORD previous;check(VirtualProtect(image+0x2000,0x1000,PAGE_EXECUTE_READ,&previous)!=FALSE);
        check(VirtualProtect(image+0xbd000,0x1000,PAGE_READONLY,&previous)!=FALSE);
        nt->OptionalHeader.SizeOfImage=1;check(!installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==system);nt->OptionalHeader.SizeOfImage=0x10b000;
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr,battleKeyboard));DWORD modified=*slot;check(modified!=system);
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==modified);
        MEMORY_BASIC_INFORMATION info{};VirtualQuery(slot,&info,sizeof(info));check(info.Protect==PAGE_READONLY);
        configureModernGamepadFixture(keyboard,poll,true);
        if(battleKeyboard){
            BYTE scene[0x1e04]{},config[4]{};*reinterpret_cast<BYTE**>(scene)=image+0xc195c;*reinterpret_cast<BYTE**>(image+0xf2428)=config;
            *reinterpret_cast<int*>(scene+0x1dc4)=1;
            BYTE getter[]={0x8b,0x44,0x24,0x04,0x83,0xf8,0x23,0xb8,10,0,0,0,0x74,0x05,0xb8,4,0,0,0,0xc2,4,0};memcpy(image+0xb5b0e,getter,sizeof(getter));check(VirtualProtect(image+0xb5000,0x1000,PAGE_EXECUTE_READWRITE,&previous)!=FALSE);
            BYTE* outer[2]={scene,nullptr};BYTE* inputFrame[2]={reinterpret_cast<BYTE*>(&outer[1]),image+0xa0b92};auto keys=image+0xf1b94;
            physicalF10=true;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_SPACE]&0x80);check(polls==0&&keys[65]==0x80);
            physicalF10=false;*reinterpret_cast<int*>(scene+0x1dcc)=1;*reinterpret_cast<unsigned*>(scene+0x1ddc)=1;*reinterpret_cast<unsigned*>(scene+0x1de0)=10;
            check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80));
            *reinterpret_cast<unsigned*>(scene+0x1de0)=11;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_SPACE]&0x80);
            configureModernGamepadFixture(keyboard,poll,false);check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80));
            configureModernGamepadFixture(keyboard,poll,true);*reinterpret_cast<unsigned*>(scene+0x1de0)=21;*reinterpret_cast<unsigned*>(scene+0x1ddc)=2;
            check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80));check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));check(*slot==system);VirtualFree(image,0,MEM_RELEASE);
            std::cout<<"BATTLE_KEYBOARD PASS F10=native_space scheduled_window=true focus_cancel=true controller_poll=0 physical_keys=preserved rollback=exact game_started=false\n";return 0;
        }
        if(battleTest){
            BYTE scene[0x1e04]{};*reinterpret_cast<BYTE**>(scene)=image+0xc195c;
            BYTE* outer[2]={scene,nullptr};BYTE* inputFrame[2]={reinterpret_cast<BYTE*>(&outer[1]),image+0xa0b92};
            auto keys=image+0xf1b94;configureModernBattleFixture(true);
            check(modernBattleKeyboardFixture(keys,inputFrame));check(modernBattleKeyboardFixture(keys,inputFrame));
            buttons=XINPUT_GAMEPAD_A;check(modernBattleKeyboardFixture(keys,inputFrame));
            if(!(keys[VK_SPACE]&0x80)||(keys[VK_LBUTTON]&0x80)){
                std::cout<<"BATTLE_CONTEXT FAIL A_space="<<bool(keys[VK_SPACE]&0x80)<<" A_mouse="<<bool(keys[VK_LBUTTON]&0x80)<<" game_started=false\n";return 1;}
            buttons=0;check(modernBattleKeyboardFixture(keys,inputFrame));buttons=XINPUT_GAMEPAD_B;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_ESCAPE]&0x80);check(!(keys[VK_RBUTTON]&0x80));
            buttons=XINPUT_GAMEPAD_DPAD_UP;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_UP]&0x80);check(!modernGamepadNavigation().active);
            configureModernBattleFixture(false);check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));check(*slot==system);VirtualFree(image,0,MEM_RELEASE);
            std::cout<<"BATTLE_CONTEXT PASS A_space=true A_mouse=false B_escape=true arrows=native virtual_navigation=false rollback=exact game_started=false\n";return 0;
        }
        using Call=BOOL(WINAPI*)();auto call=reinterpret_cast<Call>(image+0x2fca);auto keys=image+0xf1b94;
        check(call());check(call());buttons=0x1000;check(call());check(keys[32]==0x81&&keys[65]==0x80);
        configureModernGamepadFixture(keyboard,poll,false);check(call());check(keys[32]==1);
        configureModernGamepadFixture(keyboard,poll,true);check(call());check(call());check(keys[32]==1);
        buttons=0;check(call());buttons=0x1000;check(call());check(keys[32]==0x81);
        connected=false;check(call());check(keys[32]==1);connected=true;check(call());check(keys[32]==1);
        keyboardOK=false;check(!call());check(keys[32]==1);keyboardOK=true;
        check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));
        SetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",L"1");SetEnvironmentVariableW(L"MC_MAP_OVERLAY",L"1");
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));configureModernGamepadFixture(keyboard,poll,true);reserved=true;int oldPolls=polls;
        check(call());check(keys[VK_F8]==0&&keys[VK_F9]==0&&keys[32]==1&&keys[65]==0x80&&polls==oldPolls);
        check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));check(*slot==system);SetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",nullptr);SetEnvironmentVariableW(L"MC_MAP_OVERLAY",nullptr);
        check(VirtualProtect(slot,sizeof(DWORD),PAGE_READWRITE,&previous)!=FALSE);*slot=system;DWORD ignored;check(VirtualProtect(slot,sizeof(DWORD),previous,&ignored)!=FALSE);check(*slot==system);
        VirtualFree(image,0,MEM_RELEASE);
        std::cout<<"MODERN_GAMEPAD_IAT PASS synthetic_image=true installed=true mismatch_rejected=true idempotent=true physical_keys=preserved focus_rearm=true failure_passthrough=true page_protection=restored rollback=exact game_started=false\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
