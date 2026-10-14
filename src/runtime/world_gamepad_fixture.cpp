#include "modern_gamepad.h"
#include "world_gamepad.h"
#include "gamepad_ui.h"
#include "camera_input_view.h"
#include <Xinput.h>
#include <cstdio>
#include <cstring>
#include <cmath>
static BYTE* image=nullptr;static BYTE world[0x15c4],actor[0x340],gui[0x194],cameraData[0xc0];
static bool connected=true,physical=false,rawUp=false;static SHORT axisX=0,axisY=0,rightX=0;static WORD buttons=0;static int checks=0,forwardCalls=0,turnCalls=0,interactions=0;static int observations=0;static bool observationControlled=false;
void require(bool,const char*);
int __fastcall interaction(void* s,void*,void* g,unsigned event){require(s==world&&g==gui&&event==0x11,"interaction uses native scene and GUI event");++interactions;if(*reinterpret_cast<int*>(world+0x15b8))*reinterpret_cast<int*>(world+0x15bc)=1;return 0;}
void observe(BYTE* s,bool controlled){if(s==world){++observations;observationControlled=controlled;}}
void require(bool v,const char* s){++checks;if(!v){fprintf(stderr,"FAIL %s\n",s);ExitProcess(1);}}
BOOL WINAPI keyboard(PBYTE keys){memset(keys,0,256);keys[VK_SPACE]=1;if(rawUp)keys[VK_UP]=0x80;if(physical)keys[VK_LEFT]=0x80;return TRUE;}
DWORD WINAPI poll(DWORD slot,XINPUT_STATE* s){if(slot||!connected)return ERROR_DEVICE_NOT_CONNECTED;*s={};s->Gamepad.sThumbLX=axisX;s->Gamepad.sThumbLY=axisY;s->Gamepad.sThumbRX=rightX;s->Gamepad.wButtons=buttons;return ERROR_SUCCESS;}
void __fastcall heading(void* p,void*,float x,float y,float z){++turnCalls;auto d=reinterpret_cast<float*>(static_cast<BYTE*>(p)+0x148);d[0]=x;d[1]=y;d[2]=z;}
void __fastcall forward(void* p,void*){++forwardCalls;auto d=reinterpret_cast<float*>(static_cast<BYTE*>(p)+0x148),v=reinterpret_cast<float*>(static_cast<BYTE*>(p)+0x16c);for(int i=0;i<3;++i)v[i]=30*d[i];}
void __fastcall tick(void*,void*){
 reinterpret_cast<BOOL(__cdecl*)()>(image+0x2fca)();auto keys=image+0xf1b94;if(rawUp)keyboard(keys); // owned raw-key buffer; no OS input injection
 if(keys[VK_UP]&0x80)reinterpret_cast<void(__thiscall*)(void*)>(image+0x6e760)(actor);
 else memset(actor+0x16c,0,12);
}
void stub(unsigned rva,const BYTE* prefix,unsigned n,void* fn){
 memcpy(image+rva,prefix,n);BYTE* p=image+rva+n;*p++=0x8b;*p++=0xe5;*p++=0x5d;*p++=0xe9;*reinterpret_cast<int32_t*>(p)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(fn)-reinterpret_cast<ULONG_PTR>(p+4));
}
int main(){
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image!=nullptr,"owned image");
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 image[0x2fca]=0x68;*reinterpret_cast<DWORD*>(image+0x2fcb)=reinterpret_cast<DWORD>(image+0xf1b94);image[0x2fcf]=0xff;image[0x2fd0]=0x15;*reinterpret_cast<DWORD*>(image+0x2fd1)=reinterpret_cast<DWORD>(image+0xbd3dc);image[0x2fd5]=0xc3;
 initializeGamepadUiFixture(image);
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
 SetEnvironmentVariableW(L"MC_MAP_OVERLAY",L"1");SetEnvironmentVariableW(L"MC_GAMEPAD_NATIVE",L"1");require(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr),"integrated installer");require(installModernGamepad(reinterpret_cast<HMODULE>(image),nullptr),"idempotence");configureModernGamepadFixture(keyboard,poll,true);
 auto run=[](){reinterpret_cast<void(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(image+0xc12c0))(world);};
 setWorldTickObserver(&observe);run();require(observations==1&&observationControlled,"read-only observer runs after native tick");setWorldTickObserver(nullptr);run();require(observations==1,"observer removal preserves native tick");axisX=32767;run();auto velocity=reinterpret_cast<float*>(actor+0x16c);
 require(velocity[0]>29.9f&&std::abs(velocity[1])<.001f&&turnCalls==1,"right stick direction becomes forward movement not tank turn");
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
 buttons=0;run();*reinterpret_cast<int*>(gui+0x190)=4;buttons=XINPUT_GAMEPAD_A;run();require(interactions==2&&(image[0xf1b94+VK_LBUTTON]&0x80),"menu confirm clicks without exploration interaction");
 *reinterpret_cast<int*>(gui+0x190)=1;
 buttons=0;run();buttons=XINPUT_GAMEPAD_X;run();require(!(image[0xf1b94+VK_LBUTTON]&0x80)&&!velocity[0]&&!velocity[1],"exploration X cannot issue cursor-directed walking");
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
 auto mouseX=reinterpret_cast<int*>(image+0xf20b0),mouseY=reinterpret_cast<int*>(image+0xf20a8);*mouseX=400;*mouseY=300;
 titleRun(4,0);titleRun(4,0);titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);
 require(modernGamepadNavigation().active,"integrated menu direction acquires navigation");
 modernGamepadFocusCursor(400,420);require(*mouseY==420,"integrated directional focus writes virtual cursor");
 titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);require(modernGamepadNavigation().active,"controller focus write must not masquerade as physical mouse movement");
 *mouseX=123;*mouseY=234;titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);
 require(!modernGamepadNavigation().active&&*mouseX==123&&*mouseY==234,"actual changed mouse coordinates retain physical priority");
 titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);require(!modernGamepadNavigation().active,"held direction cannot steal navigation after real mouse movement");
 titleRun(4,0);titleRun(4,XINPUT_GAMEPAD_DPAD_DOWN);require(modernGamepadNavigation().active,"neutral direction rearms navigation after real mouse movement");
 rightX=32767;Sleep(20);titleRun(4,0);int firstCursorX=*mouseX;require(firstCursorX>123,"right stick moves virtual cursor through actual input hook");
 Sleep(20);titleRun(4,0);require(*mouseX>firstCursorX,"right stick own previous write cannot block sustained cursor movement");rightX=0;
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
 printf("WORLD_GAMEPAD_FIXTURE PASS checks=%d camera_relative=true analog_speed=true native_movement=true keyboard_priority=true rollback=exact game_started=false\n",checks);
}
