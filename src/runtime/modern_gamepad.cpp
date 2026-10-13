#include "modern_gamepad.h"
#include "modern_input.h"
#include "world_gamepad.h"
#include "gamepad_cursor.h"
#include "gamepad_ui.h"
#include "camera_input_view.h"
#include <Xinput.h>
#include <intrin.h>
#include <cstring>
#include <cmath>
#include <cwchar>

namespace {
using Keyboard=BOOL(WINAPI*)(PBYTE);
using Poll=DWORD(WINAPI*)(DWORD,XINPUT_STATE*);
Keyboard original=nullptr;
DWORD originalIat=0;
Poll poll=nullptr;
ULONG_PTR caller=0;
HWND* gameWindow=nullptr;
modern_input::Router router;
SRWLOCK lock=SRWLOCK_INIT;
DWORD selected=0xffffffff;
bool backendTried=false;
bool nativeRouting=false;bool passthroughOnly=false,mapReservedKeys=false;volatile LONG mapPadButtons=0;
BYTE* engine=nullptr;
thread_local bool worldScope=false;
thread_local modern_input::MoveIntent movement;
thread_local bool pendingInteraction=false;
modern_input::Cursor controllerCursor;DWORD cursorTime=0;
GamepadNavigation navigation;DWORD inputSerial=0;unsigned navHeld=0;WORD lastButtons=0;
bool realMouseKnown=false,navMouseBlocked=false;int realMouseX=0,realMouseY=0;unsigned triggerHeld=0;DWORD triggerTime=0;
void(*inputTrace)(const wchar_t*)=nullptr;DWORD traceTime=0;
#ifdef MODERN_INPUT_TEST
bool fixtureForeground=false;
#endif
const uint8_t bindings[7]={VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,VK_SPACE,VK_ESCAPE,0};
bool readable(const void* a,size_t n){
 auto p=reinterpret_cast<ULONG_PTR>(a),end=p+n;if(!p||end<p)return false;
 while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;
}
bool orbitKeyboard(PBYTE keys,bool focused){
 if(!focused||!worldScope||!engine||!keys||!(0x80&(keys[VK_UP]|keys[VK_DOWN]|keys[VK_LEFT]|keys[VK_RIGHT]))||(keys[VK_LBUTTON]&0x80))return false;
 auto cam=*reinterpret_cast<BYTE**>(engine+0xf2290);float displayed[16];
 if(!render_input::inputView.read(reinterpret_cast<uintptr_t>(cam),GetTickCount(),displayed))return false;
 int x=int(bool(keys[VK_RIGHT]&0x80))-int(bool(keys[VK_LEFT]&0x80)),y=int(bool(keys[VK_UP]&0x80))-int(bool(keys[VK_DOWN]&0x80));
 movement=modern_input::cameraRelative(static_cast<SHORT>(x*32767),static_cast<SHORT>(y*32767),0,displayed);
 const int arrows[]={VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT};for(int k:arrows)keys[k]&=0x7f;
 if(movement.active)keys[VK_UP]|=0x80;
 return true;
}
BOOL __cdecl keyboardInner(PBYTE keys,ULONG_PTR returnAddress,void* nativeFrame) {
    BOOL ok=original(keys);
    if(returnAddress!=caller)return ok;
    InterlockedExchange(&mapPadButtons,0);
    if(mapReservedKeys&&!worldScope)notifyWorldTickObserver(nullptr,false);
    if(ok&&mapReservedKeys){keys[VK_F8]=keys[VK_F9]=0;}
    DWORD owner=0;HWND front=GetForegroundWindow();
    if(front)GetWindowThreadProcessId(front,&owner);
    bool focused=gameWindow && front==*gameWindow && owner==GetCurrentProcessId() && !IsIconic(front);
#ifdef MODERN_INPUT_TEST
    focused=fixtureForeground;
#endif
    if(passthroughOnly){movement={};navigation={};if(ok)orbitKeyboard(keys,focused);return ok;}
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
        if(!poll&&inputTrace)inputTrace(L"INPUT_BACKEND_UNAVAILABLE xinput1_4=true");
    }
    movement={};
    navigation={};
    if(!poll){router.update({},false,false);ReleaseSRWLockExclusive(&lock);return ok;}
    modern_input::Sample sample{};XINPUT_STATE state{};
    if(selected!=0xffffffff && poll(selected,&state)==ERROR_SUCCESS) {
        sample.connected=true;sample.device=selected;
    }else {
        selected=0xffffffff;
        for(DWORD i=0;i<4;++i)if(poll(i,&state)==ERROR_SUCCESS){selected=i;sample.connected=true;sample.device=i;break;}
    }
    if(sample.connected){sample.buttons=state.Gamepad.wButtons;sample.x=state.Gamepad.sThumbLX;sample.y=state.Gamepad.sThumbLY;
        sample.rx=state.Gamepad.sThumbRX;sample.ry=state.Gamepad.sThumbRY;sample.lt=state.Gamepad.bLeftTrigger;sample.rt=state.Gamepad.bRightTrigger;}
    auto frame=router.update(sample,ok!=FALSE,focused);int titlePhase=-1;
    if(ok&&mapReservedKeys&&nativeRouting&&worldScope&&frame.armed&&focused)InterlockedExchange(&mapPadButtons,((sample.buttons&XINPUT_GAMEPAD_BACK)?1:0)|((sample.buttons&XINPUT_GAMEPAD_RIGHT_THUMB)?2:0));
    if(ok&&nativeRouting){
        bool clicksAllowed=true;
        uint8_t nativeBindings[7]={VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,static_cast<uint8_t>(worldScope?0:VK_LBUTTON),VK_RBUTTON,VK_RBUTTON};
        // Title update tests key 0x1b and sets +64 for logo/opening skip.
        // Preserve the native Esc path; Space does not set that skip request.
        if(readable(nativeFrame,8)&&reinterpret_cast<BYTE**>(nativeFrame)[1]==engine+0xb71d1){
            auto parent=*reinterpret_cast<BYTE**>(nativeFrame);
            if(reinterpret_cast<ULONG_PTR>(parent)>0x38&&readable(parent-0x38,4)){
                auto title=*reinterpret_cast<BYTE**>(parent-0x38);
                if(readable(title,0x74)&&*reinterpret_cast<ULONG_PTR*>(title)==reinterpret_cast<ULONG_PTR>(engine+0xc22f0)){
                    int phase=*reinterpret_cast<int*>(title+0x70);titlePhase=phase;
                    if(phase==1||phase==3)nativeBindings[4]=VK_ESCAPE;
                    else if(phase<4){frame.held&=~uint32_t(modern_input::Confirm);clicksAllowed=false;}
                    else if(phase!=4&&phase!=8){frame.held&=~uint32_t(modern_input::Confirm);clicksAllowed=false;}
                }
            }
        }
        bool keyboardDirection=(keys[VK_UP]|keys[VK_DOWN]|keys[VK_LEFT]|keys[VK_RIGHT]|keys[VK_LBUTTON])&0x80;
        bool physicalArrows=(keys[VK_UP]|keys[VK_DOWN]|keys[VK_LEFT]|keys[VK_RIGHT])&0x80;
        if(worldScope){
            // Confirm is a scene interaction request, not a global UI Space key.
            pendingInteraction=frame.armed&&focused&&(frame.pressed&modern_input::Confirm);
            frame.held&=~uint32_t(15);
            bool orbitKeys=orbitKeyboard(keys,focused);
            if(!orbitKeys&&frame.armed&&focused&&!keyboardDirection&&engine){
                auto camera=*reinterpret_cast<BYTE**>(engine+0xf2290);
                if(camera&&readable(camera+0x80,64)){
                    float displayed[16];auto view=reinterpret_cast<float*>(camera+0x80);
                    if(render_input::inputView.read(reinterpret_cast<uintptr_t>(camera),GetTickCount(),displayed))view=displayed;
                    movement=modern_input::cameraRelative(sample.x,sample.y,sample.buttons,view);
                }
            }
            if(movement.active)frame.held|=modern_input::Up;
        }else{
            if(sample.buttons&XINPUT_GAMEPAD_LEFT_SHOULDER)frame.held|=modern_input::Left;
            if(sample.buttons&XINPUT_GAMEPAD_RIGHT_SHOULDER)frame.held|=modern_input::Right;
            if(physicalArrows)frame.held&=~uint32_t(15);
        }
        modern_input::mergeKeyboard(keys,frame,nativeBindings);
        if(frame.armed&&focused){
            if(clicksAllowed&&!worldScope&&(sample.buttons&XINPUT_GAMEPAD_X))keys[VK_LBUTTON]|=0x80;
            if(sample.buttons&XINPUT_GAMEPAD_Y)keys[VK_TAB]|=0x80;
        }
        DWORD now=GetTickCount();unsigned elapsed=cursorTime?now-cursorTime:0;cursorTime=now;
        int w=*reinterpret_cast<int*>(engine+0xf1b48),h=*reinterpret_cast<int*>(engine+0xf1b4c);
        auto x=reinterpret_cast<int*>(engine+0xf20b0),y=reinterpret_cast<int*>(engine+0xf20a8);
        bool mouseMoved=realMouseKnown&&(*x!=realMouseX||*y!=realMouseY);realMouseKnown=true;realMouseX=*x;realMouseY=*y;
        if(mouseMoved)navMouseBlocked=true;if(!(frame.held&15))navMouseBlocked=false;
        auto point=controllerCursor.update(*x,*y,sample.rx,sample.ry,elapsed,w,h,frame.armed&&focused);
        if(point.owned){*x=static_cast<int>(point.x);*y=static_cast<int>(point.y);}
        navigation={frame.held&15,(frame.held&15)&~navHeld,++inputSerial,now,
                    frame.armed&&focused&&!worldScope&&!keyboardDirection&&!navMouseBlocked
                    &&std::abs(int(sample.rx))<8689&&std::abs(int(sample.ry))<8689
                    &&!((sample.buttons|lastButtons)&(XINPUT_GAMEPAD_A|XINPUT_GAMEPAD_X|XINPUT_GAMEPAD_B|XINPUT_GAMEPAD_START))};
        navHeld=frame.held&15;lastButtons=sample.buttons;
        unsigned triggers=(sample.lt>=128?1u:0u)|(sample.rt>=128?2u:0u);
        if(frame.armed&&focused&&!worldScope&&triggers&&triggers!=3&&(triggers!=triggerHeld||DWORD(now-triggerTime)>=150)){
            // WM_MOUSEWHEEL stores -(signed delta)/120 in this original field.
            *reinterpret_cast<int*>(engine+0xf20a0)=triggers==1?-1:1;triggerTime=now;
        }
        triggerHeld=triggers;
    }else if(ok)modern_input::mergeKeyboard(keys,frame,bindings);
    DWORD traceNow=GetTickCount();
    if(inputTrace&&(!traceTime||DWORD(traceNow-traceTime)>=1000)){
        traceTime=traceNow;wchar_t message[256];
        swprintf_s(message,L"INPUT_FRAME connected=%u slot=%u focused=%u armed=%u world=%u buttons=%04x actions=%02x native=%u title_phase=%d ui_active=%u mouse_blocked=%u",
            unsigned(sample.connected),selected,unsigned(focused),unsigned(frame.armed),unsigned(worldScope),unsigned(sample.buttons),unsigned(frame.held),unsigned(nativeRouting),titlePhase,unsigned(navigation.active),unsigned(navMouseBlocked));
        inputTrace(message);
    }
    ReleaseSRWLockExclusive(&lock);
    return ok;
}
__declspec(naked) BOOL WINAPI keyboardBridge(PBYTE){__asm {
 push ebp
 mov ebp,esp
 push dword ptr[ebp]
 push dword ptr[ebp+4]
 push dword ptr[ebp+8]
 call keyboardInner
 add esp,12
 mov esp,ebp
 pop ebp
 ret 4
}}
}
void modernGamepadWorldScope(bool enabled){worldScope=enabled;movement={};pendingInteraction=false;}
bool modernGamepadConsumeInteraction(){bool value=worldScope&&pendingInteraction;pendingInteraction=false;return value;}
modern_input::MoveIntent modernGamepadMoveIntent(){return worldScope?movement:modern_input::MoveIntent{};}
unsigned modernGamepadMapButtons(){return static_cast<unsigned>(InterlockedCompareExchange(&mapPadButtons,0,0));}
GamepadNavigation modernGamepadNavigation(){return navigation;}
void modernGamepadFocusCursor(float x,float y){if(!nativeRouting||!engine||!navigation.active)return;int w=*reinterpret_cast<int*>(engine+0xf1b48),h=*reinterpret_cast<int*>(engine+0xf1b4c);controllerCursor.focus(x,y,w,h);*reinterpret_cast<int*>(engine+0xf20b0)=static_cast<int>(x);*reinterpret_cast<int*>(engine+0xf20a8)=static_cast<int>(y);}

