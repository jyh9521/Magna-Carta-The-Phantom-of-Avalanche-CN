#include "modern_gamepad.h"
#include "battle_edge.h"
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <cstdlib>
static bool connected=true,keyboardOK=true,reserved=false;static int polls=0;
static WORD buttons=0;static SHORT stickX=0,stickY=0;static DWORD activeSlot=0;static bool traceMode=false;static bool physicalF10=false,physicalSpace=false;
static BOOL WINAPI keyboard(PBYTE keys){if(!keyboardOK)return FALSE;memset(keys,0,256);if(traceMode)return TRUE;keys[32]=1;keys[65]=0x80;if(physicalSpace)keys[VK_SPACE]|=0x80;if(physicalF10)keys[VK_F10]=0x80;if(reserved)keys[VK_F8]=keys[VK_F9]=0x80;return TRUE;}
static DWORD WINAPI poll(DWORD slot,XINPUT_STATE* state){++polls;if(slot!=activeSlot||!connected)return ERROR_DEVICE_NOT_CONNECTED;*state={};state->Gamepad.wButtons=buttons;state->Gamepad.sThumbLX=stickX;state->Gamepad.sThumbLY=stickY;return ERROR_SUCCESS;}
static void check(bool b){if(!b)throw std::runtime_error("gamepad IAT fixture failed");}
int main(int argc,char** argv){
    bool battleKeyboard=false,battleEdge=false,battleTrace=true;
    unsigned mode=argc>1?unsigned(std::atoi(argv[1])):1;
    try {
        auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));check(image!=nullptr);
        auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
        auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
        image[0x2fca]=0x68;*reinterpret_cast<DWORD*>(image+0x2fcb)=reinterpret_cast<DWORD>(image+0xf1b94);
        image[0x2fcf]=0xff;image[0x2fd0]=0x15;*reinterpret_cast<DWORD*>(image+0x2fd1)=reinterpret_cast<DWORD>(image+0xbd3dc);image[0x2fd5]=0xc3;
        BYTE battleCall[]={0xe8,0x03,0x24,0xf6,0xff,0x8b,0x45,0xfc};memcpy(image+0xa0b8d,battleCall,sizeof(battleCall));
        BYTE comboTimer[]={0x8b,0x88,0xe0,0x1d,0,0,0x83,0xc1,1};memcpy(image+0xa1711,comboTimer,sizeof(comboTimer));
        *reinterpret_cast<BYTE**>(image+0xc1964)=image+0xa0b7e;
        image[0xae411]=0xc7;image[0xae412]=0x02;*reinterpret_cast<BYTE**>(image+0xae413)=image+0xc203c;
        image[0x9d424]=0xc7;image[0x9d425]=0;*reinterpret_cast<BYTE**>(image+0x9d426)=image+0xc1960;
        image[0xbdfb]=0xff;image[0xbdfc]=0x15;*reinterpret_cast<BYTE**>(image+0xbdfd)=image+0xbd42c;
        DWORD systemMessage=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetMessageA"));*reinterpret_cast<DWORD*>(image+0xbd42c)=systemMessage;
        auto slot=reinterpret_cast<DWORD*>(image+0xbd3dc);
        DWORD system=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetKeyboardState"));*slot=system;
        auto messageSlot=reinterpret_cast<DWORD*>(image+0xbd42c);
        image[0x9d424]^=1;check(!installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==system&&*messageSlot==systemMessage);image[0x9d424]^=1;
        image[0xbdfb]^=1;check(!installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==system&&*messageSlot==systemMessage);image[0xbdfb]^=1;
        *messageSlot=1;check(!installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==system&&*messageSlot==1);*messageSlot=systemMessage;
        DWORD previous;check(VirtualProtect(image+0x2000,0x1000,PAGE_EXECUTE_READ,&previous)!=FALSE);
        check(VirtualProtect(image+0xbd000,0x1000,PAGE_READONLY,&previous)!=FALSE);
        nt->OptionalHeader.SizeOfImage=1;check(!installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==system);nt->OptionalHeader.SizeOfImage=0x10b000;
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr,battleKeyboard||battleEdge));DWORD modified=*slot;check(modified!=system);
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==modified);
        MEMORY_BASIC_INFORMATION info{};VirtualQuery(slot,&info,sizeof(info));check(info.Protect==PAGE_READONLY);
        configureModernGamepadFixture(keyboard,poll,true);
        if(battleTrace){
            traceMode=true;configureModernBattleFixture(true);
            BYTE scene[0x1e04]{},gui[0x1e0]{};*reinterpret_cast<BYTE**>(scene)=*reinterpret_cast<BYTE**>(image+0x9d426);
            *reinterpret_cast<BYTE**>(scene+0x10fc)=gui;*reinterpret_cast<BYTE**>(gui)=*reinterpret_cast<BYTE**>(image+0xae413);*reinterpret_cast<BYTE**>(gui+0x1bc)=scene;*reinterpret_cast<unsigned*>(gui+4)=0xf6;*reinterpret_cast<unsigned*>(gui+0x190)=mode;
            BYTE* outer[2]={scene,nullptr};BYTE* inputFrame[2]={reinterpret_cast<BYTE*>(&outer[1]),image+0xa0b92};auto keys=image+0xf1b94;
            *reinterpret_cast<int*>(image+0xf1b48)=800;*reinterpret_cast<int*>(image+0xf1b4c)=600;
            *reinterpret_cast<int*>(image+0xf20b0)=400;*reinterpret_cast<int*>(image+0xf20a8)=300;
            struct Step{const char* name;WORD button;SHORT x,y;bool front,online;unsigned nextMode=0;DWORD device=0xffffffff;};
            Step steps[]={
             {"connect",0,0,0,true,true},{"neutral",0,0,0,true,true},
             {"up_down",1,0,0,true,true},{"up_hold",1,0,0,true,true},{"up_up",0,0,0,true,true},
             {"down_down",2,0,0,true,true},{"down_up",0,0,0,true,true},
             {"left_down",4,0,0,true,true},{"left_up",0,0,0,true,true},
             {"right_down",8,0,0,true,true},{"right_up",0,0,0,true,true},
             {"stick_up",0,0,30000,true,true},{"stick_up_up",0,0,0,true,true},
             {"stick_down",0,0,-30000,true,true},{"stick_down_up",0,0,0,true,true},
             {"stick_left",0,-30000,0,true,true},{"stick_left_up",0,0,0,true,true},
             {"stick_right",0,30000,0,true,true},{"stick_right_up",0,0,0,true,true},
             {"A_down",XINPUT_GAMEPAD_A,0,0,true,true},{"A_hold",XINPUT_GAMEPAD_A,0,0,true,true},{"A_up",0,0,0,true,true},
             {"B_down",XINPUT_GAMEPAD_B,0,0,true,true},{"B_hold",XINPUT_GAMEPAD_B,0,0,true,true},{"B_up",0,0,0,true,true},
             {"Start_down",XINPUT_GAMEPAD_START,0,0,true,true},{"Start_up",0,0,0,true,true},
             {"X_down",XINPUT_GAMEPAD_X,0,0,true,true},{"X_up",0,0,0,true,true},
             {"Y_down",XINPUT_GAMEPAD_Y,0,0,true,true},{"Y_up",0,0,0,true,true},
             {"LB_down",XINPUT_GAMEPAD_LEFT_SHOULDER,0,0,true,true},{"LB_up",0,0,0,true,true},
             {"RB_down",XINPUT_GAMEPAD_RIGHT_SHOULDER,0,0,true,true},{"RB_up",0,0,0,true,true},
             {"focus_lost_A",XINPUT_GAMEPAD_A,0,0,false,true},{"focus_return_A",XINPUT_GAMEPAD_A,0,0,true,true},
             {"focus_neutral",0,0,0,true,true},{"focus_A_rearm",XINPUT_GAMEPAD_A,0,0,true,true},{"focus_A_up",0,0,0,true,true},
             {"B_before_disconnect",XINPUT_GAMEPAD_B,0,0,true,true},{"disconnect_B",XINPUT_GAMEPAD_B,0,0,true,false},{"reconnect_B",XINPUT_GAMEPAD_B,0,0,true,true},
             {"reconnect_neutral",0,0,0,true,true},{"reconnect_B_rearm",XINPUT_GAMEPAD_B,0,0,true,true},{"reconnect_B_up",0,0,0,true,true},
             {"fresh_A_enter4",XINPUT_GAMEPAD_A,0,0,true,true,4},{"held_A_enter5",XINPUT_GAMEPAD_A,0,0,true,true,5},
             {"context_A_release",0,0,0,true,true,5},{"A_menu5_down",XINPUT_GAMEPAD_A,0,0,true,true,5},{"A_menu5_up",0,0,0,true,true,5},
             {"B_menu5_down",XINPUT_GAMEPAD_B,0,0,true,true,5},{"held_B_enter1",XINPUT_GAMEPAD_B,0,0,true,true,1},
             {"context_B_up",0,0,0,true,true,1},{"B_field_down",XINPUT_GAMEPAD_B,0,0,true,true,1},
             {"B_focusloss",XINPUT_GAMEPAD_B,0,0,false,true,1},{"B_focusreturn",XINPUT_GAMEPAD_B,0,0,true,true,1},
             {"context_neutral",0,0,0,true,true,1},
             {"slot_A_press",XINPUT_GAMEPAD_A,0,0,true,true,4,0},{"slot_switch_A_held",XINPUT_GAMEPAD_A,0,0,true,true,4,1},
             {"slot_neutral",0,0,0,true,true,4,1},{"slot_A_fresh",XINPUT_GAMEPAD_A,0,0,true,true,4,1},{"slot_A_up",0,0,0,true,true,4,1},
             {"unknown_all",XINPUT_GAMEPAD_A|XINPUT_GAMEPAD_B|XINPUT_GAMEPAD_DPAD_UP,0,0,true,true,99}
            };
            std::cout<<"{\"schema\":1,\"kind\":\"metadata\",\"production\":\"modern_gamepad.cpp\",\"battle_vptr\":\"ctor9d424\",\"xinput_boundary\":\"stub\",\"game_started\":false}\n";
            unsigned serial=0;
            for(const auto& step:steps){if(step.device!=0xffffffff)activeSlot=step.device;if(step.nextMode){mode=step.nextMode;*reinterpret_cast<unsigned*>(gui+0x190)=mode;}buttons=step.button;stickX=step.x;stickY=step.y;connected=step.online;configureModernGamepadFixture(keyboard,poll,step.front);*reinterpret_cast<int*>(image+0xf1c9c+VK_LBUTTON*4)=0x123456;*reinterpret_cast<int*>(image+0xf1c9c+VK_RBUTTON*4)=0x123456;
             check(modernBattleKeyboardFixture(keys,inputFrame));
             unsigned cleared=(*reinterpret_cast<int*>(image+0xf1c9c+VK_LBUTTON*4)==0?1:0)|(*reinterpret_cast<int*>(image+0xf1c9c+VK_RBUTTON*4)==0?2:0);
             const char hex[]="0123456789abcdef";char bytes[513];for(unsigned i=0;i<256;++i){bytes[i*2]=hex[keys[i]>>4];bytes[i*2+1]=hex[keys[i]&15];}bytes[512]=0;
             auto n=modernGamepadNavigation();std::cout<<"{\"kind\":\"frame\",\"serial\":"<<serial++<<",\"action\":\""<<step.name<<"\",\"mode\":"<<mode<<",\"buttons\":"<<step.button<<",\"device\":"<<activeSlot<<",\"lx\":"<<step.x<<",\"ly\":"<<step.y<<",\"focused\":"<<(step.front?"true":"false")<<",\"connected\":"<<(step.online?"true":"false")<<",\"keys\":\""<<bytes<<"\",\"cursor\":["<<*reinterpret_cast<int*>(image+0xf20b0)<<","<<*reinterpret_cast<int*>(image+0xf20a8)<<"],\"nav_active\":"<<(n.active?"true":"false")<<",\"nav_held\":"<<n.held<<",\"nav_pressed\":"<<n.pressed<<",\"nav_time\":"<<n.time<<",\"clear_mouse_counters\":"<<cleared<<",\"cancel_menu\":"<<(modernGamepadMenuCancellation()?"true":"false")<<"}\n";
            }
            configureModernBattleFixture(false);check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));VirtualFree(image,0,MEM_RELEASE);return 0;
        }
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
