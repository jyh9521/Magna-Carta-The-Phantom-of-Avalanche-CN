#include "window_mode.h"
#include <cstring>
#include <algorithm>
#include <initializer_list>
#include <intrin.h>
bool setNativeWindowed(BYTE* image,size_t available,bool enabled){
 if(!image||available<0x10b000)return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+dos->e_lfanew);
 if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 // 原生设置装载器：mov dword ptr [engine+f1b40],1；仅将立即数切换为0。
 BYTE expected[]={0xc7,0x05,0,0,0,0,1,0,0,0};
 *reinterpret_cast<DWORD*>(expected+2)=reinterpret_cast<DWORD>(image+0xf1b40);
 BYTE* site=image+0x9a0e;
 if(memcmp(site,expected,6)||site[6]>1||memcmp(site+7,expected+7,3))return false;
 BYTE desired=enabled?0:1;if(site[6]==desired)return true;
 DWORD old=0;if(!VirtualProtect(site+6,1,PAGE_EXECUTE_READWRITE,&old))return false;
 BYTE before=site[6];site[6]=desired;
 bool ok=FlushInstructionCache(GetCurrentProcess(),site+6,1)!=FALSE;DWORD unused=0;
 if(!ok||!VirtualProtect(site+6,1,old,&unused)){site[6]=before;FlushInstructionCache(GetCurrentProcess(),site+6,1);VirtualProtect(site+6,1,old,&unused);return false;}
 return true;
}
// Window size is separate from the engine's logical render/input dimensions.
namespace {
using CreateWindowFn=decltype(&CreateWindowExA);
using GetCursorFn=decltype(&GetCursorPos);
using SetCursorFn=decltype(&SetCursorPos);
using OffsetFn=decltype(&OffsetRect);
using ClientRectFn=decltype(&GetClientRect);
CreateWindowFn originalCreateWindow=nullptr;
GetCursorFn originalGetCursor=nullptr;
SetCursorFn originalSetCursor=nullptr;
OffsetFn originalOffset=nullptr;
ClientRectFn originalClientRect=nullptr;
ULONG_PTR allocationCaller=0;
HWND sizedWindow=nullptr;
int requestedWidth=0,requestedHeight=0,logicalWidth=0,logicalHeight=0;
ULONG_PTR presentCaller=0;
void(*windowTrace)(const wchar_t*)=nullptr;
bool imageHeader(BYTE* image,size_t available,DWORD size){
 if(!image||available<size)return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+dos->e_lfanew);
 return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&nt->OptionalHeader.SizeOfImage==size;
}
bool replaceSlot(DWORD* slot,DWORD from,DWORD to){
 if(*slot==to)return true;if(*slot!=from)return false;
 DWORD old=0;if(!VirtualProtect(slot,4,PAGE_READWRITE,&old))return false;
 InterlockedExchange(reinterpret_cast<LONG*>(slot),static_cast<LONG>(to));DWORD unused=0;
 if(!VirtualProtect(slot,4,old,&unused)){InterlockedExchange(reinterpret_cast<LONG*>(slot),static_cast<LONG>(from));VirtualProtect(slot,4,old,&unused);return false;}return true;
}
bool windowCoordinates(POINT& origin,RECT& client){
 origin={0,0};return sizedWindow&&IsWindow(sizedWindow)&&ClientToScreen(sizedWindow,&origin)&&GetClientRect(sizedWindow,&client)&&client.right>0&&client.bottom>0&&logicalWidth>0&&logicalHeight>0;
}
POINT scalePoint(POINT point,POINT origin,int fromW,int fromH,int toW,int toH){
 return {origin.x+MulDiv(point.x-origin.x,toW,fromW),origin.y+MulDiv(point.y-origin.y,toH,fromH)};
}
BOOL WINAPI sizedGetCursor(LPPOINT point){
 BOOL result=originalGetCursor(point);POINT origin{};RECT client{};
 if(result&&point&&windowCoordinates(origin,client))*point=scalePoint(*point,origin,client.right,client.bottom,logicalWidth,logicalHeight);
 return result;
}
BOOL WINAPI sizedSetCursor(int x,int y){
 POINT point{x,y},origin{};RECT client{};
 if(windowCoordinates(origin,client))point=scalePoint(point,origin,logicalWidth,logicalHeight,client.right,client.bottom);
 return originalSetCursor(point.x,point.y);
}
HWND WINAPI sizedCreateWindow(DWORD ex,LPCSTR cls,LPCSTR title,DWORD style,int x,int y,int width,int height,HWND parent,HMENU menu,HINSTANCE instance,LPVOID param){
 HWND window=originalCreateWindow(ex,cls,title,style,x,y,width,height,parent,menu,instance,param);
 if(window&&!parent&&style==0x12ca0000&&requestedWidth>0){
  RECT client{};if(!GetClientRect(window,&client)||!resizeWindowClient(window,requestedWidth,requestedHeight)){DestroyWindow(window);return nullptr;}
  logicalWidth=client.right;logicalHeight=client.bottom;sizedWindow=window;
  if(windowTrace){GetClientRect(window,&client);wchar_t line[160]{};swprintf_s(line,L"WINDOW_CLIENT_SIZE requested=%dx%d actual=%ldx%ld logical=%dx%d",requestedWidth,requestedHeight,client.right,client.bottom,logicalWidth,logicalHeight);windowTrace(line);}
 }
 return window;
}
BOOL WINAPI logicalClientRect(HWND window,LPRECT rect){
 BOOL result=originalClientRect(window,rect);
 // Only the native backbuffer allocation call, not other driver/Win32 consumers.
 if(result&&rect&&window==sizedWindow&&logicalWidth>0&&logicalHeight>0&&reinterpret_cast<ULONG_PTR>(_ReturnAddress())==allocationCaller){
  static bool reported=false;
  if(windowTrace&&!reported){wchar_t line[160]{};swprintf_s(line,L"WINDOW_BACKBUFFER_SIZE logical=%dx%d physical=%ldx%ld",logicalWidth,logicalHeight,rect->right,rect->bottom);windowTrace(line);reported=true;}
  *rect={0,0,logicalWidth,logicalHeight};
 }
 return result;
}
BOOL dispatchOffset(LPRECT rect,int x,int y,ULONG_PTR caller){
 POINT origin{};RECT client{};
 if(rect&&caller==presentCaller&&windowCoordinates(origin,client)){
  static bool reported=false;
  if(windowTrace&&!reported){wchar_t line[160]{};swprintf_s(line,L"WINDOW_PRESENT_SIZE source=%ldx%ld destination=%ldx%ld",rect->right-rect->left,rect->bottom-rect->top,client.right,client.bottom);windowTrace(line);reported=true;}
  rect->right=rect->left+client.right;rect->bottom=rect->top+client.bottom;
 }
 return originalOffset(rect,x,y);
}
BOOL WINAPI sizedOffset(LPRECT rect,int x,int y){return dispatchOffset(rect,x,y,reinterpret_cast<ULONG_PTR>(_ReturnAddress()));}
}
bool parseWindowResolution(const wchar_t* value,int& width,int& height){
 struct Size{const wchar_t* text;int w,h;};
 for(auto s:{Size{L"960x540",960,540},Size{L"1280x720",1280,720},Size{L"1600x900",1600,900},Size{L"1920x1080",1920,1080},Size{L"2560x1440",2560,1440}}){if(value&&!wcscmp(value,s.text)){width=s.w;height=s.h;return true;}}
 return false;
}
bool resizeWindowClient(HWND window,int width,int height){
 if(!window||width<=0||height<=0)return false;
 MONITORINFO monitor{sizeof(monitor)};if(!GetMonitorInfoW(MonitorFromWindow(window,MONITOR_DEFAULTTONEAREST),&monitor))return false;
 DWORD style=static_cast<DWORD>(GetWindowLongPtrW(window,GWL_STYLE)),ex=static_cast<DWORD>(GetWindowLongPtrW(window,GWL_EXSTYLE));
 RECT border{0,0,0,0};if(!AdjustWindowRectEx(&border,style,GetMenu(window)!=nullptr,ex))return false;
 int maxW=monitor.rcWork.right-monitor.rcWork.left-(border.right-border.left),maxH=monitor.rcWork.bottom-monitor.rcWork.top-(border.bottom-border.top);
 if(maxW<16||maxH<9)return false;
 // Integer 16:9 fit, including borders and the taskbar, never an offscreen title bar.
 int units=(std::min)({width/16,height/9,maxW/16,maxH/9});if(units<1)return false;
 RECT rect{0,0,units*16,units*9};if(!AdjustWindowRectEx(&rect,style,GetMenu(window)!=nullptr,ex))return false;
 int w=rect.right-rect.left,h=rect.bottom-rect.top;
 return SetWindowPos(window,nullptr,monitor.rcWork.left+(monitor.rcWork.right-monitor.rcWork.left-w)/2,monitor.rcWork.top+(monitor.rcWork.bottom-monitor.rcWork.top-h)/2,w,h,SWP_NOZORDER|SWP_NOACTIVATE)!=FALSE;
}
bool installWindowSizing(BYTE* image,size_t available,int width,int height,void(*logger)(const wchar_t*)){
 if(!imageHeader(image,available,0x10b000))return false;
 int w=0,h=0;wchar_t value[40]{};swprintf_s(value,L"%dx%d",width,height);if(!parseWindowResolution(value,w,h))return false;
 const DWORD offsets[]={0xbd418,0xbd3e8,0xbd3e4};
 const char* names[]={"CreateWindowExA","GetCursorPos","SetCursorPos"};
 const DWORD hooks[]={reinterpret_cast<DWORD>(sizedCreateWindow),reinterpret_cast<DWORD>(sizedGetCursor),reinterpret_cast<DWORD>(sizedSetCursor)};
 DWORD originals[3]{};HMODULE user=GetModuleHandleW(L"user32.dll");
 for(int i=0;i<3;++i){originals[i]=reinterpret_cast<DWORD>(GetProcAddress(user,names[i]));if(!originals[i]||(*reinterpret_cast<DWORD*>(image+offsets[i])!=originals[i]&&*reinterpret_cast<DWORD*>(image+offsets[i])!=hooks[i]))return false;}
 // Validate the main game window call before touching any IAT slot.
 if(image[0xc1e3]!=0xff||image[0xc1e4]!=0x15||*reinterpret_cast<DWORD*>(image+0xc1e5)!=reinterpret_cast<DWORD>(image+0xbd418))return false;
 DWORD previous[3]{};for(int i=0;i<3;++i)previous[i]=*reinterpret_cast<DWORD*>(image+offsets[i]);
 for(int i=0;i<3;++i)if(!replaceSlot(reinterpret_cast<DWORD*>(image+offsets[i]),previous[i],hooks[i])){for(int j=i-1;j>=0;--j)replaceSlot(reinterpret_cast<DWORD*>(image+offsets[j]),hooks[j],previous[j]);return false;}
 originalCreateWindow=reinterpret_cast<CreateWindowFn>(originals[0]);originalGetCursor=reinterpret_cast<GetCursorFn>(originals[1]);originalSetCursor=reinterpret_cast<SetCursorFn>(originals[2]);requestedWidth=w;requestedHeight=h;windowTrace=logger;return true;
}
bool installWindowPresentation(BYTE* image,size_t available){
 if(!imageHeader(image,available,0x2c000))return false;
 if(image[0x31f7]!=0xff||image[0x31f8]!=0x15||*reinterpret_cast<DWORD*>(image+0x31f9)!=reinterpret_cast<DWORD>(image+0x1a55c))return false;
 if(image[0x2a4c]!=0xff||image[0x2a4d]!=0x15||*reinterpret_cast<DWORD*>(image+0x2a4e)!=reinterpret_cast<DWORD>(image+0x1a560))return false;
 const DWORD offsets[]={0x1a55c,0x1a560};
 const char* names[]={"OffsetRect","GetClientRect"};
 const DWORD hooks[]={reinterpret_cast<DWORD>(sizedOffset),reinterpret_cast<DWORD>(logicalClientRect)};
 DWORD originals[2]{},previous[2]{};
 for(int i=0;i<2;++i){originals[i]=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),names[i]));previous[i]=*reinterpret_cast<DWORD*>(image+offsets[i]);if(!originals[i]||(previous[i]!=originals[i]&&previous[i]!=hooks[i]))return false;}
 for(int i=0;i<2;++i)if(!replaceSlot(reinterpret_cast<DWORD*>(image+offsets[i]),previous[i],hooks[i])){for(int j=i-1;j>=0;--j)replaceSlot(reinterpret_cast<DWORD*>(image+offsets[j]),hooks[j],previous[j]);return false;}
 originalOffset=reinterpret_cast<OffsetFn>(originals[0]);originalClientRect=reinterpret_cast<ClientRectFn>(originals[1]);
 presentCaller=reinterpret_cast<ULONG_PTR>(image+0x31fd);allocationCaller=reinterpret_cast<ULONG_PTR>(image+0x2a52);return true;
}
#ifdef WINDOW_SIZE_TEST
void configureWindowApisFixture(CreateWindowFn create,GetCursorFn get,SetCursorFn set){originalCreateWindow=create;originalGetCursor=get;originalSetCursor=set;}
void configureWindowSizeFixture(HWND window,int width,int height,ULONG_PTR caller){sizedWindow=window;logicalWidth=width;logicalHeight=height;presentCaller=caller;originalOffset=&OffsetRect;}
BOOL offsetWindowSizeFixture(LPRECT rect,int x,int y,ULONG_PTR caller){return dispatchOffset(rect,x,y,caller);}
POINT mapWindowSizeFixture(POINT point,POINT origin,int fw,int fh,int tw,int th){return scalePoint(point,origin,fw,fh,tw,th);}
#endif