#ifdef MODERN_INPUT_TEST
void configureModernGamepadFixture(BOOL(WINAPI* keyboard)(PBYTE),DWORD(WINAPI* controller)(DWORD,XINPUT_STATE*),bool front) {
    original=keyboard;poll=controller;backendTried=true;fixtureForeground=front;
}
void configureModernNavigationFixture(BYTE* p,GamepadNavigation n){engine=p;nativeRouting=true;navigation=n;}
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
    if(*slot==reinterpret_cast<DWORD>(&keyboardBridge))return engine==bytes&&(!nativeRouting||(canSetWorldGamepad(module,true)&&canSetGamepadUi(module,true)));
    auto systemKeyboard=reinterpret_cast<Keyboard>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetKeyboardState"));
    if(!systemKeyboard || *slot!=reinterpret_cast<DWORD>(systemKeyboard))return false;
    wchar_t passFlag[8]{};passthroughOnly=GetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",passFlag,8)==1&&passFlag[0]==L'1';
    mapReservedKeys=GetEnvironmentVariableW(L"MC_MAP_OVERLAY",passFlag,8)==1&&passFlag[0]==L'1';
    wchar_t mode[8]{};bool native=GetEnvironmentVariableW(L"MC_GAMEPAD_NATIVE",mode,8)==1&&mode[0]==L'1';
    if(native&&passthroughOnly)return false;
    if(native&&(!canSetWorldGamepad(module,true)||!canSetGamepadUi(module,true)))return false;
    DWORD previous;
    if(!VirtualProtect(slot,sizeof(DWORD),PAGE_READWRITE,&previous))return false;
    original=systemKeyboard;caller=reinterpret_cast<ULONG_PTR>(bytes+0x2fd5);
    originalIat=reinterpret_cast<DWORD>(systemKeyboard);
    engine=bytes;nativeRouting=native;inputTrace=logger;traceTime=0;
    if(nativeRouting){modern_input::Config config;config.engage=12000;config.release=5500;router=modern_input::Router(config);}
    gameWindow=reinterpret_cast<HWND*>(bytes+0xf1b44);
    InterlockedExchange(reinterpret_cast<LONG*>(slot),reinterpret_cast<LONG>(&keyboardBridge));
    DWORD ignored;
    if(!VirtualProtect(slot,sizeof(DWORD),previous,&ignored)) {
        InterlockedExchange(reinterpret_cast<LONG*>(slot),reinterpret_cast<LONG>(systemKeyboard));
        VirtualProtect(slot,sizeof(DWORD),previous,&ignored);return false;
    }
    if(logger)logger(passthroughOnly?L"INPUT_PASSTHROUGH_READY controller=false map_reserved_keys=prototype_flag source_keyboard=preserved":nativeRouting?L"MODERN_INPUT_READY backend=xinput1_4 route=native_world_and_ui menu=right_button":L"MODERN_INPUT_READY backend=xinput1_4 route=keyboard_poll menu=unmapped");
    if(nativeRouting&&!installWorldGamepad(module,logger)){
        if(VirtualProtect(slot,4,PAGE_READWRITE,&previous)){*slot=reinterpret_cast<DWORD>(systemKeyboard);VirtualProtect(slot,4,previous,&ignored);}return false;
    }
    if(nativeRouting&&!installGamepadUi(module,logger)){
        removeWorldGamepad(module);
        if(VirtualProtect(slot,4,PAGE_READWRITE,&previous)){*slot=reinterpret_cast<DWORD>(systemKeyboard);VirtualProtect(slot,4,previous,&ignored);}return false;
    }
    return true;
}
bool removeModernGamepad(HMODULE module){
    auto p=reinterpret_cast<BYTE*>(module);if(p!=engine||!readable(p,0x10b000))return false;
    auto slot=reinterpret_cast<DWORD*>(p+0xbd3dc);if(*slot!=reinterpret_cast<DWORD>(&keyboardBridge))return false;
    if(nativeRouting&&(!canSetWorldGamepad(module,false)||!canSetGamepadUi(module,false)))return false;
    if(nativeRouting&&!removeWorldGamepad(module))return false;
    if(nativeRouting&&!removeGamepadUi(module)){installWorldGamepad(module,nullptr);return false;}
    DWORD old;if(!VirtualProtect(slot,4,PAGE_READWRITE,&old)){if(nativeRouting){installWorldGamepad(module,nullptr);installGamepadUi(module,nullptr);}return false;}*slot=originalIat;DWORD ignored;
    if(!VirtualProtect(slot,4,old,&ignored)){*slot=reinterpret_cast<DWORD>(&keyboardBridge);VirtualProtect(slot,4,old,&ignored);if(nativeRouting){installWorldGamepad(module,nullptr);installGamepadUi(module,nullptr);}return false;}
    router=modern_input::Router();worldScope=false;movement={};InterlockedExchange(&mapPadButtons,0);return true;
}
