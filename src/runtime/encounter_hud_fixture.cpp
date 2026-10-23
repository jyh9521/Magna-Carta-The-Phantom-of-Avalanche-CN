// Production message loop replay with deterministic Win32 presentation boundaries.
// No desktop windows, game modules or interactive application are opened.
#include "encounter_control.h"
#include <cstdio>
#include <stdexcept>
namespace replay {
ULONGLONG now=1000;bool visible=false;int paints=0,invalidations=0,shows=0;POINT position{};SIZE size{};
HWND host=reinterpret_cast<HWND>(1),popup=reinterpret_cast<HWND>(2);bool focused=true;
BOOL WINAPI valid(HWND){return TRUE;}
BOOL WINAPI iconic(HWND){return FALSE;}
HWND WINAPI foreground(){return focused?host:nullptr;}
DWORD WINAPI pid(HWND,LPDWORD p){*p=GetCurrentProcessId();return 1;}
BOOL WINAPI rect(HWND,LPRECT p){*p={0,0,1920,1080};return TRUE;}
BOOL WINAPI origin(HWND,LPPOINT p){*p={100,100};return TRUE;}
DWORD WINAPI wait(HANDLE,DWORD){return WAIT_TIMEOUT;}
ULONGLONG WINAPI clock(){return now;}
BOOL WINAPI show(HWND,int mode){visible=mode!=SW_HIDE;if(visible)++shows;return TRUE;}
BOOL WINAPI move(HWND,HWND,int x,int y,int w,int h,UINT flags){if(!(flags&SWP_NOMOVE))position={x,y};if(!(flags&SWP_NOSIZE))size={w,h};if(flags&SWP_SHOWWINDOW){visible=true;++shows;}return TRUE;}
BOOL WINAPI invalidate(HWND,const RECT*,BOOL){++invalidations;return TRUE;}
int WINAPI text(HDC dc,LPCWSTR str,int count,LPRECT rect,UINT flags){
 if(GetObjectType(dc)!=OBJ_MEMDC)throw std::runtime_error("text drawn to window DC");
 return DrawTextW(dc,str,count,rect,flags);
}
BOOL WINAPI layer(HWND,HDC,POINT* pt,SIZE* s,HDC dc,POINT*,COLORREF,BLENDFUNCTION*,DWORD){
 if(!dc||!pt||!s)return FALSE;position=*pt;size=*s;++paints;return TRUE;
}
}
#define IsWindow replay::valid
#define IsIconic replay::iconic
#define GetForegroundWindow replay::foreground
#define GetWindowThreadProcessId replay::pid
#define GetClientRect replay::rect
#define ClientToScreen replay::origin
#define WaitForSingleObject replay::wait
#define GetTickCount64 replay::clock
#define ShowWindow replay::show
#define SetWindowPos replay::move
#define InvalidateRect replay::invalidate
#define UpdateLayeredWindow replay::layer
#define DrawTextW replay::text
#include "encounter_control.cpp"
void require(bool b,const char* s){if(!b)throw std::runtime_error(s);}
void tick(){windowProc(replay::popup,WM_TIMER,1,0);}
void press(){BYTE k[256]{};encounterKeyboard(k,true);k[VK_F5]=0x80;encounterKeyboard(k,true);}
int main(){try{
 gameWindow=&replay::host;encounterTestReset();
 tick();require(!replay::visible,"HUD visible before first F5 (persistent banner)");
 press();tick();require(replay::visible,"toggle notification missing");
 require(replay::position.x>100&&replay::position.y>100,"unpositioned top-left drawing");
 require(replay::size.cy<=36&&replay::size.cx<=360,"oversized banner");
 int frames=replay::paints,shows=replay::shows;
 require(replay::position.x+replay::size.cx==2004&&replay::position.y+replay::size.cy==1156,"client-relative lower-right placement");
 for(int i=0;i<20;++i){replay::now+=50;tick();}
 require(replay::paints==frames&&replay::invalidations==0&&replay::shows==shows,"unchanged HUD redraws every timer");
 replay::now=2799;tick();require(replay::visible,"notification expires too early");
 replay::now=2800;tick();require(!replay::visible,"HUD still visible after two seconds");
 press();tick();require(replay::visible&&replay::paints==frames+1,"second toggle does not refresh bitmap");
 replay::focused=false;tick();require(!replay::visible,"unfocused HUD visible");
 replay::now+=2100;replay::focused=true;tick();require(!replay::visible,"expired toast reappears on refocus");
 puts("ENCOUNTER_HUD PASS startup=hidden duration=1800ms size=compact redraw=on_change only=layered_bitmap origin=positioned focus=hidden game_started=false");return 0;
}catch(const std::exception& e){printf("ENCOUNTER_HUD FAIL %s\n",e.what());return 1;}}
