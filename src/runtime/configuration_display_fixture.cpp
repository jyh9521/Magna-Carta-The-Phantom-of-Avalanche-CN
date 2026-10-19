#include "advanced_display.h"
#include "configuration_display_presets.h"
#include "window_mode.h"
#include <iostream>
#include <stdexcept>
#include <cstring>
static HWND ownedWindow=nullptr;
static POINT ownedCursor{};
static HWND WINAPI ownedCreate(DWORD,LPCSTR,LPCSTR,DWORD,int,int,int,int,HWND,HMENU,HINSTANCE,LPVOID){return ownedWindow;}
static BOOL WINAPI ownedGetCursor(LPPOINT point){*point=ownedCursor;return TRUE;}
static BOOL WINAPI ownedSetCursor(int x,int y){ownedCursor={x,y};return TRUE;}
static unsigned checks=0;
void check(bool b){++checks;if(!b)throw std::runtime_error("configuration display fixture failed");}
int main(){try{
 for(const auto& p:configurationDisplayPresets){
  check(advancedConfigMatches(p.name,p.hash));check(!advancedConfigMatches(p.name,"unknown"));
  check(advancedProfileWide(p.name));check(advancedProfileRender60(p.name)==p.render60);
 }
 check(!advancedConfigMatches(L"md3-8k-borderless-30",configurationDisplayPresets[0].hash));
 check(!advancedProfileWide(L"unknown"));check(!advancedProfileRender60(L"unknown"));
 auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(image);
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 BYTE instruction[]={0xc7,0x05,0,0,0,0,1,0,0,0,0xc3};
 *reinterpret_cast<DWORD*>(instruction+2)=reinterpret_cast<DWORD>(image+0xf1b40);memcpy(image+0x9a0e,instruction,sizeof(instruction));
 using Store=void(__cdecl*)();auto call=reinterpret_cast<Store>(image+0x9a0e);
 call();check(*reinterpret_cast<DWORD*>(image+0xf1b40)==1);
 check(setNativeWindowed(image,0x10b000,true));call();check(*reinterpret_cast<DWORD*>(image+0xf1b40)==0);
 check(setNativeWindowed(image,0x10b000,true));
 check(setNativeWindowed(image,0x10b000,false));call();check(*reinterpret_cast<DWORD*>(image+0xf1b40)==1);
 check(!memcmp(image+0x9a0e,instruction,sizeof(instruction)));
 for(unsigned i=0;i<10;++i){if(i==6)continue;image[0x9a0e+i]^=1;check(!setNativeWindowed(image,0x10b000,true));image[0x9a0e+i]^=1;}
 check(!setNativeWindowed(image,52,true));image[0x9a14]=2;check(!setNativeWindowed(image,0x10b000,true));image[0x9a14]=1;
 nt->OptionalHeader.SizeOfImage=0x1000;check(!setNativeWindowed(image,0x10b000,true));
 VirtualFree(image,0,MEM_RELEASE);
 int w=0,h=0;check(!parseWindowResolution(L"1x1",w,h));check(!parseWindowResolution(L"1280x720junk",w,h));
 HWND window=CreateWindowExW(0,L"STATIC",L"hidden size fixture",WS_OVERLAPPEDWINDOW,0,0,800,600,nullptr,nullptr,nullptr,nullptr);check(window!=nullptr);
 check(!IsWindowVisible(window));
 for(const auto* size:{L"960x540",L"1280x720",L"1600x900",L"1920x1080",L"2560x1440"}){
  check(parseWindowResolution(size,w,h));check(resizeWindowClient(window,w,h));
  RECT client{},outer{};check(GetClientRect(window,&client)!=FALSE);check(GetWindowRect(window,&outer)!=FALSE);
  MONITORINFO monitor{sizeof(monitor)};check(GetMonitorInfoW(MonitorFromWindow(window,MONITOR_DEFAULTTONEAREST),&monitor)!=FALSE);
  check(client.right*9==client.bottom*16);check(client.right<=w&&client.bottom<=h);check(client.right>=640&&client.bottom>=360);
  check(outer.left>=monitor.rcWork.left&&outer.top>=monitor.rcWork.top&&outer.right<=monitor.rcWork.right&&outer.bottom<=monitor.rcWork.bottom);
  configureWindowSizeFixture(window,800,600,0x1234);
  RECT dest{0,0,800,600};check(offsetWindowSizeFixture(&dest,100,-50,0x1234)!=FALSE);check(dest.left==100&&dest.top==-50&&dest.right==100+client.right&&dest.bottom==-50+client.bottom);
  RECT unrelated{0,0,800,600};check(offsetWindowSizeFixture(&unrelated,100,-50,0x4321)!=FALSE);check(unrelated.right==900&&unrelated.bottom==550);
  for(POINT origin:{POINT{0,0},POINT{-1920,100},POINT{400,-50}})for(int x:{0,400,800})for(int y:{0,300,600}){
   POINT logical{origin.x+x,origin.y+y};POINT actual=mapWindowSizeFixture(logical,origin,800,600,client.right,client.bottom);
   POINT restored=mapWindowSizeFixture(actual,origin,client.right,client.bottom,800,600);check(abs(restored.x-logical.x)<=1&&abs(restored.y-logical.y)<=1);
  }
 }
 check(!IsWindowVisible(window));DestroyWindow(window);configureWindowSizeFixture(nullptr,0,0,0);
 // Production installers reject wrong slots/call sites without partially changing imports.
 auto e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));check(e!=nullptr);
 auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(e);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(e+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=0x10b000;
 auto user=GetModuleHandleW(L"user32.dll");DWORD offsets[]={0xbd418,0xbd3e8,0xbd3e4};const char* names[]={"CreateWindowExA","GetCursorPos","SetCursorPos"};DWORD originals[3]{};
 for(int i=0;i<3;++i){originals[i]=reinterpret_cast<DWORD>(GetProcAddress(user,names[i]));*reinterpret_cast<DWORD*>(e+offsets[i])=originals[i];}
 e[0xc1e3]=0xff;e[0xc1e4]=0x15;*reinterpret_cast<DWORD*>(e+0xc1e5)=reinterpret_cast<DWORD>(e+0xbd418);
 *reinterpret_cast<DWORD*>(e+0xbd3e8)=0;check(!installWindowSizing(e,0x10b000,1280,720,nullptr));check(*reinterpret_cast<DWORD*>(e+0xbd418)==originals[0]);*reinterpret_cast<DWORD*>(e+0xbd3e8)=originals[1];
 e[0xc1e3]^=1;check(!installWindowSizing(e,0x10b000,1280,720,nullptr));e[0xc1e3]^=1;
 check(installWindowSizing(e,0x10b000,1280,720,nullptr));check(installWindowSizing(e,0x10b000,1280,720,nullptr));
 for(int i=0;i<3;++i)check(*reinterpret_cast<DWORD*>(e+offsets[i])!=originals[i]);
 // Execute the actual installed IAT wrappers with owned APIs: no visible window/cursor movement.
 ownedWindow=CreateWindowExW(0,L"STATIC",L"hidden installed hook fixture",WS_OVERLAPPEDWINDOW,0,0,800,600,nullptr,nullptr,nullptr,nullptr);check(ownedWindow!=nullptr);
 RECT initial{0,0,800,600};check(AdjustWindowRectEx(&initial,WS_OVERLAPPEDWINDOW,FALSE,0)!=FALSE);
 check(SetWindowPos(ownedWindow,nullptr,0,0,initial.right-initial.left,initial.bottom-initial.top,SWP_NOZORDER|SWP_NOACTIVATE)!=FALSE);
 configureWindowApisFixture(&ownedCreate,&ownedGetCursor,&ownedSetCursor);
 auto create=reinterpret_cast<decltype(&CreateWindowExA)>(*reinterpret_cast<DWORD*>(e+offsets[0]));
 check(create(0,"STATIC","owned",0x12ca0000,0,0,0,0,nullptr,nullptr,nullptr,nullptr)==ownedWindow);
 RECT actualClient{};check(GetClientRect(ownedWindow,&actualClient)!=FALSE);check(actualClient.right*9==actualClient.bottom*16);check(actualClient.right>=960);
 POINT origin{0,0};check(ClientToScreen(ownedWindow,&origin)!=FALSE);
 auto get=reinterpret_cast<decltype(&GetCursorPos)>(*reinterpret_cast<DWORD*>(e+offsets[1]));
 auto set=reinterpret_cast<decltype(&SetCursorPos)>(*reinterpret_cast<DWORD*>(e+offsets[2]));
 for(int x:{0,400,800})for(int y:{0,300,600}){
  check(set(origin.x+x,origin.y+y)!=FALSE);
  check(abs(ownedCursor.x-(origin.x+MulDiv(x,actualClient.right,800)))<=1);
  check(abs(ownedCursor.y-(origin.y+MulDiv(y,actualClient.bottom,600)))<=1);
  POINT polled{};check(get(&polled)!=FALSE);check(abs(polled.x-origin.x-x)<=1&&abs(polled.y-origin.y-y)<=1);
 }
 check(!IsWindowVisible(ownedWindow));DestroyWindow(ownedWindow);ownedWindow=nullptr;configureWindowSizeFixture(nullptr,0,0,0);
 VirtualFree(e,0,MEM_RELEASE);
 auto driver=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2c000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));check(driver!=nullptr);
 auto dd=reinterpret_cast<IMAGE_DOS_HEADER*>(driver);dd->e_magic=IMAGE_DOS_SIGNATURE;dd->e_lfanew=0x100;
 auto dn=reinterpret_cast<IMAGE_NT_HEADERS32*>(driver+0x100);dn->Signature=IMAGE_NT_SIGNATURE;dn->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;dn->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;dn->OptionalHeader.SizeOfImage=0x2c000;
 driver[0x31f7]=0xff;driver[0x31f8]=0x15;*reinterpret_cast<DWORD*>(driver+0x31f9)=reinterpret_cast<DWORD>(driver+0x1a55c);
 auto offset=reinterpret_cast<DWORD*>(driver+0x1a55c);*offset=reinterpret_cast<DWORD>(&OffsetRect);
 driver[0x31f7]^=1;check(!installWindowPresentation(driver,0x2c000));check(*offset==reinterpret_cast<DWORD>(&OffsetRect));driver[0x31f7]^=1;
 check(installWindowPresentation(driver,0x2c000));check(installWindowPresentation(driver,0x2c000));check(*offset!=reinterpret_cast<DWORD>(&OffsetRect));
 VirtualFree(driver,0,MEM_RELEASE);

 std::cout<<"WINDOW_SIZE_FIXTURE PASS sizes=5 client=16:9 work_area=fit destination=scaled mouse=roundtrip unrelated=unchanged visible=false"<<std::endl;

 std::cout<<"CONFIGURATION_DISPLAY_FIXTURE PASS checks="<<checks<<" profiles=24 native_window_store=0 rollback=1 mismatch=rejected game_started=false"<<std::endl;return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}}
