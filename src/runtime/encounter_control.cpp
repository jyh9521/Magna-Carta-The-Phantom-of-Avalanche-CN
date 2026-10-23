#include "encounter_control.h"
#include <cstring>
namespace {
constexpr unsigned rva=0x6e07d,imageSize=0x10b000;
constexpr BYTE prefix[]={0x55,0x8b,0xec,0x83,0xec,0x0c};
BYTE* engine=nullptr;BYTE* trampoline=nullptr;
using Check=int(__thiscall*)(void*);Check original=nullptr;
volatile LONG enabled=1,uiStarted=0;bool held=true;
void(*trace)(const wchar_t*)=nullptr;
HANDLE uiThread=nullptr,stopEvent=nullptr;HWND* gameWindow=nullptr;
wchar_t onLabel[128]=L"Random encounters: ON  [F5]",offLabel[128]=L"Random encounters: OFF  [F5]";
int __fastcall checkHook(void* scene,void*){return InterlockedCompareExchange(&enabled,0,0)?original(scene):0;}
void patch(BYTE* base,BYTE* out){out[0]=0xe9;*reinterpret_cast<int*>(out+1)=int(reinterpret_cast<uintptr_t>(&checkHook)-reinterpret_cast<uintptr_t>(base+rva+5));out[5]=0x90;}
bool write(BYTE* to,const BYTE* bytes){DWORD old;if(!VirtualProtect(to,6,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(to,bytes,6);bool ok=FlushInstructionCache(GetCurrentProcess(),to,6)!=FALSE;DWORD unused;return VirtualProtect(to,6,old,&unused)!=FALSE&&ok;}
bool mapped(BYTE* base,size_t size,bool active){
 if(!base||size<imageSize)return false;auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(base+dos->e_lfanew);
 if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=imageSize)return false;
 // Independent body and caller guards keep this scoped to random encounters.
 const BYTE body[]={0x83,0x7d,0xf4,0x05};
 if(memcmp(base+0x6e093,body,4)||base[0x6e22d]!=0xc3)return false;
 BYTE changed[6];patch(base,changed);bool clean=!memcmp(base+rva,prefix,6),installed=engine==base&&trampoline&&!memcmp(base+rva,changed,6);
 if(!clean&&!installed)return false;if(active&&installed)return true;if(!active&&clean)return true;
 if(active){
  trampoline=static_cast<BYTE*>(VirtualAlloc(nullptr,11,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));if(!trampoline)return false;
  memcpy(trampoline,prefix,6);trampoline[6]=0xe9;*reinterpret_cast<int*>(trampoline+7)=int(base+rva+6-trampoline-11);DWORD old;
  if(!VirtualProtect(trampoline,11,PAGE_EXECUTE_READ,&old)||!FlushInstructionCache(GetCurrentProcess(),trampoline,11)){VirtualFree(trampoline,0,MEM_RELEASE);trampoline=nullptr;return false;}
  original=reinterpret_cast<Check>(trampoline);
  if(!write(base+rva,changed)){write(base+rva,prefix);VirtualFree(trampoline,0,MEM_RELEASE);trampoline=nullptr;original=nullptr;return false;}
  engine=base;gameWindow=reinterpret_cast<HWND*>(base+0xf1b44);return true;
 }
 if(!write(base+rva,prefix)){write(base+rva,changed);return false;}
 VirtualFree(trampoline,0,MEM_RELEASE);trampoline=nullptr;original=nullptr;engine=nullptr;gameWindow=nullptr;return true;
}
void paint(HDC dc,int width,int height){
 RECT rect{0,0,width,height};HBRUSH brush=CreateSolidBrush(RGB(18,32,42));FillRect(dc,&rect,brush);DeleteObject(brush);
 SetBkMode(dc,TRANSPARENT);SetTextColor(dc,encountersEnabled()?RGB(224,241,228):RGB(255,216,143));
 HFONT font=CreateFontW(-height*5/11,0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,L"Microsoft YaHei");auto old=SelectObject(dc,font);
 DrawTextW(dc,encounterStatus(),-1,&rect,DT_CENTER|DT_VCENTER|DT_SINGLELINE|DT_NOPREFIX);SelectObject(dc,old);DeleteObject(font);
}
LRESULT CALLBACK windowProc(HWND window,UINT message,WPARAM w,LPARAM l){
 if(message==WM_NCHITTEST)return HTTRANSPARENT;
 if(message==WM_MOUSEACTIVATE)return MA_NOACTIVATE;
 if(message==WM_PAINT){PAINTSTRUCT ps{};HDC dc=BeginPaint(window,&ps);RECT rect{};GetClientRect(window,&rect);paint(dc,rect.right,rect.bottom);EndPaint(window,&ps);return 0;}
 if(message==WM_TIMER){
  if(WaitForSingleObject(stopEvent,0)==WAIT_OBJECT_0){DestroyWindow(window);return 0;}
  HWND game=gameWindow?*gameWindow:nullptr;DWORD pid=0;if(game)GetWindowThreadProcessId(game,&pid);
  if(!game||!IsWindow(game)||IsIconic(game)||GetForegroundWindow()!=game||pid!=GetCurrentProcessId()){ShowWindow(window,SW_HIDE);return 0;}
  RECT rect{};POINT origin{};GetClientRect(game,&rect);ClientToScreen(game,&origin);
  int height=rect.bottom/22;if(height<24)height=24;if(height>72)height=72;
  int width=height*8;if(width>rect.right)width=rect.right;
  SetWindowPos(window,HWND_TOPMOST,origin.x+(rect.right-width)/2,origin.y+height/2,width,height,SWP_NOACTIVATE|SWP_SHOWWINDOW);
  InvalidateRect(window,nullptr,FALSE);return 0;
 }
 if(message==WM_DESTROY){PostQuitMessage(0);return 0;}return DefWindowProcW(window,message,w,l);
}
DWORD WINAPI threadMain(void*){
 HINSTANCE instance=GetModuleHandleW(nullptr);WNDCLASSW cls{};cls.lpfnWndProc=windowProc;cls.hInstance=instance;cls.lpszClassName=L"MagnaCartaEncounterStatus";
 if(!RegisterClassW(&cls)){if(trace)trace(L"ENCOUNTER_HUD_FAILED register_class=true");return 1;}
 HWND window=CreateWindowExW(WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,cls.lpszClassName,L"",WS_POPUP,0,0,320,40,nullptr,nullptr,instance,nullptr);
 if(window){SetLayeredWindowAttributes(window,0,232,LWA_ALPHA);SetTimer(window,1,50,nullptr);MSG message{};while(GetMessageW(&message,nullptr,0,0)>0){TranslateMessage(&message);DispatchMessageW(&message);}}
 if(trace)trace(window?L"ENCOUNTER_HUD_CLOSED":L"ENCOUNTER_HUD_FAILED create_window=true");UnregisterClassW(cls.lpszClassName,instance);return window?0:1;
}
void startUi(){
#ifndef ENCOUNTER_CONTROL_TEST
 if(InterlockedCompareExchange(&uiStarted,1,0))return;
 stopEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);if(stopEvent)uiThread=CreateThread(nullptr,0,threadMain,nullptr,0,nullptr);
 if(!uiThread){if(stopEvent)CloseHandle(stopEvent);stopEvent=nullptr;if(trace)trace(L"ENCOUNTER_HUD_FAILED thread_creation=true");}
#endif
}
}
bool encountersEnabled(){return InterlockedCompareExchange(&enabled,0,0)!=0;}
const wchar_t* encounterStatus(){return encountersEnabled()?onLabel:offLabel;}
void encounterKeyboard(PBYTE keys,bool focused){
 bool down=keys&&(keys[VK_F5]&0x80);if(!focused||!keys){held=true;return;}
 startUi();if(down&&!held){bool on=!encountersEnabled();InterlockedExchange(&enabled,on?1:0);if(trace)trace(on?L"ENCOUNTER_STATE enabled=true key=F5":L"ENCOUNTER_STATE enabled=false key=F5");}
 held=down;keys[VK_F5]=0;
}
bool installEncounterControl(HMODULE module,void(*logger)(const wchar_t*)){
 if(!mapped(reinterpret_cast<BYTE*>(module),imageSize,true))return false;trace=logger;
 wchar_t label[128]{};DWORD n=GetEnvironmentVariableW(L"MC_ENCOUNTER_ON",label,128);if(n&&n<128)wcscpy_s(onLabel,label);
 n=GetEnvironmentVariableW(L"MC_ENCOUNTER_OFF",label,128);if(n&&n<128)wcscpy_s(offLabel,label);
 if(trace)trace(L"ENCOUNTER_CONTROL_READY initial=on key=F5 scope=random_only counters=preserved scripts=unchanged");return true;
}
bool removeEncounterControl(){
 if(!engine)return true;if(!mapped(engine,imageSize,false))return false;
 if(stopEvent){SetEvent(stopEvent);WaitForSingleObject(uiThread,3000);CloseHandle(uiThread);CloseHandle(stopEvent);uiThread=stopEvent=nullptr;}return true;
}
#ifdef ENCOUNTER_CONTROL_TEST
bool encounterTestMapped(BYTE* p,size_t size,bool on){return mapped(p,size,on);}
void encounterTestReset(){enabled=1;held=true;}
void encounterTestPaint(HDC dc,int w,int h){paint(dc,w,h);}
#endif
