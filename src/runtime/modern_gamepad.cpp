#include "modern_gamepad.h"
#include "modern_input.h"
#include "battle_input.h"
#include "battle_edge.h"
#include "battle_pad_context.h"
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
using Message=BOOL(WINAPI*)(LPMSG,HWND,UINT,UINT);
Message originalMessage=nullptr;DWORD messageIat=0;
combat_input::SpaceEdgeLatch spaceEdges;BYTE* edgeScene=nullptr;bool physicalBattleInput=false;
Keyboard original=nullptr;
DWORD originalIat=0;
Poll poll=nullptr;
ULONG_PTR caller=0;
HWND* gameWindow=nullptr;
modern_input::Router router;modern_input::MenuDirection menuDirection;
bool cursorHidden=false,cursorArmed=false,cursorMenu=false;WORD cursorButtons=0;bool cursorRightEngaged=false;
SRWLOCK lock=SRWLOCK_INIT;
DWORD selected=0xffffffff;
bool backendTried=false;
combat_input::PadContextGate padContext;
bool battleReady=false;thread_local bool battleScope=false;combat_input::ComboAssist comboAssist;bool assistPadOwned=false,assistBurst=false;
bool nativeRouting=false;bool passthroughOnly=false,mapReservedKeys=false;volatile LONG mapPadButtons=0;
BYTE* engine=nullptr;
thread_local bool worldScope=false;
thread_local modern_input::MoveIntent movement;
thread_local bool pendingInteraction=false;
modern_input::Cursor controllerCursor;DWORD cursorTime=0;
GamepadNavigation navigation;DWORD inputSerial=0;unsigned navHeld=0;WORD lastButtons=0;
bool syntheticLeftOwned=false,syntheticRightOwned=false;unsigned syntheticLeftDevice=0xffffffff;volatile LONG cancelMenuPress=0;
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
BYTE* battleScene(void* frame){
 if(!battleReady||!readable(frame,8)||reinterpret_cast<BYTE**>(frame)[1]!=engine+0xa0b92)return nullptr;
 auto parent=*reinterpret_cast<BYTE**>(frame);if(reinterpret_cast<ULONG_PTR>(parent)<4||!readable(parent-4,4))return nullptr;
 auto scene=*reinterpret_cast<BYTE**>(parent-4);
 return readable(scene,0x1e04)&&*reinterpret_cast<BYTE**>(scene)==engine+0xc1960?scene:nullptr;
}
unsigned battleMode(BYTE* scene){
 if(!scene)return 0;
 auto gui=*reinterpret_cast<BYTE**>(scene+0x10fc);
 if(!readable(gui,0x1c0)||*reinterpret_cast<BYTE**>(gui)!=engine+0xc203c||*reinterpret_cast<BYTE**>(gui+0x1bc)!=scene)return 0;
 return *reinterpret_cast<unsigned*>(gui+0x190);
}
bool battleFocused(){
#ifdef MODERN_INPUT_TEST
 return fixtureForeground;
#else
 HWND front=GetForegroundWindow();DWORD owner=0;if(front)GetWindowThreadProcessId(front,&owner);
 return gameWindow&&front==*gameWindow&&owner==GetCurrentProcessId()&&!IsIconic(front);
#endif
}
bool edgeValid(BYTE* scene){return battleReady&&scene&&readable(scene,0x1e04)&&*reinterpret_cast<BYTE**>(scene)==engine+0xc1960&&*reinterpret_cast<int*>(scene+0x1dc4)==1;}
BOOL WINAPI messageHook(LPMSG msg,HWND window,UINT first,UINT last){
 auto source=reinterpret_cast<ULONG_PTR>(_ReturnAddress());
 BOOL result=originalMessage(msg,window,first,last);
 if(source==reinterpret_cast<ULONG_PTR>(engine+0xbe01)){
  bool valid=result>0&&msg&&battleFocused()&&edgeValid(edgeScene);
  if(!valid){spaceEdges.clear();edgeScene=nullptr;}
  else if((msg->message==WM_KILLFOCUS)||(msg->message==WM_ACTIVATEAPP&&!msg->wParam)){spaceEdges.clear();edgeScene=nullptr;}
  else if(gameWindow&&msg->hwnd==*gameWindow&&(msg->message==WM_KEYDOWN||msg->message==WM_KEYUP)&&msg->wParam==VK_SPACE)
   spaceEdges.message(reinterpret_cast<uintptr_t>(edgeScene),GetTickCount(),msg->time,msg->message==WM_KEYDOWN,(msg->lParam&(1ul<<30))!=0,true);
 }
 return result;
}
void battleEdge(PBYTE keys,BYTE* scene,bool focused){
 bool valid=keys&&focused&&edgeValid(scene);DWORD now=GetTickCount();
 bool edge=spaceEdges.consume(reinterpret_cast<uintptr_t>(scene),now,valid);edgeScene=valid?scene:nullptr;
 physicalBattleInput=valid&&(edge||(keys[VK_SPACE]&0x80));
 if(edge){
  // GetKeyboardState may have already observed the up from a presentation-only
  // pump. Reconstruct the real down edge at the next native sample, exactly once.
  keys[VK_SPACE]|=0x80;
  *reinterpret_cast<int*>(engine+0xf1c9c+VK_SPACE*sizeof(int))=0;
 }
}
void battleAssist(PBYTE keys,BYTE* scene,bool focused,bool padTrigger,bool padEligible){
 bool normalTrigger=keys&&(keys[VK_F10]&0x80),burstTrigger=keys&&(keys[VK_F11]&0x80);
 bool keyboardTrigger=normalTrigger||burstTrigger,trigger=keyboardTrigger||padTrigger;
 if(trigger)assistBurst=burstTrigger;
 combat_input::ComboState state{};
 state.burst=assistBurst;bool incompatible=false;
 if(scene){state.owner=reinterpret_cast<uintptr_t>(scene);state.active=*reinterpret_cast<int*>(scene+0x1dc4)==1;
  state.timed=*reinterpret_cast<int*>(scene+0x1dcc)==1;state.tick=*reinterpret_cast<unsigned*>(scene+0x1de0);state.count=*reinterpret_cast<unsigned*>(scene+0x1ddc);
  bool rageTimed=*reinterpret_cast<int*>(scene+0x1de8)==1;
  incompatible=assistBurst?state.timed:rageTimed;
  if(assistBurst){state.timed=rageTimed;state.tick=*reinterpret_cast<unsigned*>(scene+0x1df4);state.count=*reinterpret_cast<unsigned*>(scene+0x1df0);}
  state.actor=reinterpret_cast<uintptr_t>(*reinterpret_cast<BYTE**>(scene+0x40));state.action=*reinterpret_cast<unsigned*>(scene+0x1744);
  auto config=*reinterpret_cast<BYTE**>(engine+0xf2428);
  if(state.active&&readable(config,4)){
   using ConfigValue=int(__thiscall*)(void*,int);auto get=reinterpret_cast<ConfigValue>(engine+0xb5b0e);
   if(assistBurst){
    int duration=get(config,0x39),margin=get(config,0x3b);state.limit=get(config,0x3a);
    state.deadline=duration>=margin&&margin>=0&&duration<=600?unsigned(duration-margin):0;
    state.interval=3;state.window=state.precision=1;
   }else{state.interval=get(config,0x23);state.window=get(config,0x24);state.precision=get(config,0x25);}
  }
 }
 if(keyboardTrigger)assistPadOwned=false;
 else if(trigger&&!comboAssist.pending())assistPadOwned=padTrigger;
 bool eligible=focused&&keys&&battleMode(scene)==1&&!incompatible&&!(normalTrigger&&burstTrigger)&&!physicalBattleInput&&(!assistPadOwned||padEligible);
 if(comboAssist.update(state,trigger,eligible)){
  keys[VK_SPACE]|=0x80;
  if(inputTrace)inputTrace(assistBurst?L"BATTLE_COMBO_ASSIST_PULSE mode=rage key=F11 route=native_space clock=33ms_logic damage=unchanged":L"BATTLE_COMBO_ASSIST_PULSE route=native_space clock=33ms_logic damage=unchanged");
 }
}
void writeControllerCursor(int x,int y){
 *reinterpret_cast<int*>(engine+0xf20b0)=x;*reinterpret_cast<int*>(engine+0xf20a8)=y;
 // Native GetCursorPos refreshes these fields before the next keyboard poll.
 // Keep the real OS baseline separate from our virtual output; never acknowledge
 // a field write as an OS mouse movement (we do not call SetCursorPos).
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
    const bool physicalLeft=ok&&(keys[VK_LBUTTON]&0x80);
    const bool physicalRight=ok&&(keys[VK_RBUTTON]&0x80);
    InterlockedExchange(&cancelMenuPress,0);
    InterlockedExchange(&mapPadButtons,0);
    if(mapReservedKeys&&!worldScope)notifyWorldTickObserver(nullptr,false);
    if(ok&&mapReservedKeys){keys[VK_F8]=keys[VK_F9]=0;}
    DWORD owner=0;HWND front=GetForegroundWindow();
    if(front)GetWindowThreadProcessId(front,&owner);
    bool focused=gameWindow && front==*gameWindow && owner==GetCurrentProcessId() && !IsIconic(front);
#ifdef MODERN_INPUT_TEST
    focused=fixtureForeground;
#endif
    auto battle=battleScene(nativeFrame);battleScope=battle!=nullptr;
    unsigned mode=battleMode(battle);
    auto route=battle?combat_input::battlePadRoute(mode):combat_input::BattlePadRoute::Outside;
    bool battleKeys=route==combat_input::BattlePadRoute::Field||route==combat_input::BattlePadRoute::Result;
    bool battleBlocked=route==combat_input::BattlePadRoute::Blocked;
    battleEdge(ok?keys:nullptr,battle,focused);
    if(passthroughOnly){movement={};navigation={};battleAssist(ok?keys:nullptr,battle,focused,false,false);if(ok)orbitKeyboard(keys,focused);return ok;}
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
    if(!poll){battleAssist(ok?keys:nullptr,battle,focused,false,false);cursorHidden=cursorArmed=false;menuDirection=modern_input::MenuDirection();router.update({},false,false);ReleaseSRWLockExclusive(&lock);return ok;}
    modern_input::Sample sample{};XINPUT_STATE state{};
    if(selected!=0xffffffff && poll(selected,&state)==ERROR_SUCCESS) {
        sample.connected=true;sample.device=selected;
    }else {
        selected=0xffffffff;
        for(DWORD i=0;i<4;++i)if(poll(i,&state)==ERROR_SUCCESS){selected=i;sample.connected=true;sample.device=i;break;}
    }
    if(sample.connected){sample.buttons=state.Gamepad.wButtons;sample.x=state.Gamepad.sThumbLX;sample.y=state.Gamepad.sThumbLY;
        sample.rx=state.Gamepad.sThumbRX;sample.ry=state.Gamepad.sThumbRY;sample.lt=state.Gamepad.bLeftTrigger;sample.rt=state.Gamepad.bRightTrigger;}
    auto routedSample=sample;
    routedSample.buttons=padContext.update(reinterpret_cast<uintptr_t>(battle),mode,sample.buttons);
    bool cancelOwned=!ok||!focused||!sample.connected||sample.device!=syntheticLeftDevice||padContext.changed;
    if(nativeRouting&&syntheticLeftOwned&&!physicalLeft&&cancelOwned){
        // Native titles activate on mouse release. A disappearing controller is
        // cancellation, not a deliberate release; leave the real mouse untouched.
        auto counter=reinterpret_cast<int*>(engine+0xf1c9c+VK_LBUTTON*sizeof(int));
        if(readable(counter,sizeof(int))){*counter=0;InterlockedExchange(&cancelMenuPress,1);}
    }
    if(nativeRouting&&syntheticRightOwned&&!physicalRight&&cancelOwned){
        // B/Start use native right-button release for return/open. Device loss
        // cancels that owned press, not the physical mouse or deliberate release.
        auto counter=reinterpret_cast<int*>(engine+0xf1c9c+VK_RBUTTON*sizeof(int));
        if(readable(counter,sizeof(int))){*counter=0;if(!physicalLeft)InterlockedExchange(&cancelMenuPress,1);}
    }
    syntheticLeftOwned=syntheticRightOwned=false;
    auto frame=router.update(routedSample,ok!=FALSE,focused);int titlePhase=-1;
    if(battleBlocked)frame.held=frame.pressed=frame.released=0;
    // A/X are manual native confirmations. Preserve them, but cancel the
    // assist before mergeKeyboard can mask a synthetic key-up sample.
    if(nativeRouting&&frame.armed&&focused&&(sample.buttons&(XINPUT_GAMEPAD_A|XINPUT_GAMEPAD_X)))physicalBattleInput=true;
    battleAssist(ok?keys:nullptr,battle,focused,frame.armed&&focused&&(!battle||route==combat_input::BattlePadRoute::Field)&&(routedSample.buttons&XINPUT_GAMEPAD_RIGHT_THUMB),frame.armed&&focused&&sample.connected&&!padContext.changed);
    if(!ok){cursorHidden=cursorArmed=false;menuDirection.update(sample,false);}
    if(ok&&mapReservedKeys&&nativeRouting&&worldScope&&frame.armed&&focused)InterlockedExchange(&mapPadButtons,((sample.buttons&XINPUT_GAMEPAD_BACK)?1:0)|((sample.buttons&XINPUT_GAMEPAD_RIGHT_THUMB)?2:0));
    if(ok&&nativeRouting){
        bool clicksAllowed=true;
        uint8_t nativeBindings[7]={VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT,static_cast<uint8_t>(worldScope?0:combat_input::confirmKey(battleKeys,VK_LBUTTON)),VK_RBUTTON,VK_RBUTTON};
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
            menuDirection.update(sample,false);
            // Confirm is a scene interaction request, not a global UI Space key.
            pendingInteraction=frame.armed&&focused&&(frame.pressed&modern_input::Confirm)&&!(sample.buttons&XINPUT_GAMEPAD_X);
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
            frame.held=(frame.held&~15u)|menuDirection.update(routedSample,frame.armed&&focused&&!battleBlocked);
            if(!battleBlocked&&(routedSample.buttons&XINPUT_GAMEPAD_LEFT_SHOULDER))frame.held|=modern_input::Left;
            if(!battleBlocked&&(routedSample.buttons&XINPUT_GAMEPAD_RIGHT_SHOULDER))frame.held|=modern_input::Right;
            if(physicalArrows)frame.held&=~uint32_t(15);
        }
        modern_input::mergeKeyboard(keys,frame,nativeBindings);
        if(frame.armed&&focused&&!battleBlocked){
            // Dedicated X = original Space in all contexts, including dialogue.
            // A remains menu confirm / nearby interaction; never issue both routes.
            if(routedSample.buttons&XINPUT_GAMEPAD_X)keys[VK_SPACE]|=0x80;
            if(routedSample.buttons&XINPUT_GAMEPAD_Y)keys[VK_TAB]|=0x80;
        }
        syntheticLeftOwned=frame.armed&&focused&&!worldScope&&clicksAllowed&&!physicalLeft&&(keys[VK_LBUTTON]&0x80);
        syntheticRightOwned=frame.armed&&focused&&!physicalRight&&(keys[VK_RBUTTON]&0x80);
        if(syntheticLeftOwned||syntheticRightOwned)syntheticLeftDevice=sample.device;
        DWORD now=GetTickCount();unsigned elapsed=cursorTime?now-cursorTime:0;cursorTime=now;
        int w=*reinterpret_cast<int*>(engine+0xf1b48),h=*reinterpret_cast<int*>(engine+0xf1b4c);
        auto x=reinterpret_cast<int*>(engine+0xf20b0),y=reinterpret_cast<int*>(engine+0xf20a8);
        bool mouseMoved=realMouseKnown&&(*x!=realMouseX||*y!=realMouseY);realMouseKnown=true;realMouseX=*x;realMouseY=*y;
        bool eligible=frame.armed&&focused&&sample.connected&&!battleBlocked;
        cursorMenu=!worldScope; // Menus need a visible locator at their actual click point.
        bool rightEngaged=std::abs(int(sample.rx))>=8689||std::abs(int(sample.ry))>=8689;
        bool mouseUsed=mouseMoved||physicalLeft||physicalRight||*reinterpret_cast<int*>(engine+0xf20a0)!=0;
        bool padUsed=(frame.pressed!=0)||((sample.buttons&~cursorButtons)!=0)||(rightEngaged&&!cursorRightEngaged);
        if(!eligible)cursorHidden=false;
        else if(mouseUsed)cursorHidden=false;
        else if(!cursorArmed||padUsed)cursorHidden=true;
        cursorArmed=eligible;cursorButtons=sample.buttons;cursorRightEngaged=rightEngaged;
        if(mouseUsed){navMouseBlocked=true;controllerCursor.mouseInput();}if(!(frame.held&15))navMouseBlocked=false;
        auto point=controllerCursor.update(*x,*y,sample.rx,sample.ry,elapsed,w,h,eligible);
        if(point.owned)writeControllerCursor(static_cast<int>(point.x),static_cast<int>(point.y));
        navigation={frame.held&15,(frame.held&15)&~navHeld,++inputSerial,now,
                    frame.armed&&focused&&!worldScope&&!battleKeys&&!battleBlocked&&!keyboardDirection&&!navMouseBlocked
                    &&std::abs(int(sample.rx))<8689&&std::abs(int(sample.ry))<8689
                    &&!((sample.buttons|lastButtons)&(XINPUT_GAMEPAD_A|XINPUT_GAMEPAD_X|XINPUT_GAMEPAD_B|XINPUT_GAMEPAD_START))};
        navHeld=frame.held&15;lastButtons=sample.buttons;
        unsigned triggers=(sample.lt>=128?1u:0u)|(sample.rt>=128?2u:0u);
        if(frame.armed&&focused&&!worldScope&&!battleBlocked&&triggers&&triggers!=3&&(triggers!=triggerHeld||DWORD(now-triggerTime)>=150)){
            // WM_MOUSEWHEEL stores -(signed delta)/120 in this original field.
            *reinterpret_cast<int*>(engine+0xf20a0)=triggers==1?-1:1;triggerTime=now;
        }
        triggerHeld=triggers;
    }else if(ok)modern_input::mergeKeyboard(keys,frame,bindings);
    DWORD traceNow=GetTickCount();
    if(inputTrace&&(!traceTime||DWORD(traceNow-traceTime)>=1000)){
        traceTime=traceNow;wchar_t message[320];
        swprintf_s(message,L"INPUT_FRAME connected=%u slot=%u focused=%u armed=%u world=%u buttons=%04x actions=%02x native=%u title_phase=%d ui_active=%u mouse_blocked=%u cursor_hidden=%u space=%u",
            unsigned(sample.connected),selected,unsigned(focused),unsigned(frame.armed),unsigned(worldScope),unsigned(sample.buttons),unsigned(frame.held),unsigned(nativeRouting),titlePhase,unsigned(navigation.active),unsigned(navMouseBlocked),unsigned(cursorHidden&&!cursorMenu),unsigned(ok&&(keys[VK_SPACE]&0x80)!=0));
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
bool modernGamepadCursorHidden(){return cursorHidden&&!cursorMenu;}
bool modernGamepadMenuCancellation(){return InterlockedCompareExchange(&cancelMenuPress,0,0)!=0;}
bool modernGamepadConsumeInteraction(){bool value=worldScope&&pendingInteraction;pendingInteraction=false;return value;}
modern_input::MoveIntent modernGamepadMoveIntent(){return worldScope?movement:modern_input::MoveIntent{};}
unsigned modernGamepadMapButtons(){return static_cast<unsigned>(InterlockedCompareExchange(&mapPadButtons,0,0));}
GamepadNavigation modernGamepadNavigation(){return navigation;}
void modernGamepadFocusCursor(float x,float y){if(!nativeRouting||!engine||!navigation.active)return;int w=*reinterpret_cast<int*>(engine+0xf1b48),h=*reinterpret_cast<int*>(engine+0xf1b4c);controllerCursor.focus(x,y,w,h);writeControllerCursor(static_cast<int>(x),static_cast<int>(y));}

#ifdef MODERN_INPUT_TEST
void configureModernGamepadFixture(BOOL(WINAPI* keyboard)(PBYTE),DWORD(WINAPI* controller)(DWORD,XINPUT_STATE*),bool front) {
    original=keyboard;poll=controller;backendTried=true;fixtureForeground=front;
}
void configureModernNavigationFixture(BYTE* p,GamepadNavigation n){engine=p;nativeRouting=true;navigation=n;}
void configureModernBattleFixture(bool native){nativeRouting=native;}
BOOL modernBattleKeyboardFixture(PBYTE keys,void* frame){return keyboardInner(keys,caller,frame);}
#endif

bool installModernGamepad(HMODULE module,void(*logger)(const wchar_t*),bool battleOnly) {
    auto bytes=reinterpret_cast<BYTE*>(module);
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(bytes);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<=0 || dos->e_lfanew>4096)return false;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(bytes+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC || nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
    if(bytes[0x2fca]!=0x68 || *reinterpret_cast<DWORD*>(bytes+0x2fcb)!=reinterpret_cast<DWORD>(bytes+0xf1b94) ||
       bytes[0x2fcf]!=0xff || bytes[0x2fd0]!=0x15 || *reinterpret_cast<DWORD*>(bytes+0x2fd1)!=reinterpret_cast<DWORD>(bytes+0xbd3dc))return false;
    const BYTE ctor[]={0xc7,0x00};
    const BYTE messageCall[]={0xff,0x15};
    if(bytes[0xae411]!=0xc7||bytes[0xae412]!=0x02||*reinterpret_cast<DWORD*>(bytes+0xae413)!=reinterpret_cast<DWORD>(bytes+0xc203c)
       ||memcmp(bytes+0x9d424,ctor,2)||*reinterpret_cast<DWORD*>(bytes+0x9d426)!=reinterpret_cast<DWORD>(bytes+0xc1960)
       ||memcmp(bytes+0xbdfb,messageCall,2)||*reinterpret_cast<DWORD*>(bytes+0xbdfd)!=reinterpret_cast<DWORD>(bytes+0xbd42c))return false;
    auto messageSlot=reinterpret_cast<DWORD*>(bytes+0xbd42c);
    auto slot=reinterpret_cast<DWORD*>(bytes+0xbd3dc);
    if(*slot==reinterpret_cast<DWORD>(&keyboardBridge))return engine==bytes&&*messageSlot==reinterpret_cast<DWORD>(&messageHook)&&(!nativeRouting||(canSetWorldGamepad(module,true)&&canSetGamepadUi(module,true)));
    auto systemKeyboard=reinterpret_cast<Keyboard>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetKeyboardState"));
    if(!systemKeyboard || *slot!=reinterpret_cast<DWORD>(systemKeyboard))return false;
    auto systemMessage=reinterpret_cast<Message>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetMessageA"));
    if(!systemMessage||*messageSlot!=reinterpret_cast<DWORD>(systemMessage))return false;
    wchar_t passFlag[8]{};passthroughOnly=GetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",passFlag,8)==1&&passFlag[0]==L'1';passthroughOnly=passthroughOnly||battleOnly;
    mapReservedKeys=GetEnvironmentVariableW(L"MC_MAP_OVERLAY",passFlag,8)==1&&passFlag[0]==L'1';
    wchar_t mode[8]{};bool native=GetEnvironmentVariableW(L"MC_GAMEPAD_NATIVE",mode,8)==1&&mode[0]==L'1'&&!battleOnly;
    if(native&&passthroughOnly)return false;
    if(native&&(!canSetWorldGamepad(module,true)||!canSetGamepadUi(module,true)))return false;
    DWORD previous;
    if(!VirtualProtect(slot,sizeof(DWORD),PAGE_READWRITE,&previous))return false;
    original=systemKeyboard;caller=reinterpret_cast<ULONG_PTR>(bytes+0x2fd5);
    originalIat=reinterpret_cast<DWORD>(systemKeyboard);
    engine=bytes;nativeRouting=native;inputTrace=logger;traceTime=0;
    const BYTE battleCall[]={0xe8,0x03,0x24,0xf6,0xff,0x8b,0x45,0xfc};
    const BYTE comboTimer[]={0x8b,0x88,0xe0,0x1d,0,0,0x83,0xc1,1};
    battleReady=!memcmp(bytes+0xa0b8d,battleCall,sizeof(battleCall))&&!memcmp(bytes+0xa1711,comboTimer,sizeof(comboTimer))
       &&*reinterpret_cast<DWORD*>(bytes+0xc1964)==reinterpret_cast<DWORD>(bytes+0xa0b7e);
    padContext.reset();comboAssist.reset();assistPadOwned=assistBurst=false;battleScope=false;spaceEdges.clear();edgeScene=nullptr;
    if(battleReady&&logger)logger(L"BATTLE_INPUT_READY field_A=Space menu_A=LMB B=RMB_release assist=F10_or_R3 rage_assist=F11 scope=source_locked clock=logic_ticks");
    if(nativeRouting){modern_input::Config config;config.engage=12000;config.release=5500;router=modern_input::Router(config);}
    gameWindow=reinterpret_cast<HWND*>(bytes+0xf1b44);
    originalMessage=systemMessage;messageIat=reinterpret_cast<DWORD>(systemMessage);
    InterlockedExchange(reinterpret_cast<LONG*>(messageSlot),reinterpret_cast<LONG>(&messageHook));
    InterlockedExchange(reinterpret_cast<LONG*>(slot),reinterpret_cast<LONG>(&keyboardBridge));
    DWORD ignored;
    if(!VirtualProtect(slot,sizeof(DWORD),previous,&ignored)) {
        InterlockedExchange(reinterpret_cast<LONG*>(messageSlot),reinterpret_cast<LONG>(systemMessage));
        InterlockedExchange(reinterpret_cast<LONG*>(slot),reinterpret_cast<LONG>(systemKeyboard));
        VirtualProtect(slot,sizeof(DWORD),previous,&ignored);return false;
    }
    if(logger)logger(passthroughOnly?L"INPUT_PASSTHROUGH_READY controller=false map_reserved_keys=prototype_flag source_keyboard=preserved":nativeRouting?L"MODERN_INPUT_READY backend=xinput1_4 route=native_world_and_ui menu=right_button":L"MODERN_INPUT_READY backend=xinput1_4 route=keyboard_poll menu=unmapped");
    if(nativeRouting&&!installWorldGamepad(module,logger)){
        if(VirtualProtect(slot,4,PAGE_READWRITE,&previous)){*messageSlot=reinterpret_cast<DWORD>(systemMessage);*slot=reinterpret_cast<DWORD>(systemKeyboard);VirtualProtect(slot,4,previous,&ignored);}return false;
    }
    if(nativeRouting&&!installGamepadUi(module,logger)){
        removeWorldGamepad(module);
        if(VirtualProtect(slot,4,PAGE_READWRITE,&previous)){*messageSlot=reinterpret_cast<DWORD>(systemMessage);*slot=reinterpret_cast<DWORD>(systemKeyboard);VirtualProtect(slot,4,previous,&ignored);}return false;
    }
    return true;
}
bool removeModernGamepad(HMODULE module){
    auto p=reinterpret_cast<BYTE*>(module);if(p!=engine||!readable(p,0x10b000))return false;
    auto slot=reinterpret_cast<DWORD*>(p+0xbd3dc);if(*slot!=reinterpret_cast<DWORD>(&keyboardBridge)||*reinterpret_cast<DWORD*>(p+0xbd42c)!=reinterpret_cast<DWORD>(&messageHook))return false;
    if(nativeRouting&&(!canSetWorldGamepad(module,false)||!canSetGamepadUi(module,false)))return false;
    if(nativeRouting&&!removeWorldGamepad(module))return false;
    if(nativeRouting&&!removeGamepadUi(module)){installWorldGamepad(module,nullptr);return false;}
    DWORD old;if(!VirtualProtect(slot,4,PAGE_READWRITE,&old)){if(nativeRouting){installWorldGamepad(module,nullptr);installGamepadUi(module,nullptr);}return false;}*slot=originalIat;*reinterpret_cast<DWORD*>(p+0xbd42c)=messageIat;DWORD ignored;
    if(!VirtualProtect(slot,4,old,&ignored)){*slot=reinterpret_cast<DWORD>(&keyboardBridge);*reinterpret_cast<DWORD*>(p+0xbd42c)=reinterpret_cast<DWORD>(&messageHook);VirtualProtect(slot,4,old,&ignored);if(nativeRouting){installWorldGamepad(module,nullptr);installGamepadUi(module,nullptr);}return false;}
    padContext.reset();spaceEdges.clear();edgeScene=nullptr;comboAssist.reset();battleScope=battleReady=false;assistPadOwned=assistBurst=false;router=modern_input::Router();menuDirection=modern_input::MenuDirection();cursorHidden=cursorArmed=cursorRightEngaged=cursorMenu=false;cursorButtons=0;worldScope=false;movement={};syntheticLeftOwned=syntheticRightOwned=false;syntheticLeftDevice=0xffffffff;InterlockedExchange(&cancelMenuPress,0);InterlockedExchange(&mapPadButtons,0);return true;
}
