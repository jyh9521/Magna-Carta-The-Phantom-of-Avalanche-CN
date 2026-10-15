#include "modern_gamepad.h"
#include "world_gamepad.h"
#include "gamepad_ui.h"
#include "camera_input_view.h"
#include <Xinput.h>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <cwchar>
static BYTE* image=nullptr;static BYTE world[0x15c4],actor[0x340],gui[0x194],cameraData[0xc0];
static int physicalX=0,physicalY=0;static DWORD controllerSlot=0;
static bool connected=true,physical=false,rawUp=false,physicalMouseDown=false,physicalRightDown=false;static SHORT axisX=0,axisY=0,rightX=0;static WORD buttons=0;static int checks=0,forwardCalls=0,turnCalls=0,interactions=0;static int observations=0;static bool observationControlled=false;
void require(bool,const char*);
int __fastcall interaction(void* s,void*,void* g,unsigned event){require(s==world&&g==gui&&event==0x11,"interaction uses native scene and GUI event");++interactions;if(*reinterpret_cast<int*>(world+0x15b8))*reinterpret_cast<int*>(world+0x15bc)=1;return 0;}
void observe(BYTE* s,bool controlled){if(s==world){++observations;observationControlled=controlled;}}
void require(bool v,const char* s){++checks;if(!v){fprintf(stderr,"FAIL %s\n",s);ExitProcess(1);}}
BOOL WINAPI keyboard(PBYTE keys){*reinterpret_cast<int*>(image+0xf20b0)=physicalX;*reinterpret_cast<int*>(image+0xf20a8)=physicalY;memset(keys,0,256);keys[VK_SPACE]=1;if(rawUp)keys[VK_UP]=0x80;if(physical)keys[VK_LEFT]=0x80;if(physicalMouseDown)keys[VK_LBUTTON]=0x80;if(physicalRightDown)keys[VK_RBUTTON]=0x80;return TRUE;}
DWORD WINAPI poll(DWORD slot,XINPUT_STATE* s){if(slot!=controllerSlot||!connected)return ERROR_DEVICE_NOT_CONNECTED;*s={};s->Gamepad.sThumbLX=axisX;s->Gamepad.sThumbLY=axisY;s->Gamepad.sThumbRX=rightX;s->Gamepad.wButtons=buttons;return ERROR_SUCCESS;}
static int cursorRecords=0,cursorLimits=0;static wchar_t lastCursorRecord[512]{};
void captureCursor(const wchar_t* line){if(wcsncmp(line,L"INPUT_CURSOR_DRAW ",18)==0){++cursorRecords;wcscpy_s(lastCursorRecord,line);}if(wcsncmp(line,L"INPUT_CURSOR_TRACE_LIMIT ",25)==0)++cursorLimits;}
static int cursorPrepares=0;void __fastcall cursorPrepare(void*,void*){++cursorPrepares;}
static int cursorDraws=0;void __fastcall cursorDraw(void*,void*){++cursorDraws;}
void __fastcall clearNativePress(void* button,void*){*reinterpret_cast<int*>(static_cast<BYTE*>(button)+0x19c)=0;}
void __fastcall heading(void* p,void*,float x,float y,float z){++turnCalls;auto d=reinterpret_cast<float*>(static_cast<BYTE*>(p)+0x148);d[0]=x;d[1]=y;d[2]=z;}
void __fastcall forward(void* p,void*){++forwardCalls;auto d=reinterpret_cast<float*>(static_cast<BYTE*>(p)+0x148),v=reinterpret_cast<float*>(static_cast<BYTE*>(p)+0x16c);for(int i=0;i<3;++i)v[i]=30*d[i];}
static unsigned titleRequests=0;static unsigned titleCommands[8]{};
static BYTE* replayMenu=nullptr;static int menuPresses=0,menuReleases=0,menuHolds=0,menuIdle=0,lastPressed=-1,lastReleased=-1;
int __fastcall titleListener(void* listener,void*,void* sender,unsigned event,unsigned,unsigned){
 auto title=*reinterpret_cast<BYTE**>(static_cast<BYTE*>(listener)+0x1a8);
 if(!title||*reinterpret_cast<int*>(title+0x70)<=3||event!=0x3c)return 0;
 unsigned id=*reinterpret_cast<unsigned*>(static_cast<BYTE*>(sender)+4),command=0;
 switch(id){case 0x16c:command=6;break;case 0x16d:command=7;break;case 0x16e:command=9;break;case 0x16f:command=11;break;default:return 0;}
 // Record the source listener's transition request, not execute a game task.
 require(titleRequests<8,"owned title command recording remains bounded");titleCommands[titleRequests++]=command;return 0;
}
static int rightReleases=0,worldMenuRequests=0;
void __fastcall rightReleased(void* widget,void*){
 ++rightReleases;
 // Source-shaped 80932 -> 6e6d8 event 40 -> 6e246 request 5.
 // Record the mode request; do not execute commercial scene transition tasks.
 if(widget==gui&&*reinterpret_cast<int*>(gui+4)==0x42&&*reinterpret_cast<int*>(gui+0x190)==1){++worldMenuRequests;*reinterpret_cast<int*>(world+0x156c)=5;}
}
void emitMenuEvent(void* widget,unsigned event){
 auto listener=*reinterpret_cast<BYTE**>(static_cast<BYTE*>(widget)+0x17c);if(!listener)return;
 auto table=*reinterpret_cast<BYTE**>(listener);
 using Event=int(__thiscall*)(void*,void*,unsigned,unsigned,unsigned);
 reinterpret_cast<Event>(*reinterpret_cast<DWORD*>(table+0x24))(listener,widget,event,0,0);
}
int __fastcall keyboardGui(void*,void*){return 0;}
void __fastcall menuPressed(void* widget,void*){++menuPresses;lastPressed=*reinterpret_cast<int*>(static_cast<BYTE*>(widget)+4);emitMenuEvent(widget,0x3b);*reinterpret_cast<int*>(static_cast<BYTE*>(widget)+0x19c)=1;}
void __fastcall menuHeld(void* widget,void*){++menuHolds;emitMenuEvent(widget,0x39);}
void __fastcall menuIdleEvent(void* widget,void*){++menuIdle;emitMenuEvent(widget,0x3a);}
void __fastcall menuReleased(void* widget,void*){++menuReleases;lastReleased=*reinterpret_cast<int*>(static_cast<BYTE*>(widget)+4);emitMenuEvent(widget,0x3c);*reinterpret_cast<int*>(static_cast<BYTE*>(widget)+0x19c)=0;}
// Controlled replay of the verified 02f95 counters and 557ee mouse dispatch.
// The original game DLL is not loaded or executed by this fixture.
int replayMouse(BYTE* root){
 for(auto child=*reinterpret_cast<BYTE**>(root+0x18);child;child=*reinterpret_cast<BYTE**>(child+0x10))if(replayMouse(child)==1)return 1;
 if(!*reinterpret_cast<int*>(root+0x160)||!*reinterpret_cast<int*>(root+0xe8))return 0;
 auto node=*reinterpret_cast<BYTE**>(root+0x100);if(!node)return 0;auto rect=*reinterpret_cast<int**>(node);
 int x=*reinterpret_cast<int*>(image+0xf20b0),y=*reinterpret_cast<int*>(image+0xf20a8);
 if(x<rect[0]||x>rect[2]||y<rect[1]||y>rect[3])return 0;
 auto table=*reinterpret_cast<BYTE**>(root);auto state=*reinterpret_cast<int*>(image+0xf1c9c+VK_LBUTTON*4);
 if(state==1)reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(table+0x188))(root);
 if(state>0)reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(table+0x18c))(root);
 if(state==0)reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(table+0x190))(root);
 if(state==-1)reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(table+0x194))(root);
 auto rightState=*reinterpret_cast<int*>(image+0xf1c9c+VK_RBUTTON*4);
 if(rightState==-1)reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(table+0x1a4))(root);
 return 1;
}
void replayMenuInput(){
 auto keys=image+0xf1b94;auto state=reinterpret_cast<int*>(image+0xf1c9c);
 for(unsigned k=0;k<256;++k){if(keys[k]&0x80)++state[k];else state[k]=state[k]>=1?-1:0;}
 auto table=*reinterpret_cast<BYTE**>(replayMenu);
 reinterpret_cast<int(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(table+0x1c8))(replayMenu);
 replayMouse(replayMenu);
}
void __fastcall tick(void*,void*){
 reinterpret_cast<BOOL(__cdecl*)()>(image+0x2fca)();auto keys=image+0xf1b94;if(rawUp)keyboard(keys); // owned raw-key buffer; no OS input injection
 if(keys[VK_UP]&0x80)reinterpret_cast<void(__thiscall*)(void*)>(image+0x6e760)(actor);
 else memset(actor+0x16c,0,12);
 if(replayMenu)replayMenuInput();
}
void stub(unsigned rva,const BYTE* prefix,unsigned n,void* fn){
 memcpy(image+rva,prefix,n);BYTE* p=image+rva+n;*p++=0x8b;*p++=0xe5;*p++=0x5d;*p++=0xe9;*reinterpret_cast<int32_t*>(p)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(fn)-reinterpret_cast<ULONG_PTR>(p+4));
}
int main(int argc,char** argv){
 const bool menuDispatchOnly=argc==2&&!strcmp(argv[1],"--menu-dispatch-only");
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image!=nullptr,"owned image");
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 image[0x2fca]=0x68;*reinterpret_cast<DWORD*>(image+0x2fcb)=reinterpret_cast<DWORD>(image+0xf1b94);image[0x2fcf]=0xff;image[0x2fd0]=0x15;*reinterpret_cast<DWORD*>(image+0x2fd1)=reinterpret_cast<DWORD>(image+0xbd3dc);image[0x2fd5]=0xc3;
 initializeGamepadUiFixture(image);BYTE clearPrefix[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc};stub(0x5718f,clearPrefix,sizeof(clearPrefix),reinterpret_cast<void*>(&clearNativePress));
 BYTE guiPrefix[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xf8};stub(0x55134,guiPrefix,sizeof(guiPrefix),reinterpret_cast<void*>(&keyboardGui));stub(0x38c24,guiPrefix,sizeof(guiPrefix),reinterpret_cast<void*>(&cursorPrepare));stub(0x48774,clearPrefix,sizeof(clearPrefix),reinterpret_cast<void*>(&cursorDraw));
 auto iat=reinterpret_cast<DWORD*>(image+0xbd3dc);DWORD oldIat=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetKeyboardState"));*iat=oldIat;
 BYTE t[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc},f[]={0x55,0x8b,0xec,0x83,0xec,0x54,0x89,0x4d,0xac},d[]={0x55,0x8b,0xec,0x83,0xec,0x1c,0x89,0x4d,0xec};
 stub(0x6b2d8,t,sizeof(t),reinterpret_cast<void*>(&tick));stub(0x652b4,f,sizeof(f),reinterpret_cast<void*>(&forward));stub(0x65504,d,sizeof(d),reinterpret_cast<void*>(&heading));
 BYTE eventPrefix[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xfc};stub(0x6e6d8,eventPrefix,sizeof(eventPrefix),reinterpret_cast<void*>(&interaction));
 *reinterpret_cast<DWORD*>(image+0xc12c0)=reinterpret_cast<DWORD>(image+0x6b2d8);*reinterpret_cast<DWORD*>(image+0xc1258)=reinterpret_cast<DWORD>(image+0x652b4);*reinterpret_cast<DWORD*>(image+0xc12a0)=reinterpret_cast<DWORD>(image+0x65504);
 BYTE entry[]={0x55,0x8b,0xec,0x8b,0x11};memcpy(image+0x6e760,entry,5);memset(image+0x6e765,0x90,0x19);BYTE call[]={0xff,0x52,0x74,0x5d,0xc3};memcpy(image+0x6e77e,call,5);
 *reinterpret_cast<DWORD*>(world)=reinterpret_cast<DWORD>(image+0xc12bc);*reinterpret_cast<BYTE**>(world+0x1564)=actor;*reinterpret_cast<BYTE**>(world+0x10c8)=gui;*reinterpret_cast<int*>(gui+0x190)=1;
 *reinterpret_cast<DWORD*>(actor)=reinterpret_cast<DWORD>(image+0xc11e4);*reinterpret_cast<BYTE**>(actor+0x20)=world;*reinterpret_cast<BYTE**>(image+0xf2290)=cameraData;
 *reinterpret_cast<int*>(gui+4)=0x42;
 auto view=reinterpret_cast<float*>(cameraData+0x80);view[0]=view[5]=view[10]=view[15]=1;
 require(installWorldGamepad(reinterpret_cast<HMODULE>(image),nullptr),"passive observer installer without XInput IAT");
 rawUp=true;*reinterpret_cast<float*>(actor+0x148)=1;reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(image+0xc12c0))(world);
 require(*reinterpret_cast<float*>(actor+0x16c)==30&&turnCalls==0&&*iat==oldIat,"passive observer preserves native keyboard movement and IAT");rawUp=false;
 require(removeWorldGamepad(reinterpret_cast<HMODULE>(image)),"passive observer exact hook rollback");
 SetEnvironmentVariableW(L"MC_MAP_OVERLAY",L"1");SetEnvironmentVariableW(L"MC_GAMEPAD_NATIVE",L"1");require(installModernGamepad(reinterpret_cast<HMODULE>(image),captureCursor),"integrated installer");require(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr),"idempotence");configureModernGamepadFixture(keyboard,poll,true);
 auto run=[](){reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(image+0xc12c0))(world);};
 setWorldTickObserver(&observe);run();require(observations==1&&observationControlled,"read-only observer runs after native tick");setWorldTickObserver(nullptr);run();require(observations==1,"observer removal preserves native tick");
 BYTE currentCursor[0x144]{},otherSprite[0x144]{};*reinterpret_cast<BYTE**>(image+0xf2388)=currentCursor;
 auto drawCursor=[&](void* value){reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(image+0xbe380))(value);};
 require(modernGamepadCursorHidden(),"detected armed controller hides game cursor");
 reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(image+0xbe38c))(currentCursor);require(cursorPrepares==1,"hidden cursor still executes original position preparation");
 drawCursor(currentCursor);require(cursorDraws==0,"current game cursor rendering suppressed");
 require(cursorRecords==1&&wcsstr(lastCursorRecord,L"decision=skip")&&wcsstr(lastCursorRecord,L"observation=draw_entry"),"cursor decision evidence must distinguish actual draw entry from input readiness");
 drawCursor(otherSprite);require(cursorDraws==1,"shared cursor class unrelated sprite draws preserved");
 require(cursorRecords==1,"unrelated sprite must not produce current-cursor evidence");drawCursor(currentCursor);require(cursorRecords==1,"unchanged draw state must not repeat cursor evidence");
 physicalX=1;run();require(!modernGamepadCursorHidden(),"raw physical mouse motion restores game cursor in same poll");drawCursor(currentCursor);require(cursorDraws==2,"mouse-restored cursor calls original draw");
 require(cursorRecords==2&&wcsstr(lastCursorRecord,L"decision=original")&&wcsstr(lastCursorRecord,L"native_blocked=0")&&wcsstr(lastCursorRecord,L"pixels=not_observed"),"mouse restore evidence records original entry not visible pixels");
 run();require(!modernGamepadCursorHidden(),"idle connected controller does not steal mouse mode back");
 buttons=XINPUT_GAMEPAD_DPAD_UP;run();require(modernGamepadCursorHidden(),"fresh controller action hides cursor again");buttons=0;run();
 physicalMouseDown=true;run();require(!modernGamepadCursorHidden(),"physical mouse click restores cursor without movement");
 require(*reinterpret_cast<int*>(image+0xf20b0)==physicalX&&*reinterpret_cast<int*>(image+0xf20a8)==physicalY,"physical click restores raw cursor position not previous virtual focus");physicalMouseDown=false;run();
 buttons=XINPUT_GAMEPAD_DPAD_UP;run();buttons=0;run();*reinterpret_cast<int*>(image+0xf20a0)=1;run();require(!modernGamepadCursorHidden(),"physical wheel restores cursor");*reinterpret_cast<int*>(image+0xf20a0)=0;
 connected=false;run();require(!modernGamepadCursorHidden(),"disconnection restores cursor");connected=true;run();run();require(modernGamepadCursorHidden(),"neutral reconnect hides cursor after arming");
 printf("GAMEPAD_CURSOR_VISIBILITY_REPLAY PASS detected=hidden motion_click_wheel=restore idle_pad=no_steal fresh_pad=hide unrelated_sprite=preserved disconnect=restore game_started=false\n");
 int turnsBeforeMovement=turnCalls;axisX=32767;run();auto velocity=reinterpret_cast<float*>(actor+0x16c);
 require(velocity[0]>29.9f&&std::abs(velocity[1])<.001f&&turnCalls==turnsBeforeMovement+1,"right stick direction becomes forward movement not tank turn");
 require((image[0xf1b94+VK_UP]&0x80)&&!(image[0xf1b94+VK_RIGHT]&0x80),"native forward key without tank steering");
 axisX=18000;run();require(velocity[0]>0&&velocity[0]<30,"analog speed scales native velocity");
 view[0]=0;view[4]=1;view[1]=-1;view[5]=0;axisX=32767;run();require(velocity[1]>29.9f&&std::abs(velocity[0])<.001f,"camera-relative actual native callback");
 float displayed[16]{};displayed[0]=displayed[5]=displayed[10]=displayed[15]=1;
 render_input::inputView.publish(displayed,reinterpret_cast<uintptr_t>(cameraData),GetTickCount(),true);
 run();require(velocity[0]>29.9f&&std::abs(velocity[1])<.001f,"orbit movement follows displayed view instead of unmodified engine view");
 physical=true;run();require(velocity[0]<-29.9f&&!(image[0xf1b94+VK_LEFT]&0x80)&&(image[0xf1b94+VK_UP]&0x80),"physical arrows use displayed orbit direction without tank steering");physical=false;
 render_input::inputView.reset();run();require(velocity[1]>29.9f&&std::abs(velocity[0])<.001f,"orbit off restores source camera movement");
 physical=true;run();require(velocity[0]==0&&velocity[1]==0&&(image[0xf1b94+VK_LEFT]&0x80),"physical keyboard wins");physical=false;
 connected=false;run();require(velocity[0]==0&&velocity[1]==0,"disconnect stops");connected=true;run();run();require(velocity[0]==0&&velocity[1]==0,"held reconnect cannot resume");axisX=0;run();axisY=32767;run();require(std::abs(velocity[0])>29.9f,"neutral rearm then continuous direction");
 *reinterpret_cast<int*>(world+0x15b8)=1;
 axisY=0;buttons=XINPUT_GAMEPAD_A;run();require(image[0xf1b94+VK_SPACE]==1&&interactions==1,"exploration A dispatches interaction without injecting menu Space");
 require(*reinterpret_cast<int*>(world+0x15bc)==1,"nearby interaction request comes from native handler");
 run();require(interactions==1,"held A cannot dispatch interaction twice");
 *reinterpret_cast<int*>(world+0x15b8)=0;*reinterpret_cast<int*>(world+0x15bc)=0;
 buttons=0;run();buttons=XINPUT_GAMEPAD_A;run();require(interactions==2&&!*reinterpret_cast<int*>(world+0x15bc),"native proximity gate prevents remote interaction");
 buttons=0;run();*reinterpret_cast<int*>(gui+0x190)=4;
 axisX=13000;axisY=0;run();
 require(!modernGamepadCursorHidden(),"menu must expose its exact native click position instead of hiding all focus feedback");
 int menuCursorDraws=cursorDraws;drawCursor(currentCursor);require(cursorDraws==menuCursorDraws+1,"menu locator calls original cursor draw at exact native hit coordinates");
 *reinterpret_cast<int*>(currentCursor+0x118)=-1;*reinterpret_cast<float*>(currentCursor+0x24)=123.5f;*reinterpret_cast<float*>(currentCursor+0x28)=456.25f;
 BYTE cursorSnapshot[sizeof(currentCursor)];memcpy(cursorSnapshot,currentCursor,sizeof(currentCursor));drawCursor(currentCursor);
 require(wcsstr(lastCursorRecord,L"native_order=-1")&&wcsstr(lastCursorRecord,L"native_blocked=1")&&wcsstr(lastCursorRecord,L"sprite_x=123.500"),"original native hide state and sprite position must be observable separately from hook decision");
 require(!memcmp(cursorSnapshot,currentCursor,sizeof(currentCursor)),"cursor evidence cannot change original object or visibility state");
 *reinterpret_cast<int*>(currentCursor+0x118)=0;
 *reinterpret_cast<float*>(currentCursor+0x24)=std::nanf("");drawCursor(currentCursor);
 require(wcsstr(lastCursorRecord,L"sprite_finite=0"),"nonfinite cursor position is explicitly marked in evidence");
 require(std::isnan(*reinterpret_cast<float*>(currentCursor+0x24)),"nonfinite normalization must affect the log only");*reinterpret_cast<float*>(currentCursor+0x24)=123.5f;
 for(int i=0;i<300;++i){*reinterpret_cast<int*>(image+0xf20b0)=i;drawCursor(currentCursor);}
 require(cursorRecords==64&&cursorLimits==1,"cursor evidence is bounded to 64 changed states and one explicit limit");
 require(installGamepadUi(reinterpret_cast<HMODULE>(image),captureCursor),"idempotent GUI install retains trace budget");
 *reinterpret_cast<int*>(image+0xf20b0)=999;drawCursor(currentCursor);require(cursorRecords==64&&cursorLimits==1,"idempotence must not reset or repeat cursor trace limit");
 printf("GAMEPAD_CURSOR_EVIDENCE_REPLAY PASS draw_entry=true original_flags=true unchanged_state=deduplicated object=unchanged limit=64 limit_notice=once pixels=not_observed game_started=false\n");

 printf("GAMEPAD_MENU_LOCATOR_REPLAY PASS menu=visible exploration=hidden mouse_restore=retained native_hit_position=exact game_started=false\n");require(!(image[0xf1b94+VK_RIGHT]&0x80),"menu moderate stick drift does not move selection");
 axisX=20000;axisY=23000;run();require((image[0xf1b94+VK_UP]&0x80)&&!(image[0xf1b94+VK_RIGHT]&0x80),"menu diagonal has exactly one dominant axis");
 axisY=-26000;run();require((image[0xf1b94+VK_DOWN]&0x80)&&!(image[0xf1b94+VK_UP]&0x80),"fast stick reversal must reverse menu direction without requiring a sampled neutral frame");
 axisY=23000;run();require((image[0xf1b94+VK_UP]&0x80)&&!(image[0xf1b94+VK_DOWN]&0x80),"reverse back on latched menu axis");
 axisX=25000;axisY=12000;run();require((image[0xf1b94+VK_UP]&0x80)&&!(image[0xf1b94+VK_RIGHT]&0x80),"menu diagonal noise cannot switch a latched direction");
 axisY=0;run();require((image[0xf1b94+VK_RIGHT]&0x80)&&!(image[0xf1b94+VK_UP]&0x80),"releasing old axis permits a new dominant axis without full-stick neutral");
 axisX=axisY=0;run();axisX=32767;run();require((image[0xf1b94+VK_RIGHT]&0x80)&&!(image[0xf1b94+VK_UP]&0x80),"recenter permits a fresh menu direction");
 axisX=-32768;run();require((image[0xf1b94+VK_LEFT]&0x80)&&!(image[0xf1b94+VK_RIGHT]&0x80),"horizontal menu stick reverses across full signed endpoint without sampled neutral");
 axisX=12000;run();require(!(image[0xf1b94+VK_LEFT]&0x80)&&!(image[0xf1b94+VK_RIGHT]&0x80),"weak opposite stick input stops obsolete direction without engaging a new one");
 axisX=32767;run();require((image[0xf1b94+VK_RIGHT]&0x80)&&!(image[0xf1b94+VK_LEFT]&0x80),"horizontal menu reversal restores right direction");
 printf("GAMEPAD_STICK_REVERSAL_REPLAY PASS vertical=immediate horizontal=immediate neutral_sample=not_required cross_axis_noise=latched signed_endpoint=valid game_started=false\n");
 buttons=XINPUT_GAMEPAD_DPAD_DOWN;run();require((image[0xf1b94+VK_DOWN]&0x80)&&!(image[0xf1b94+VK_RIGHT]&0x80),"Dpad overrides held menu stick without competing keys");
 axisX=axisY=0;buttons=0;run();printf("GAMEPAD_MENU_PRECISION_REPLAY PASS engage=19000 release=11000 diagonal=one_axis direction=latched dpad=priority world_analog=unchanged game_started=false\n");
 buttons=XINPUT_GAMEPAD_A;run();require(interactions==2&&(image[0xf1b94+VK_LBUTTON]&0x80),"menu confirm clicks without exploration interaction");
 *reinterpret_cast<int*>(gui+0x190)=1;
 buttons=0;run();buttons=XINPUT_GAMEPAD_X;run();require(!(image[0xf1b94+VK_LBUTTON]&0x80)&&!velocity[0]&&!velocity[1],"exploration X cannot issue cursor-directed walking");
 require(image[0xf1b94+VK_SPACE]&0x80,"X must map original Space for interaction and dialogue");
 run();require((image[0xf1b94+VK_SPACE]&0x80)&&interactions==2,"X held uses original Space path without duplicate direct interaction");
 buttons=0;run();require(!(image[0xf1b94+VK_SPACE]&0x80),"X release clears synthetic Space preserving raw low bit");
 printf("GAMEPAD_SPACE_REPLAY PASS X=Space high_bit=merged held=native direct_interaction=not_duplicated mouse_walk=false game_started=false\n");
 buttons=XINPUT_GAMEPAD_START;run();require(image[0xf1b94+VK_RBUTTON]&0x80,"menu maps native right button");
 buttons=0;run();buttons=XINPUT_GAMEPAD_BACK;run();require(modernGamepadMapButtons()==1&&image[0xf1b94+VK_F8]==0,"View button routes only to map observer, never native F8");
 buttons=0;run();buttons=XINPUT_GAMEPAD_RIGHT_THUMB;run();require(modernGamepadMapButtons()==2&&image[0xf1b94+VK_F9]==0,"R3 routes only to minimap observer");
 // Source-shaped title -> input -> real IAT bridge stack. No commercial code runs.
 memset(image+0x2f95,0x90,0x35);BYTE inputPrologue[]={0x55,0x8b,0xec,0x83,0xec,0x08};memcpy(image+0x2f95,inputPrologue,sizeof(inputPrologue));
 BYTE epilogue[]={0x8b,0xe5,0x5d,0xc3};memcpy(image+0x2fd5,epilogue,sizeof(epilogue));
 memset(image+0xb71a6,0x90,0x26);BYTE titlePrologue[]={0x55,0x8b,0xec,0x83,0xec,0x38,0x89,0x4d,0xc8};memcpy(image+0xb71a6,titlePrologue,sizeof(titlePrologue));
 image[0xb71cc]=0xe8;*reinterpret_cast<int32_t*>(image+0xb71cd)=0x2f95-0xb71d1;memcpy(image+0xb71d1,epilogue,sizeof(epilogue));
 BYTE title[0x74]{};*reinterpret_cast<DWORD*>(title)=reinterpret_cast<DWORD>(image+0xc22f0);
 auto titleRun=[&](int phase,WORD pressed){*reinterpret_cast<int*>(title+0x70)=phase;buttons=pressed;reinterpret_cast<void(__thiscall*)(void*)>(image+0xb71a6)(title);};
 titleRun(1,0);titleRun(1,XINPUT_GAMEPAD_A);
 require((image[0xf1b94+VK_ESCAPE]&0x80)&&!(image[0xf1b94+VK_SPACE]&0x80),"logo skip uses source Esc not Space through IAT bridge");
 titleRun(3,0);titleRun(3,XINPUT_GAMEPAD_A);require(image[0xf1b94+VK_ESCAPE]&0x80,"opening skip uses source Esc");
 titleRun(4,0);titleRun(4,XINPUT_GAMEPAD_A);require(image[0xf1b94+VK_LBUTTON]&0x80,"visible title confirm remains native mouse click");
 titleRun(5,0);titleRun(5,XINPUT_GAMEPAD_A);require(!(image[0xf1b94+VK_LBUTTON]&0x80)&&!(image[0xf1b94+VK_ESCAPE]&0x80),"title transition does not receive confirm clicks or skip");
 *reinterpret_cast<int*>(image+0xf1b48)=800;*reinterpret_cast<int*>(image+0xf1b4c)=600;
 auto mouseX=reinterpret_cast<int*>(image+0xf20b0),mouseY=reinterpret_cast<int*>(image+0xf20a8);*mouseX=physicalX=400;*mouseY=physicalY=300;
 if(!menuDispatchOnly){
 titleRun(4,0);titleRun(4,0);titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);
 require(modernGamepadNavigation().active,"integrated menu direction acquires navigation");
 modernGamepadFocusCursor(400,420);require(*mouseY==420,"integrated directional focus writes virtual cursor");
 titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);require(modernGamepadNavigation().active&&*mouseX==400&&*mouseY==420,"native physical mouse polling must not erase controller menu focus");
 titleRun(4,0);titleRun(4,XINPUT_GAMEPAD_A);
 require(*mouseX==400&&*mouseY==420&&(image[0xf1b94+VK_LBUTTON]&0x80),"A press retains selected menu hit position after real OS cursor poll");
 titleRun(4,0);require(*mouseX==400&&*mouseY==420&&!(image[0xf1b94+VK_LBUTTON]&0x80),"A release retains selected native click position");
 titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);
 *mouseX=physicalX=123;*mouseY=physicalY=234;titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);
 require(!modernGamepadNavigation().active&&*mouseX==123&&*mouseY==234,"actual changed mouse coordinates retain physical priority");
 titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);require(!modernGamepadNavigation().active,"held direction cannot steal navigation after real mouse movement");
 titleRun(4,0);titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);require(modernGamepadNavigation().active,"neutral direction rearms navigation after real mouse movement");
 rightX=32767;Sleep(20);titleRun(4,0);int firstCursorX=*mouseX;require(firstCursorX>123,"right stick moves virtual cursor through actual input hook");
 Sleep(20);titleRun(4,0);require(*mouseX>firstCursorX,"right stick own previous write cannot block sustained cursor movement");rightX=0;
 }
 BYTE menuRoot[0x1b0]{},titleScene[0x74]{},menuWidgets[4][0x1a8]{},menuNodes[4][8]{};int menuRects[4][4]={{300,400,500,440},{300,450,500,490},{300,500,500,540},{300,550,500,590}};
 *reinterpret_cast<BYTE**>(menuRoot+0x1a8)=titleScene;*reinterpret_cast<int*>(titleScene+0x70)=4;
 auto menuVt=image+0xbee80;auto titleVt=image+0xc2340;constexpr unsigned arrowMethods[]={0x55f0a,0x55f23,0x55f3c,0x55f55};
 for(unsigned n=0;n<4;++n)*reinterpret_cast<DWORD*>(menuVt+0xc8+n*4)=reinterpret_cast<DWORD>(image+arrowMethods[n]);
 *reinterpret_cast<DWORD*>(menuVt+0x188)=reinterpret_cast<DWORD>(&menuPressed);*reinterpret_cast<DWORD*>(menuVt+0x18c)=reinterpret_cast<DWORD>(&menuHeld);*reinterpret_cast<DWORD*>(menuVt+0x190)=reinterpret_cast<DWORD>(&menuIdleEvent);*reinterpret_cast<DWORD*>(menuVt+0x194)=reinterpret_cast<DWORD>(&menuReleased);
 *reinterpret_cast<DWORD*>(menuVt+0x1a4)=reinterpret_cast<DWORD>(&rightReleased);
 auto menuWidget=[&](BYTE* widget){*reinterpret_cast<BYTE**>(widget)=menuVt;*reinterpret_cast<int*>(widget+0x160)=*reinterpret_cast<int*>(widget+0xe8)=1;*reinterpret_cast<BYTE**>(widget+0x17c)=menuRoot;};
 menuWidget(menuRoot);*reinterpret_cast<BYTE**>(menuRoot)=titleVt;*reinterpret_cast<DWORD*>(titleVt+0x24)=reinterpret_cast<DWORD>(&titleListener);*reinterpret_cast<BYTE**>(menuRoot+0x18)=menuWidgets[0];
 for(int n=0;n<4;++n){menuWidget(menuWidgets[n]);*reinterpret_cast<int*>(menuWidgets[n]+4)=0x16c+n;*reinterpret_cast<int**>(menuNodes[n])=menuRects[n];*reinterpret_cast<BYTE**>(menuWidgets[n]+0x100)=menuNodes[n];if(n<3)*reinterpret_cast<BYTE**>(menuWidgets[n]+0x10)=menuWidgets[n+1];}
 image[0x2fd5]=0xc3; // Return to plain owned input call after the title-stack replay.
 *reinterpret_cast<int*>(gui+0x190)=4;physicalX=400;physicalY=300;buttons=0;axisX=axisY=rightX=0;run();run();replayMenu=menuRoot;
 buttons=XINPUT_GAMEPAD_DPAD_DOWN;run();require(*mouseX==400&&*mouseY==420,"production navigation selects first native mouse hit rectangle");
 buttons=0;run();buttons=XINPUT_GAMEPAD_A;run();
 require(menuPresses==1&&lastPressed==0x16c&&titleRequests==0,"A must reach selected native button first-press callback after physical poll");
 run();require(menuPresses==1&&menuReleases==0&&menuHolds==2&&titleRequests==0,"held A uses native held callback without duplicating first-press or release");
 buttons=0;run();require(menuReleases==1&&lastReleased==0x16c,"A release reaches the same selected native button callback");
 int released=menuReleases,idle=menuIdle;run();require(menuReleases==released&&menuIdle==idle+1&&titleRequests==1,"native idle state zero differs from release state minus one");
 buttons=XINPUT_GAMEPAD_DPAD_DOWN;run();buttons=0;run();buttons=XINPUT_GAMEPAD_A;run();buttons=0;run();
 require(menuPresses==2&&menuReleases==2&&lastPressed==0x16d&&lastReleased==0x16d,"navigate then A dispatches second menu item rather than stale first focus");
 *reinterpret_cast<int*>(menuWidgets[1]+0x160)=0;buttons=XINPUT_GAMEPAD_A;run();buttons=0;run();require(menuPresses==2&&menuReleases==2,"disabled selected button does not receive controller callbacks");
 *reinterpret_cast<int*>(menuWidgets[1]+0x160)=1;physicalX=400;physicalY=520;buttons=0;run();buttons=XINPUT_GAMEPAD_A;run();buttons=0;run();
 require(menuPresses==3&&menuReleases==3&&lastPressed==0x16e&&lastReleased==0x16e,"real mouse handoff plus A dispatch uses the actual new hit rectangle");
 require(titleRequests==3&&titleCommands[0]==6&&titleCommands[1]==7&&titleCommands[2]==9,"A release must reach source-shaped title listener commands not only a generic button callback");
 printf("MENU_DISPATCH_REPLAY PASS press=%d release=%d held=%d idle_distinct=true physical_poll=true disabled_guard=true callbacks=source_shaped commercial_code_executed=false\n",menuPresses,menuReleases,menuHolds);
 buttons=XINPUT_GAMEPAD_DPAD_DOWN;run();buttons=0;run();buttons=XINPUT_GAMEPAD_A;run();
 require(titleRequests==3,"quit press must not request exit before native release");buttons=0;run();
 require(titleRequests==4&&titleCommands[3]==11&&lastReleased==0x16f,"fourth title item requests quit through native release listener contract");
 *reinterpret_cast<int*>(titleScene+0x70)=1;buttons=XINPUT_GAMEPAD_A;run();buttons=0;run();
 require(titleRequests==4,"title phase below4 rejects menu activation even with source release event");
 *reinterpret_cast<int*>(titleScene+0x70)=4;
 printf("TITLE_LISTENER_REPLAY PASS requests=4 commands=6,7,9,11 event=3c release_only=true phase_guard=true native_widget_ids=true listener_vtable=true transition_executor=not_run commercial_code_executed=false\n");
 buttons=0;run();buttons=XINPUT_GAMEPAD_A;run();const unsigned beforeDisconnect=titleRequests;
 connected=false;run();
 require(titleRequests==beforeDisconnect,"disconnect while A held must cancel synthetic press rather than activate release-only title action");
 require(*reinterpret_cast<int*>(menuWidgets[3]+0x19c)==0,"cancelled controller press must clear native button visual state without release action");
 connected=true;run();require(titleRequests==beforeDisconnect,"held reconnect must not confirm a menu item");
 buttons=0;run();buttons=XINPUT_GAMEPAD_A;run();buttons=0;run();
 require(titleRequests==beforeDisconnect+1,"neutral reconnect permits a fresh normal A release confirmation");
 // A physical left button remains authoritative when the controller disconnects.
 physicalX=400;physicalY=420;buttons=XINPUT_GAMEPAD_A;run();physicalMouseDown=true;run();
 const unsigned beforePhysicalRelease=titleRequests;connected=false;run();require(titleRequests==beforePhysicalRelease,"physical held mouse is not released by controller cancellation");
 physicalMouseDown=false,physicalRightDown=false;buttons=0;run();require(titleRequests==beforePhysicalRelease+1,"real physical mouse release still reaches native title listener");
 connected=true;run();buttons=0;run();
 buttons=XINPUT_GAMEPAD_A;run();const unsigned beforeSwitch=titleRequests;
 controllerSlot=1;run();require(titleRequests==beforeSwitch,"replacement controller cannot release-confirm the previous controller press");
 require(*reinterpret_cast<int*>(menuWidgets[0]+0x19c)==0,"replacement controller cancels prior native press visual");
 buttons=0;run();buttons=XINPUT_GAMEPAD_A;run();buttons=0;run();require(titleRequests==beforeSwitch+1,"replacement controller confirms only after neutral rearm and fresh press");
 controllerSlot=0;buttons=0;run();run();
 printf("GAMEPAD_DISCONNECT_REPLAY PASS synthetic_release=cancelled device_switch=cancelled visual_press=cleared physical_release=preserved neutral_rearm=true focus_path=unchanged game_started=false\n");
 // Menu B must release once deliberately, never because a controller disappeared.
 buttons=0;run();int rightBefore=rightReleases;buttons=XINPUT_GAMEPAD_B;run();
 require(rightReleases==rightBefore,"B press does not prematurely dispatch native right release");
 connected=false;buttons=0;run();require(rightReleases==rightBefore,"disconnect while B held must cancel right release instead of returning menu");
 connected=true;buttons=XINPUT_GAMEPAD_B;run();run();require(rightReleases==rightBefore,"reconnect held B must not return menu");
 buttons=0;run();buttons=XINPUT_GAMEPAD_B;run();buttons=0;run();require(rightReleases==rightBefore+1,"fresh B deliberate release retains native return event");
 buttons=XINPUT_GAMEPAD_B;run();controllerSlot=2;buttons=0;run();require(rightReleases==rightBefore+1,"controller replacement while B held cancels return event");
 run();buttons=XINPUT_GAMEPAD_B;run();physicalX=400;physicalY=570;physicalRightDown=true;run();connected=false;buttons=0;run();
 require(rightReleases==rightBefore+1,"physical right mouse remains held when controller disappears");
 physicalRightDown=false;run();require(rightReleases==rightBefore+2,"physical right mouse deliberate release is preserved");
 connected=true;controllerSlot=0;buttons=0;run();run();
 // Exploration uses the same original right-release to request field mode 5.
 *reinterpret_cast<BYTE**>(gui)=menuVt;*reinterpret_cast<int*>(gui+0x190)=1;
 *reinterpret_cast<int*>(gui+0xe8)=*reinterpret_cast<int*>(gui+0x160)=1;
 BYTE worldNode[8]{};int worldRect[]={0,0,800,600};*reinterpret_cast<int**>(worldNode)=worldRect;*reinterpret_cast<BYTE**>(gui+0x100)=worldNode;
 replayMenu=gui;buttons=XINPUT_GAMEPAD_START;run();require(worldMenuRequests==0,"Start press waits for source right-release event");
 connected=false;buttons=0;run();require(worldMenuRequests==0,"disconnect while Start held must not request field menu mode 5");
 connected=true;buttons=0;run();run();buttons=XINPUT_GAMEPAD_START;run();buttons=0;run();
 require(worldMenuRequests==1&&*reinterpret_cast<int*>(world+0x156c)==5,"deliberate Start release requests source field menu mode 5 once");run();require(worldMenuRequests==1,"idle cannot repeat field menu request");
 printf("GAMEPAD_CANCEL_RELEASE_REPLAY PASS menu_B=deliberate_release device_loss=cancelled device_switch=cancelled physical_right=preserved world_Start=mode5 release_event=40 transition_executor=not_run game_started=false\n");
 replayMenu=nullptr;*reinterpret_cast<int*>(gui+0x190)=1;
 buttons=0;require(removeModernGamepad(reinterpret_cast<HMODULE>(image)),"integrated rollback");require(*iat==oldIat&&*reinterpret_cast<DWORD*>(image+0xc12c0)==reinterpret_cast<DWORD>(image+0x6b2d8)&&*reinterpret_cast<DWORD*>(image+0xc1258)==reinterpret_cast<DWORD>(image+0x652b4),"all three original slots restored");
 image[0x6e77e]^=1;require(!installWorldGamepad(reinterpret_cast<HMODULE>(image),nullptr),"unknown movement callsite rejects");image[0x6e77e]^=1;
 image[0x6e6d8]^=1;require(!installWorldGamepad(reinterpret_cast<HMODULE>(image),nullptr),"unknown interaction handler rejects before installing hooks");image[0x6e6d8]^=1;
 // Camera-only recipe must adapt keyboard movement without polling an Xbox.
 image[0x2fd5]=0xc3;SetEnvironmentVariableW(L"MC_GAMEPAD_NATIVE",nullptr);SetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",L"1");
 require(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr)&&installWorldGamepad(reinterpret_cast<HMODULE>(image),nullptr),"camera-only keyboard installer");
 configureModernGamepadFixture(keyboard,nullptr,true);render_input::inputView.publish(displayed,reinterpret_cast<uintptr_t>(cameraData),GetTickCount(),true);
 physical=true;run();require(velocity[0]<-29.9f&&!(image[0xf1b94+VK_LEFT]&0x80)&&(image[0xf1b94+VK_UP]&0x80),"camera-only keyboard follows orbit without XInput backend");
 *reinterpret_cast<int*>(gui+0x190)=4;run();require(!modernGamepadMoveIntent().active&&(image[0xf1b94+VK_LEFT]&0x80),"camera keyboard adaptation excludes menus");*reinterpret_cast<int*>(gui+0x190)=1;
 render_input::inputView.reset();run();require((image[0xf1b94+VK_LEFT]&0x80)&&!(image[0xf1b94+VK_UP]&0x80),"camera toggle off restores original keyboard semantics");physical=false;
 require(removeWorldGamepad(reinterpret_cast<HMODULE>(image))&&removeModernGamepad(reinterpret_cast<HMODULE>(image)),"camera-only exact rollback");SetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",nullptr);
 SetEnvironmentVariableW(L"MC_MAP_OVERLAY",nullptr);SetEnvironmentVariableW(L"MC_GAMEPAD_NATIVE",nullptr);VirtualFree(image,0,MEM_RELEASE);
 printf("GAMEPAD_CURSOR_RENDER_BOUNDARY_REPLAY PASS preparation=preserved hidden_submission=suppressed mouse_restore=original menu_submission=original game_started=false\n");
 printf("WORLD_GAMEPAD_FIXTURE PASS checks=%d camera_relative=true analog_speed=true native_movement=true keyboard_priority=true rollback=exact game_started=false\n",checks);
}
