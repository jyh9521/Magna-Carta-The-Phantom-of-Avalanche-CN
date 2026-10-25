// Production canvas and window-paint boundary probe; no game or visible windows.
#include "map_overlay.h"
#include <objidl.h>
#include <gdiplus.h>
#include <cstdio>
#include <chrono>
static int allocations=0,windowBlits=0;static bool painting=false;
static HDC probeDC=nullptr;
HBITMAP WINAPI countedBitmap(HDC d,int w,int h){++allocations;return CreateCompatibleBitmap(d,w,h);}
HBITMAP WINAPI countedDIB(HDC d,const BITMAPINFO* i,UINT u,void** p,HANDLE h,DWORD o){++allocations;return CreateDIBSection(d,i,u,p,h,o);}
BOOL WINAPI countedBlit(HDC d,int x,int y,int w,int h,HDC s,int a,int b,DWORD rop){if(painting)++windowBlits;return BitBlt(d,x,y,w,h,s,a,b,rop);}
HDC WINAPI probePaint(HWND,LPPAINTSTRUCT p){p->hdc=probeDC;return probeDC;}
BOOL WINAPI probeEnd(HWND,const PAINTSTRUCT*){return TRUE;}
BOOL WINAPI probeRect(HWND,LPRECT r){*r={0,0,1280,720};return TRUE;}
BOOL WINAPI probeValidate(HWND,const RECT*){return TRUE;}
#define CreateCompatibleBitmap countedBitmap
#define CreateDIBSection countedDIB
#define BitBlt countedBlit
#define BeginPaint probePaint
#define EndPaint probeEnd
#define GetClientRect probeRect
#define ValidateRect probeValidate
#ifndef MAP_PROBE_SOURCE
#define MAP_PROBE_SOURCE "map_overlay.cpp"
#endif
#include MAP_PROBE_SOURCE
int wmain(int argc,wchar_t** argv){
 if(argc<2)return 2;
 Gdiplus::GdiplusStartupInput input;ULONG_PTR token=0;Gdiplus::GdiplusStartup(&token,&input,nullptr);
 wcscpy_s(assetDirectory,argv[1]);canvas.player.valid=true;canvas.player.identifier=9;canvas.player.fieldIdentifier=29;canvas.player.actorIdentifier=1;canvas.player.directionX=1;canvas.display.mode=MapDisplayMode::Full;canvas.scale=1;load(9);
 if(!canvas.image)return 3;
 probeDC=CreateCompatibleDC(nullptr);HBITMAP bitmap=::CreateDIBSection(nullptr,[](){static BITMAPINFO i{};i.bmiHeader.biSize=40;i.bmiHeader.biWidth=1280;i.bmiHeader.biHeight=-720;i.bmiHeader.biPlanes=1;i.bmiHeader.biBitCount=32;return &i;}(),DIB_RGB_COLORS,nullptr,nullptr,0);auto old=SelectObject(probeDC,bitmap);
 painting=true;
#ifdef MAP_FRAME_PRESENT_V2
 configured=true;snapshot=canvas.player;snapshot.timestamp=GetTickCount();FramePanel panel{};
 if(!mapFramePanel(1280,720,panel)||!panel.alphaDC||panel.x!=0||panel.y!=0)return 4;
#else
 windowProc(nullptr,WM_PAINT,0,0);
#endif
 painting=false;
 const auto start=std::chrono::steady_clock::now();allocations=0;
 for(int i=0;i<60;++i){canvas.player.x=float(i);renderCanvas(probeDC,1280,720);}
 const auto ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count()/60;
 MapMetadata m{{'M','C','M','1'},2048,2048,{0,0,2048,2048},{0,0},1};MapView v;mapView(m,100,100,true,v);MapOverlayLayout l;mapOverlayLayout(1920,1080,MapDisplayMode::Mini,l);
 bool pass=windowBlits==0&&allocations<=2&&v.span>=720&&l.x>=960&&l.y>=200;
 printf("MAP_PRESENTATION %s window_dc_blits=%d recurring_bitmap_allocations=%d mini_span=%.0f anchor=%d,%d moving_full_ms=%.3f game_started=false\n",pass?"PASS":"FAIL",windowBlits,allocations,v.span,l.x,l.y,ms);
#ifdef MAP_FRAME_PRESENT_V2
 // Repeat actual native provider transitions without a window or desktop.
 configured=true;canvas.display.mode=MapDisplayMode::Mini;snapshot.timestamp=GetTickCount();wasActive=false;
 FramePanel p{};if(!mapFramePanel(1280,720,p)||p.x<640||p.y<144||!p.alphaDC)return 5;
 canvas.display.mode=MapDisplayMode::Full;wasActive=false;snapshot.timestamp=GetTickCount();
 if(!mapFramePanel(1280,720,p)||p.x!=0||p.y!=0||p.width!=1280||p.height!=720)return 6;
 const auto cpuStart=std::chrono::steady_clock::now();
 for(int i=0;i<60;++i){snapshot.x=float(i);snapshot.timestamp=GetTickCount();lastFrameAt=GetTickCount()-34;
  if(!mapFramePanel(1280,720,p))return 12;
  BLENDFUNCTION blend{AC_SRC_OVER,0,255,AC_SRC_ALPHA};if(!AlphaBlend(probeDC,0,0,1280,720,p.alphaDC,0,0,1280,720,blend))return 13;
 }
 printf("MAP_NATIVE_PANEL moving_blend_ms=%.3f size=1280x720 game_started=false\n",std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-cpuStart).count()/60);
 const auto builds=terrainBuilds;for(int i=0;i<30;++i){canvas.player.x+=1;composeCanvas(1280,720);}
 if(terrainBuilds!=builds)return 7;
 if(!composeCanvas(800,600)||terrainBuilds!=builds+1)return 8;
 canvas.display.mode=MapDisplayMode::Off;snapshot.timestamp=GetTickCount();if(mapFramePanel(800,600,p)||p.pixels||p.alphaDC)return 9;
 canvas.display.mode=MapDisplayMode::Full;snapshot.valid=false;if(mapFramePanel(800,600,p)||p.pixels||p.alphaDC)return 10;
 for(int ui:{480,600,1080})for(auto dims:{SIZE{640,480},SIZE{800,600},SIZE{1280,720},SIZE{1920,1080},SIZE{3440,1440},SIZE{3840,2160},SIZE{7680,4320},SIZE{1080,1920}}){
  MapOverlayLayout a;if(!mapOverlayLayout(dims.cx,dims.cy,MapDisplayMode::Mini,a,ui)||a.y<=97.f*dims.cy/ui||a.x+a.width>dims.cx||a.y+a.height>dims.cy)return 11;
 }
 puts("MAP_PANEL_LIFECYCLE PASS mini_full_off=exclusive stale=hidden resize=rebuilt moving_full_cache=retained resolutions=24 compass_alpha_bottom=97");
#endif
 // Include-owned production caches must be released before shutting down GDI+.
#ifdef MAP_FRAME_PRESENT_V2
 stopMapOverlay();
 if(argc==4){snapshot={};snapshot.valid=true;snapshot.identifier=225;snapshot.fieldIdentifier=-1;snapshot.actorIdentifier=0;snapshot.x=-489.4f;snapshot.y=-46.9f;snapshot.directionX=1;
  if(!mapOverlayTestRenderMode(argv[1],argv[2],MapDisplayMode::Mini,304,304,false)||!mapOverlayTestRenderMode(argv[1],argv[3],MapDisplayMode::Full,1280,720,true))return 14;
 }
#endif
 SelectObject(probeDC,old);DeleteObject(bitmap);DeleteDC(probeDC);delete canvas.image;canvas.image=nullptr;
 Gdiplus::GdiplusShutdown(token);return pass?0:1;
}
