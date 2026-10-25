#include "modern_gamepad.h"
#include "battle_edge.h"
#include "battle_pad_context.h"
#include "map_input.h"
#include <cstring>
#include <iostream>
#include <stdexcept>
static bool connected=true,keyboardOK=true,reserved=false;static int polls=0;
static WORD buttons=0;static SHORT rightStick=0;static BYTE leftTrigger=0;static bool physicalF10=false,physicalSpace=false,physicalLeft=false;
static BOOL WINAPI keyboard(PBYTE keys){if(!keyboardOK)return FALSE;memset(keys,0,256);keys[32]=1;keys[65]=0x80;if(physicalLeft)keys[VK_LBUTTON]|=0x80;if(physicalSpace)keys[VK_SPACE]|=0x80;if(physicalF10)keys[VK_F10]=0x80;if(reserved)keys[VK_F8]=keys[VK_F9]=0x80;return TRUE;}
static DWORD WINAPI poll(DWORD slot,XINPUT_STATE* state){++polls;if(slot||!connected)return ERROR_DEVICE_NOT_CONNECTED;*state={};state->Gamepad.wButtons=buttons;state->Gamepad.sThumbRX=rightStick;state->Gamepad.bLeftTrigger=leftTrigger;return ERROR_SUCCESS;}
static void check(bool b){if(!b)throw std::runtime_error("gamepad IAT fixture failed");}
int main(int argc,char** argv){
    bool battleTest=argc==2&&!strcmp(argv[1],"--battle-context");
    bool battleKeyboard=argc==2&&!strcmp(argv[1],"--battle-keyboard");
    bool battleEdge=argc==2&&!strcmp(argv[1],"--battle-edge");
    bool mapEdge=argc==2&&!strcmp(argv[1],"--map-edge");
    if(mapEdge){SetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",L"1");SetEnvironmentVariableW(L"MC_MAP_OVERLAY",L"1");}
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
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr,battleKeyboard||battleEdge||mapEdge));DWORD modified=*slot;check(modified!=system);
        check(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr));check(*slot==modified);
        MEMORY_BASIC_INFORMATION info{};VirtualQuery(slot,&info,sizeof(info));check(info.Protect==PAGE_READONLY);
        configureModernGamepadFixture(keyboard,poll,true);
        if(mapEdge){
            HWND window=CreateWindowExA(0,"STATIC","offline F9 input fixture",WS_POPUP,0,0,1,1,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);check(window!=nullptr&&!IsWindowVisible(window));
            *reinterpret_cast<HWND*>(image+0xf1b44)=window;
            BYTE msgCaller[]={0x55,0x8b,0xec,0xff,0x75,0x14,0xff,0x75,0x10,0xff,0x75,0x0c,0xff,0x75,0x08};
            memcpy(image+0xbdec,msgCaller,sizeof(msgCaller));image[0xbe01]=0x5d;image[0xbe02]=0xc2;image[0xbe03]=16;image[0xbe04]=0;
            check(VirtualProtect(image+0xb000,0x1000,PAGE_EXECUTE_READWRITE,&previous)!=FALSE);
            using Message=BOOL(WINAPI*)(LPMSG,HWND,UINT,UINT);auto get=reinterpret_cast<Message>(image+0xbdec);
            using Call=BOOL(WINAPI*)();auto call=reinterpret_cast<Call>(image+0x2fca);auto keys=image+0xf1b94;
            auto post=[&](UINT kind,LPARAM flags,WPARAM key=VK_F9,bool source=true){check(PostMessageA(window,kind,key,flags)!=FALSE);MSG msg{};auto invoke=source?get:reinterpret_cast<Message>(*messageSlot);check(invoke(&msg,window,kind,kind)>0);check(msg.message==kind&&msg.wParam==key);};
            int scene=0;modernGamepadWorldScope(true);modernGamepadMapContext(&scene,9,true);check(call());
            post(WM_KEYDOWN,1);post(WM_KEYUP,LPARAM(3ul<<30)|1); // Complete tap before UI refresh.
            check(modernGamepadConsumeMapCycles(true)==1);check(modernGamepadConsumeMapCycles(true)==0);
            post(WM_KEYDOWN,1);post(WM_KEYDOWN,LPARAM(1ul<<30)|1);post(WM_KEYDOWN,LPARAM(1ul<<30)|1);
            check(modernGamepadConsumeMapCycles(true)==1);post(WM_KEYUP,LPARAM(3ul<<30)|1);
            for(int i=0;i<3;++i){post(WM_KEYDOWN,1);post(WM_KEYUP,LPARAM(3ul<<30)|1);}check(modernGamepadConsumeMapCycles(true)==3);
            post(WM_KEYDOWN,1,VK_F8);post(WM_KEYUP,LPARAM(3ul<<30)|1,VK_F8);check(modernGamepadConsumeMapCycles(true)==0);
            post(WM_KEYDOWN,1,VK_F9,false);post(WM_KEYUP,LPARAM(3ul<<30)|1,VK_F9,false);check(modernGamepadConsumeMapCycles(true)==0);
            post(WM_KEYDOWN,1);check(modernGamepadConsumeMapCycles(false)==0);check(modernGamepadConsumeMapCycles(true)==0);
            reserved=true;modernGamepadMapContext(&scene,9,true);check(call());post(WM_KEYDOWN,LPARAM(1ul<<30)|1);check(modernGamepadConsumeMapCycles(true)==0);
            post(WM_KEYUP,LPARAM(3ul<<30)|1);reserved=false;check(call());post(WM_KEYDOWN,1);post(WM_KEYUP,LPARAM(3ul<<30)|1);check(modernGamepadConsumeMapCycles(true)==1);
            post(WM_KEYDOWN,1);configureModernGamepadFixture(keyboard,poll,false);post(WM_KEYUP,LPARAM(3ul<<30)|1);check(modernGamepadConsumeMapCycles(true)==0);
            configureModernGamepadFixture(keyboard,poll,true);modernGamepadMapContext(&scene,9,true);check(call());post(WM_KEYDOWN,1);modernGamepadMapContext(&scene,10,true);check(modernGamepadConsumeMapCycles(true)==0);
            check(call());post(WM_KEYDOWN,1);post(WM_KEYUP,LPARAM(3ul<<30)|1);modernGamepadMapContext(nullptr,0,false);check(modernGamepadConsumeMapCycles(true)==0);
            modernGamepadMapContext(&scene,10,true);check(call());for(int i=0;i<12;++i){post(WM_KEYDOWN,1);post(WM_KEYUP,LPARAM(3ul<<30)|1);}check(modernGamepadConsumeMapCycles(true)==8);
            reserved=true;check(call());check(keys[VK_F8]==0x80&&keys[VK_F9]==0&&polls==0);reserved=false;
            check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));check(*slot==system&&*messageSlot==systemMessage);check(modernGamepadConsumeMapCycles(true)==0);
            DestroyWindow(window);VirtualFree(image,0,MEM_RELEASE);SetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",nullptr);SetEnvironmentVariableW(L"MC_MAP_OVERLAY",nullptr);
            map_input::CycleLatch latch;latch.context(1,9,10,true);latch.keyboard(10,false,true);latch.message(20,20,true,false,true);latch.message(21,21,false,false,true);check(latch.consume(30,true)==1);check(latch.consume(31,true)==0);
            latch.message(40,40,true,false,true);latch.context(1,9,260,true);check(latch.consume(291,true)==0);
            latch.context(1,9,0xfffffff0,true);latch.keyboard(0xfffffff0,false,true);latch.message(5,5,true,false,true);check(latch.consume(20,true)==1);
            std::cout<<"MAP_F9_MESSAGE PASS short_tap=latched held=single_edge queue_bound=8 source_site=BE01 F8=preserved focus_cancel=true scene_cancel=true stale_cancel=true wrap=true controller_poll=0 rollback=both_IATs game_started=false\n";return 0;
        }
        if(battleEdge){
            // Fixture obtains scene vptr from the constructor operand, not a
            // handwritten preceding-table address. Both production IATs execute.
            BYTE scene[0x1e04]{};*reinterpret_cast<BYTE**>(scene)=*reinterpret_cast<BYTE**>(image+0x9d426);
            BYTE gui[0x1c0]{};*reinterpret_cast<BYTE**>(scene+0x10fc)=gui;*reinterpret_cast<BYTE**>(gui)=*reinterpret_cast<BYTE**>(image+0xae413);*reinterpret_cast<BYTE**>(gui+0x1bc)=scene;*reinterpret_cast<unsigned*>(gui+0x190)=1;
            *reinterpret_cast<int*>(scene+0x1dc4)=1;
            BYTE* outer[2]={scene,nullptr};BYTE* inputFrame[2]={reinterpret_cast<BYTE*>(&outer[1]),image+0xa0b92};
            HWND window=CreateWindowExA(0,"STATIC","offline input fixture",WS_POPUP,0,0,1,1,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);check(window!=nullptr);
            *reinterpret_cast<HWND*>(image+0xf1b44)=window;
            // The verified native GetMessage return address is BE01.
            BYTE msgCaller[]={0x55,0x8b,0xec,0xff,0x75,0x14,0xff,0x75,0x10,0xff,0x75,0x0c,0xff,0x75,0x08};
            memcpy(image+0xbdec,msgCaller,sizeof(msgCaller));image[0xbe01]=0x5d;image[0xbe02]=0xc2;image[0xbe03]=16;image[0xbe04]=0;
            check(VirtualProtect(image+0xb000,0x1000,PAGE_EXECUTE_READWRITE,&previous)!=FALSE);
            using Message=BOOL(WINAPI*)(LPMSG,HWND,UINT,UINT);auto get=reinterpret_cast<Message>(image+0xbdec);
            auto keys=image+0xf1b94;auto counter=reinterpret_cast<int*>(image+0xf1c9c+VK_SPACE*4);
            auto post=[&](UINT kind,LPARAM flags){check(PostMessageA(window,kind,VK_SPACE,flags)!=FALSE);MSG msg{};check(get(&msg,window,kind,kind)>0);check(msg.message==kind);};
            check(modernBattleKeyboardFixture(keys,inputFrame)); // bind verified owner
            post(WM_KEYDOWN,1);post(WM_KEYUP,LPARAM(3ul<<30)|1);
            check(modernBattleKeyboardFixture(keys,inputFrame));
            bool latched=(keys[VK_SPACE]&0x80)!=0;
            if(!latched){std::cout<<"BATTLE_EDGE FAIL lost_tap=true native_sample_space=0 game_started=false\n";return 1;}
            check(*counter==0);check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80));
            // Held physical Space remains high; repeats never retrigger its counter.
            physicalSpace=true;post(WM_KEYDOWN,1);*counter=7;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_SPACE]&0x80);check(*counter==0);
            *counter=1;post(WM_KEYDOWN,LPARAM(1ul<<30)|1);check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_SPACE]&0x80);check(*counter==1);
            // A true release/repress between polls must reset the previous hold.
            post(WM_KEYUP,LPARAM(3ul<<30)|1);post(WM_KEYDOWN,1);check(modernBattleKeyboardFixture(keys,inputFrame));check(*counter==0);
            physicalSpace=false;
            post(WM_KEYDOWN,LPARAM(1ul<<30)|1);check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80));
            post(WM_KEYDOWN,1);configureModernGamepadFixture(keyboard,poll,false);check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80));
            configureModernGamepadFixture(keyboard,poll,true);check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80));
            post(WM_KEYDOWN,1);*reinterpret_cast<int*>(scene+0x1dc4)=0;check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80));
            *reinterpret_cast<int*>(scene+0x1dc4)=1;check(modernBattleKeyboardFixture(keys,inputFrame));
            BYTE config[4]{};*reinterpret_cast<BYTE**>(image+0xf2428)=config;
            BYTE getter[]={0x8b,0x44,0x24,0x04,0x83,0xf8,0x23,0xb8,10,0,0,0,0x74,0x05,0xb8,4,0,0,0,0xc2,4,0};memcpy(image+0xb5b0e,getter,sizeof(getter));check(VirtualProtect(image+0xb5000,0x1000,PAGE_EXECUTE_READWRITE,&previous)!=FALSE);
            physicalF10=true;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_SPACE]&0x80);physicalF10=false;
            *reinterpret_cast<int*>(scene+0x1dcc)=1;*reinterpret_cast<unsigned*>(scene+0x1ddc)=1;*reinterpret_cast<unsigned*>(scene+0x1de0)=10;
            check(modernBattleKeyboardFixture(keys,inputFrame));post(WM_KEYDOWN,1);post(WM_KEYUP,LPARAM(3ul<<30)|1);
            check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_SPACE]&0x80); // real tap owns this pulse
            *reinterpret_cast<unsigned*>(scene+0x1ddc)=2;*reinterpret_cast<unsigned*>(scene+0x1de0)=21;
            check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80)); // pending assist was cancelled
            check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));check(*reinterpret_cast<DWORD*>(image+0xbd42c)==systemMessage);DestroyWindow(window);VirtualFree(image,0,MEM_RELEASE);
            combat_input::SpaceEdgeLatch latch;latch.sample(1,10,true);latch.message(1,20,20,true,false,true);check(latch.consume(1,40,true));check(!latch.consume(1,41,true));
            latch.message(1,42,42,true,true,true);check(!latch.consume(1,43,true));
            latch.message(1,44,44,true,false,true);check(!latch.consume(2,45,true));
            latch.message(2,46,46,true,false,true);check(!latch.consume(2,113,true));
            latch.sample(2,0xfffffff0,true);latch.message(2,5,5,true,false,true);check(latch.consume(2,20,true));
            std::cout<<"BATTLE_EDGE PASS lost_tap=restored once=true held=preserved repress=edge assist_cancel=true repeat=false focus_cancel=true scene_cancel=true stale_cancel=true wrap=true ctor_vptr=derived rollback=both_IATs game_started=false\n";return 0;
        }
        if(battleKeyboard){
            BYTE scene[0x1e04]{},config[4]{};*reinterpret_cast<BYTE**>(scene)=*reinterpret_cast<BYTE**>(image+0x9d426);
            BYTE gui[0x1c0]{};*reinterpret_cast<BYTE**>(scene+0x10fc)=gui;*reinterpret_cast<BYTE**>(gui)=*reinterpret_cast<BYTE**>(image+0xae413);*reinterpret_cast<BYTE**>(gui+0x1bc)=scene;*reinterpret_cast<unsigned*>(gui+0x190)=1;*reinterpret_cast<BYTE**>(image+0xf2428)=config;
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
            combat_input::PadContextGate gate;gate.update(1,1,0);check(gate.update(1,4,XINPUT_GAMEPAD_A)&XINPUT_GAMEPAD_A); // fresh edge at boundary
            check(!(gate.update(1,5,XINPUT_GAMEPAD_A)&XINPUT_GAMEPAD_A));gate.update(1,5,0);check(gate.update(1,5,XINPUT_GAMEPAD_A)&XINPUT_GAMEPAD_A);
            BYTE scene[0x1e04]{};*reinterpret_cast<BYTE**>(scene)=*reinterpret_cast<BYTE**>(image+0x9d426);
            BYTE gui[0x1c0]{};*reinterpret_cast<BYTE**>(scene+0x10fc)=gui;*reinterpret_cast<BYTE**>(gui)=*reinterpret_cast<BYTE**>(image+0xae413);*reinterpret_cast<BYTE**>(gui+0x1bc)=scene;*reinterpret_cast<unsigned*>(gui+0x190)=1;
            BYTE* outer[2]={scene,nullptr};BYTE* inputFrame[2]={reinterpret_cast<BYTE*>(&outer[1]),image+0xa0b92};
            auto keys=image+0xf1b94;configureModernBattleFixture(true);
            check(modernBattleKeyboardFixture(keys,inputFrame));check(modernBattleKeyboardFixture(keys,inputFrame));
            buttons=XINPUT_GAMEPAD_A;check(modernBattleKeyboardFixture(keys,inputFrame));
            if(!(keys[VK_SPACE]&0x80)||(keys[VK_LBUTTON]&0x80)){
                std::cout<<"BATTLE_CONTEXT FAIL A_space="<<bool(keys[VK_SPACE]&0x80)<<" A_mouse="<<bool(keys[VK_LBUTTON]&0x80)<<" game_started=false\n";return 1;}
            buttons=0;check(modernBattleKeyboardFixture(keys,inputFrame));buttons=XINPUT_GAMEPAD_B;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_RBUTTON]&0x80);check(!(keys[VK_ESCAPE]&0x80));
            buttons=XINPUT_GAMEPAD_DPAD_UP;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_UP]&0x80);check(!modernGamepadNavigation().active);
            buttons=XINPUT_GAMEPAD_A;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_SPACE]&0x80);
            *reinterpret_cast<unsigned*>(gui+0x190)=4;check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80)&&!(keys[VK_LBUTTON]&0x80));
            buttons=0;check(modernBattleKeyboardFixture(keys,inputFrame));buttons=XINPUT_GAMEPAD_A;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_LBUTTON]&0x80);
            auto left=reinterpret_cast<int*>(image+0xf1c9c+VK_LBUTTON*4);*left=7;*reinterpret_cast<unsigned*>(gui+0x190)=5;check(modernBattleKeyboardFixture(keys,inputFrame));check(*left==0&&!(keys[VK_LBUTTON]&0x80));check(modernGamepadMenuCancellation());
            buttons=0;check(modernBattleKeyboardFixture(keys,inputFrame));buttons=XINPUT_GAMEPAD_B;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_RBUTTON]&0x80);
            auto right=reinterpret_cast<int*>(image+0xf1c9c+VK_RBUTTON*4);
            physicalLeft=true;*right=7;*left=2;configureModernGamepadFixture(keyboard,poll,false);check(modernBattleKeyboardFixture(keys,inputFrame));check(*right==0&&*left==2&&(keys[VK_LBUTTON]&0x80)&&!modernGamepadMenuCancellation());physicalLeft=false;
            configureModernGamepadFixture(keyboard,poll,true);buttons=0;check(modernBattleKeyboardFixture(keys,inputFrame));check(modernBattleKeyboardFixture(keys,inputFrame));buttons=XINPUT_GAMEPAD_B;check(modernBattleKeyboardFixture(keys,inputFrame));
            *right=7;configureModernGamepadFixture(keyboard,poll,false);check(modernBattleKeyboardFixture(keys,inputFrame));check(*right==0&&!(keys[VK_RBUTTON]&0x80));check(modernGamepadMenuCancellation());
            configureModernGamepadFixture(keyboard,poll,true);buttons=0;check(modernBattleKeyboardFixture(keys,inputFrame));check(modernBattleKeyboardFixture(keys,inputFrame));buttons=XINPUT_GAMEPAD_DPAD_DOWN;check(modernBattleKeyboardFixture(keys,inputFrame));check(modernGamepadNavigation().active);
            *reinterpret_cast<unsigned*>(gui+0x190)=7;buttons=0;check(modernBattleKeyboardFixture(keys,inputFrame));buttons=XINPUT_GAMEPAD_A;check(modernBattleKeyboardFixture(keys,inputFrame));check(keys[VK_SPACE]&0x80&&!(keys[VK_LBUTTON]&0x80));
            *reinterpret_cast<unsigned*>(gui+0x190)=99;rightStick=30000;leftTrigger=255;int oldX=*reinterpret_cast<int*>(image+0xf20b0),oldWheel=*reinterpret_cast<int*>(image+0xf20a0);Sleep(20);buttons=XINPUT_GAMEPAD_A|XINPUT_GAMEPAD_B|XINPUT_GAMEPAD_DPAD_UP;check(modernBattleKeyboardFixture(keys,inputFrame));check(!(keys[VK_SPACE]&0x80)&&!(keys[VK_LBUTTON]&0x80)&&!(keys[VK_RBUTTON]&0x80)&&!(keys[VK_UP]&0x80));check(oldX==*reinterpret_cast<int*>(image+0xf20b0)&&oldWheel==*reinterpret_cast<int*>(image+0xf20a0));rightStick=0;leftTrigger=0;physicalSpace=true;check(modernBattleKeyboardFixture(keys,inputFrame));check((keys[VK_SPACE]&0x80)&&keys[65]==0x80);physicalSpace=false;
            configureModernBattleFixture(false);check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));check(*slot==system);VirtualFree(image,0,MEM_RELEASE);
            std::cout<<"BATTLE_CONTEXT PASS A_space=true A_mouse=false B=RMB_release field_arrows=native menu_navigation=true held_context_rearm=true mouse_cancel_on_focus=true unknown_mode=blocked physical_keyboard=preserved mixed_mouse_priority=true rollback=exact game_started=false\n";return 0;
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
        check(call());check(keys[VK_F8]==0x80&&keys[VK_F9]==0&&keys[32]==1&&keys[65]==0x80&&polls==oldPolls);
        check(removeModernGamepad(reinterpret_cast<HMODULE>(image)));check(*slot==system);SetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",nullptr);SetEnvironmentVariableW(L"MC_MAP_OVERLAY",nullptr);
        check(VirtualProtect(slot,sizeof(DWORD),PAGE_READWRITE,&previous)!=FALSE);*slot=system;DWORD ignored;check(VirtualProtect(slot,sizeof(DWORD),previous,&ignored)!=FALSE);check(*slot==system);
        VirtualFree(image,0,MEM_RELEASE);
        std::cout<<"MODERN_GAMEPAD_IAT PASS synthetic_image=true installed=true mismatch_rejected=true idempotent=true physical_keys=preserved focus_rearm=true failure_passthrough=true page_protection=restored rollback=exact game_started=false\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
