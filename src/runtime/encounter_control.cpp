#include "encounter_control.h"
#include <cstring>
#include <cwchar>
#include "panel_canvas.h"
namespace {
constexpr unsigned rva=0x6e07d,imageSize=0x10b000;
constexpr BYTE prefix[]={0x55,0x8b,0xec,0x83,0xec,0x0c};
BYTE* engine=nullptr;BYTE* trampoline=nullptr;
using Check=int(__thiscall*)(void*);Check original=nullptr;
volatile LONG enabled=1,uiStarted=0,toastSerial=0;bool held=true;
alignas(8) volatile LONG64 toastAt=0;
bool hudShown=false;LONG renderedSerial=0,observedSerial=0,failureSerial=0;RECT renderedRect{};
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
// All glyphs are drawn into an off-screen DIB. Never issue text drawing to a
// window DC: legacy DirectDraw wrappers can redirect those calls to the game.
void hudFailure(const wchar_t*,DWORD,LONG);
bool present(HWND window,const RECT& area,LONG serial){
 int height=(area.bottom-area.top)/36;if(height<24)height=24;if(height>32)height=32;
 int width=height*10;if(width>area.right-area.left-16)width=area.right-area.left-16;
 if(width<=0)return false;
 BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=width;
 info.bmiHeader.biHeight=-height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
 void* pixels=nullptr;HBITMAP bitmap=CreateDIBSection(nullptr,&info,DIB_RGB_COLORS,&pixels,nullptr,0);
 HDC memory=CreateCompatibleDC(nullptr);if(!bitmap||!memory){if(bitmap)DeleteObject(bitmap);if(memory)DeleteDC(memory);return false;}
 auto previous=SelectObject(memory,bitmap);paint(memory,width,height);
 POINT position{area.right-width-16,area.bottom-height-24},source{};SIZE size{width,height};
 BLENDFUNCTION blend{AC_SRC_OVER,0,232,0};
 bool ok=UpdateLayeredWindow(window,nullptr,&position,&size,memory,&source,0,&blend,ULW_ALPHA)!=FALSE;
 DWORD error=ok?0:GetLastError();
 SelectObject(memory,previous);DeleteDC(memory);DeleteObject(bitmap);
 if(ok){renderedSerial=serial;renderedRect=area;}else hudFailure(L"bitmap_submit",error,serial);return ok;
}
void hudFailure(const wchar_t* stage,DWORD error,LONG serial){
 if(trace&&failureSerial!=serial){failureSerial=serial;wchar_t line[192];swprintf_s(line,L"ENCOUNTER_HUD_FAILED phase=%s error=%lu serial=%ld",stage,error,serial);trace(line);}
}
void hideHud(HWND window){if(hudShown){ShowWindow(window,SW_HIDE);hudShown=false;}}
LRESULT CALLBACK windowProc(HWND window,UINT message,WPARAM w,LPARAM l){
 if(message==WM_NCHITTEST)return HTTRANSPARENT;
 if(message==WM_MOUSEACTIVATE)return MA_NOACTIVATE;
 if(message==WM_ERASEBKGND)return 1;
 if(message==WM_PAINT){PAINTSTRUCT ps{};BeginPaint(window,&ps);EndPaint(window,&ps);return 0;}
 if(message==WM_TIMER){
  if(WaitForSingleObject(stopEvent,0)==WAIT_OBJECT_0){DestroyWindow(window);return 0;}
  LONG serial=InterlockedCompareExchange(&toastSerial,0,0);
  ULONGLONG at=static_cast<ULONGLONG>(InterlockedCompareExchange64(&toastAt,0,0));
  HWND game=gameWindow?*gameWindow:nullptr;DWORD pid=0;if(game)GetWindowThreadProcessId(game,&pid);
  if(serial&&trace&&observedSerial!=serial){observedSerial=serial;wchar_t line[256];swprintf_s(line,L"ENCOUNTER_HUD_REQUEST serial=%ld age_ms=%llu game=%p foreground=%p same_process=%d iconic=%d",serial,GetTickCount64()-at,game,GetForegroundWindow(),pid==GetCurrentProcessId(),game?IsIconic(game):0);trace(line);}
  if(!serial||GetTickCount64()-at>=1800||!game||!IsWindow(game)||IsIconic(game)||GetForegroundWindow()!=game||pid!=GetCurrentProcessId()){hideHud(window);return 0;}
  RECT rect{};POINT origin{};if(!GetClientRect(game,&rect)||!ClientToScreen(game,&origin)||rect.right<=16||rect.bottom<=64){hideHud(window);return 0;}
  rect={origin.x,origin.y,origin.x+rect.right,origin.y+rect.bottom};
  if(serial!=renderedSerial||memcmp(&rect,&renderedRect,sizeof(rect))){if(!present(window,rect,serial)){hideHud(window);return 0;}}
  if(!hudShown){
   if(!SetWindowPos(window,HWND_TOPMOST,0,0,0,0,SWP_NOACTIVATE|SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW)){hudFailure(L"show",GetLastError(),serial);return 0;}
   hudShown=true;
   // DDrawCompat 0.7.1 only registers visible windows for compositing.
   // The hidden upload primes Windows safely; this second upload supplies the
   // now-registered compositor without a window-DC draw or idle redraw loop.
   if(!present(window,rect,serial)){hideHud(window);return 0;}
   if(trace){wchar_t line[192];swprintf_s(line,L"ENCOUNTER_HUD_PRESENT serial=%ld client=%ldx%ld path=visible_bitmap duration_ms=1800",serial,rect.right-rect.left,rect.bottom-rect.top);trace(line);}
  }
  return 0;
 }
 if(message==WM_DESTROY){PostQuitMessage(0);return 0;}return DefWindowProcW(window,message,w,l);
}
DWORD WINAPI threadMain(void*){
 HINSTANCE instance=GetModuleHandleW(nullptr);WNDCLASSW cls{};cls.lpfnWndProc=windowProc;cls.hInstance=instance;cls.lpszClassName=L"MagnaCartaEncounterStatus";
 if(!RegisterClassW(&cls)){if(trace)trace(L"ENCOUNTER_HUD_FAILED register_class=true");return 1;}
 HWND window=CreateWindowExW(WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,cls.lpszClassName,L"",WS_POPUP,0,0,320,40,nullptr,nullptr,instance,nullptr);
 if(window){
  if(trace)trace(L"ENCOUNTER_HUD_WINDOW_READY path=hidden_then_visible_bitmap");
  if(!SetTimer(window,1,50,nullptr)){if(trace)trace(L"ENCOUNTER_HUD_FAILED phase=timer");DestroyWindow(window);UnregisterClassW(cls.lpszClassName,instance);return 1;}
  MSG message{};while(GetMessageW(&message,nullptr,0,0)>0){TranslateMessage(&message);DispatchMessageW(&message);}}
 if(trace)trace(window?L"ENCOUNTER_HUD_CLOSED":L"ENCOUNTER_HUD_FAILED create_window=true");UnregisterClassW(cls.lpszClassName,instance);return window?0:1;
}
void startUi(){
#ifndef ENCOUNTER_CONTROL_TEST
 if(frameOverlayAvailable())return;
 if(InterlockedCompareExchange(&uiStarted,1,0))return;
 stopEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);if(stopEvent)uiThread=CreateThread(nullptr,0,threadMain,nullptr,0,nullptr);
 if(!uiThread){if(stopEvent)CloseHandle(stopEvent);stopEvent=nullptr;if(trace)trace(L"ENCOUNTER_HUD_FAILED thread_creation=true");}
#endif
}
}
bool encounterFramePanel(int width,int height,FramePanel& out){
 const LONG serial=InterlockedCompareExchange(&toastSerial,0,0);
 const auto at=static_cast<ULONGLONG>(InterlockedCompareExchange64(&toastAt,0,0));
 if(!serial||GetTickCount64()-at>=1800||width<64||height<96)return false;
 int h=height/36;if(h<24)h=24;if(h>48)h=48;int w=h*10;if(w>width-16)w=width-16;
 static PanelCanvas canvas;static LONG painted=0;bool changed=canvas.width!=w||canvas.height!=h;
 if(!canvas.resize(w,h))return false;
 if(changed||painted!=serial){paint(canvas.dc,w,h);GdiFlush();painted=serial;}
 out={width-w-8,height-h-8,w,h,canvas.pixels};return true;
}
bool encountersEnabled(){return InterlockedCompareExchange(&enabled,0,0)!=0;}
const wchar_t* encounterStatus(){return encountersEnabled()?onLabel:offLabel;}
void encounterKeyboard(PBYTE keys,bool focused){
 bool down=keys&&(keys[VK_F5]&0x80);if(!focused||!keys){held=true;return;}
 startUi();if(down&&!held){bool on=!encountersEnabled();InterlockedExchange(&enabled,on?1:0);InterlockedExchange64(&toastAt,static_cast<LONG64>(GetTickCount64()));InterlockedIncrement(&toastSerial);if(trace)trace(on?L"ENCOUNTER_STATE enabled=true key=F5":L"ENCOUNTER_STATE enabled=false key=F5");}
 held=down;keys[VK_F5]=0;
}
bool installEncounterControl(HMODULE module,void(*logger)(const wchar_t*)){
 if(!mapped(reinterpret_cast<BYTE*>(module),imageSize,true))return false;trace=logger;
 wchar_t label[128]{};DWORD n=GetEnvironmentVariableW(L"MC_ENCOUNTER_ON",label,128);if(n&&n<128)wcscpy_s(onLabel,label);
 n=GetEnvironmentVariableW(L"MC_ENCOUNTER_OFF",label,128);if(n&&n<128)wcscpy_s(offLabel,label);
#ifndef ENCOUNTER_CONTROL_TEST
 if(frameOverlayAvailable()){setFramePanel(1,&encounterFramePanel);if(trace)trace(L"ENCOUNTER_FRAME_READY cold_start=direct_backbuffer alt_tab_required=false duration_ms=1800");}
#endif
 if(trace)trace(L"ENCOUNTER_CONTROL_READY initial=on key=F5 scope=random_only counters=preserved scripts=unchanged");return true;
}
bool removeEncounterControl(){
 if(!engine)return true;if(!mapped(engine,imageSize,false))return false;
#ifndef ENCOUNTER_CONTROL_TEST
 if(frameOverlayAvailable())setFramePanel(1,nullptr);
#endif
 if(stopEvent){SetEvent(stopEvent);WaitForSingleObject(uiThread,3000);CloseHandle(uiThread);CloseHandle(stopEvent);uiThread=stopEvent=nullptr;}return true;
}
#ifdef ENCOUNTER_CONTROL_TEST
bool encounterTestMapped(BYTE* p,size_t size,bool on){return mapped(p,size,on);}
void encounterTestReset(){enabled=1;held=true;toastSerial=0;toastAt=0;hudShown=false;renderedSerial=observedSerial=failureSerial=0;renderedRect={};}
void encounterTestPaint(HDC dc,int w,int h){paint(dc,w,h);}
#endif
