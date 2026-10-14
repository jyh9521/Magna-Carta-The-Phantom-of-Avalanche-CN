#include "map_overlay.h"
#ifndef MAP_OVERLAY_TEST
#include "modern_gamepad.h"
#endif
#include <objidl.h>
#include <gdiplus.h>
#include <memory>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <cstdio>
using namespace Gdiplus;
namespace {
BYTE* engine=nullptr;void(*trace)(const wchar_t*)=nullptr;
SRWLOCK snapshotLock=SRWLOCK_INIT;MapSnapshot snapshot;
MapTrailPoint history[128]{};unsigned historyCount=0;BYTE* historyActor=nullptr;int historyMap=-1;
HANDLE uiThread=nullptr,stopEvent=nullptr,initEvent=nullptr;DWORD uiThreadId=0;volatile LONG initStatus=-1,uiStarted=0;bool configured=false;HWND overlayWindow=nullptr;
wchar_t assetDirectory[32768]{};wchar_t label[256]=L"Terrain geometry";
wchar_t legend[256]=L"N NPC    B Box    P Player";
bool readable(const void* a,size_t n){auto p=reinterpret_cast<ULONG_PTR>(a),end=p+n;if(!p||end<p)return false;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;}
struct Canvas {MapMetadata metadata{};Bitmap* image=nullptr;MapSnapshot player;int loaded=-2;float scale=1;bool mini=false,large=false,heldMini=false,heldLarge=false;};
Canvas canvas;
unsigned mapPad(){
#ifdef MAP_OVERLAY_TEST
 return 0;
#else
 return modernGamepadMapButtons();
#endif
}
DWORD WINAPI threadMain(void*);
void startUi(){
 if(!configured||InterlockedCompareExchange(&uiStarted,1,0)!=0)return;
 stopEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);initEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);
 if(!stopEvent||!initEvent){if(stopEvent)CloseHandle(stopEvent);if(initEvent)CloseHandle(initEvent);stopEvent=initEvent=nullptr;if(trace)trace(L"MAP_OVERLAY_WINDOW_FAILED reason=event_creation");return;}
 InterlockedExchange(&initStatus,-1);uiThread=CreateThread(nullptr,0,threadMain,nullptr,0,&uiThreadId);
 if(!uiThread){CloseHandle(stopEvent);CloseHandle(initEvent);stopEvent=initEvent=nullptr;if(trace)trace(L"MAP_OVERLAY_WINDOW_FAILED reason=thread_creation");}
}
void load(int identifier){
 canvas.loaded=identifier;delete canvas.image;canvas.image=nullptr;wchar_t path[32768];swprintf_s(path,L"%s\\%04d.map",assetDirectory,identifier);
 HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(file==INVALID_HANDLE_VALUE){if(trace)trace(L"MAP_OVERLAY_ASSET_UNAVAILABLE version_or_coverage=unsupported");return;}
 DWORD count=0;bool ok=GetFileSize(file,nullptr)==sizeof(MapMetadata)&&ReadFile(file,&canvas.metadata,sizeof(MapMetadata),&count,nullptr)&&count==sizeof(MapMetadata);CloseHandle(file);
 if(!ok||!mapMetadataValid(canvas.metadata))return;
 swprintf_s(path,L"%s\\%04d.png",assetDirectory,identifier);auto image=std::make_unique<Bitmap>(path);
 if(image->GetLastStatus()!=Ok||image->GetWidth()!=canvas.metadata.width||image->GetHeight()!=canvas.metadata.height)return;
 canvas.image=image.release();if(trace)trace(L"MAP_OVERLAY_ASSET_LOADED projection=first_frame geometry_only=true");
}
void renderCanvas(HDC target,int width,int height){
 HDC dc=CreateCompatibleDC(target);HBITMAP buffer=CreateCompatibleBitmap(target,std::max(width,1),std::max(height,1));auto old=SelectObject(dc,buffer);
 {
 Graphics graphics(dc);graphics.Clear(Color(255,19,32,39));graphics.SetSmoothingMode(SmoothingModeAntiAlias);
 if(canvas.image){int size=std::max(1,std::min(width-int(24*canvas.scale),height-int(84*canvas.scale)));int x=(width-size)/2,y=int(36*canvas.scale);MapView view;
  if(mapView(canvas.metadata,canvas.player.x,canvas.player.y,canvas.mini,view)){
   graphics.SetClip(Rect(x,y,size,size));float zoom=float(size)/view.span;
   // Clipping the shifted/scaled atlas keeps minimap edges centered on the player.
   graphics.DrawImage(canvas.image,REAL(x-view.left*zoom),REAL(y-view.top*zoom),REAL(canvas.metadata.width*zoom),REAL(canvas.metadata.height*zoom));
   auto point=[&](float wx,float wy,float& px,float& py){if(!mapViewPoint(canvas.metadata,view,wx,wy,float(size),px,py))return false;px+=x;py+=y;return true;};
   float worldSpan=view.span/canvas.metadata.scale;float step=std::pow(10.f,std::floor(std::log10(worldSpan/5.f)));if(!std::isfinite(step)||step<=0)step=1;if(worldSpan/step>10)step*=5;else if(worldSpan/step>5)step*=2;
   float minX=canvas.metadata.bounds[0]+(view.left-canvas.metadata.origin[0])/canvas.metadata.scale;
   float maxY=canvas.metadata.bounds[1]+(canvas.metadata.height-canvas.metadata.origin[1]-view.top)/canvas.metadata.scale;
   Pen grid(Color(80,132,158,164),1);
   for(unsigned i=0;i<16;++i){float wx=std::ceil(minX/step)*step+i*step;if(wx>minX+worldSpan)break;float px=0,py=0;if(point(wx,maxY,px,py))graphics.DrawLine(&grid,px,REAL(y),px,REAL(y+size));}
   for(unsigned i=0;i<16;++i){float wy=std::floor(maxY/step)*step-i*step;if(wy<maxY-worldSpan)break;float px=0,py=0;if(point(minX,wy,px,py))graphics.DrawLine(&grid,REAL(x),py,REAL(x+size),py);}
   Pen trail(Color(210,245,213,106),2*canvas.scale);
   for(unsigned i=1;i<canvas.player.trailCount;++i){float ax=0,ay=0,bx=0,by=0;if(point(canvas.player.trail[i-1].x,canvas.player.trail[i-1].y,ax,ay)&&point(canvas.player.trail[i].x,canvas.player.trail[i].y,bx,by))graphics.DrawLine(&trail,ax,ay,bx,by);}
   for(unsigned i=0;i<canvas.player.landmarkCount;++i){auto m=canvas.player.landmarks[i];float px=0,py=0;if(!point(m.x,m.y,px,py))continue;
    float radius=5*canvas.scale;SolidBrush brush(m.kind==1?Color(255,75,205,244):Color(255,181,114,235));
    if(m.kind==1)graphics.FillEllipse(&brush,px-radius,py-radius,2*radius,2*radius);else graphics.FillRectangle(&brush,px-radius,py-radius,2*radius,2*radius);
   }
   float px=0,py=0;if(point(canvas.player.x,canvas.player.y,px,py)){
    SolidBrush player(Color(255,255,166,35));float dx=canvas.player.directionX,dy=-canvas.player.directionY,length=std::hypot(dx,dy),r=8*canvas.scale;
    if(length>.001f){dx/=length;dy/=length;PointF arrow[]={{px+dx*r,py+dy*r},{px-dx*r*.7f-dy*r*.7f,py-dy*r*.7f+dx*r*.7f},{px-dx*r*.7f+dy*r*.7f,py-dy*r*.7f-dx*r*.7f}};graphics.FillPolygon(&player,arrow,3);}
    else graphics.FillEllipse(&player,px-r*.6f,py-r*.6f,r*1.2f,r*1.2f);
   }
   graphics.ResetClip();
  }
 }
 }
 SetBkMode(dc,TRANSPARENT);SetTextColor(dc,RGB(235,221,182));HFONT font=CreateFontW(-int(18*canvas.scale),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,L"Segoe UI");auto oldFont=SelectObject(dc,font);
 wchar_t title[320];swprintf_s(title,L"%s  %04d",label,canvas.player.identifier);TextOutW(dc,int(12*canvas.scale),int(9*canvas.scale),title,static_cast<int>(wcslen(title)));SelectObject(dc,oldFont);DeleteObject(font);
 font=CreateFontW(-int(14*canvas.scale),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,L"Segoe UI");oldFont=SelectObject(dc,font);
 TextOutW(dc,int(12*canvas.scale),height-int(42*canvas.scale),legend,static_cast<int>(wcslen(legend)));
 bool outside=canvas.player.x<canvas.metadata.bounds[0]||canvas.player.x>canvas.metadata.bounds[2]||canvas.player.y<canvas.metadata.bounds[1]||canvas.player.y>canvas.metadata.bounds[3];
 swprintf_s(title,L"X %.1f   Y %.1f   N:%u  B:%u%s%s",canvas.player.x,canvas.player.y,unsigned(std::count_if(canvas.player.landmarks,canvas.player.landmarks+canvas.player.landmarkCount,[](const MapLandmark& m){return m.kind==1;})),unsigned(std::count_if(canvas.player.landmarks,canvas.player.landmarks+canvas.player.landmarkCount,[](const MapLandmark& m){return m.kind==2;})),canvas.player.landmarksTruncated?L"+":L"",outside?L"  !":L"");
 TextOutW(dc,int(12*canvas.scale),height-int(22*canvas.scale),title,static_cast<int>(wcslen(title)));SelectObject(dc,oldFont);DeleteObject(font);
 BitBlt(target,0,0,width,height,dc,0,0,SRCCOPY);SelectObject(dc,old);DeleteObject(buffer);DeleteDC(dc);
}
void paint(HWND window){PAINTSTRUCT ps{};HDC target=BeginPaint(window,&ps);RECT r{};GetClientRect(window,&r);renderCanvas(target,r.right,r.bottom);EndPaint(window,&ps);}
LRESULT CALLBACK windowProc(HWND window,UINT message,WPARAM w,LPARAM l){
 if(message==WM_NCHITTEST)return HTTRANSPARENT;
 if(message==WM_MOUSEACTIVATE)return MA_NOACTIVATE;
 if(message==WM_ERASEBKGND)return 1;
 if(message==WM_PAINT){paint(window);return 0;}
 if(message==WM_TIMER){
  if(WaitForSingleObject(stopEvent,0)==WAIT_OBJECT_0){DestroyWindow(window);return 0;}
  HWND game=GetForegroundWindow();DWORD pid=0;GetWindowThreadProcessId(game,&pid);auto current=readMapSnapshot();
  bool active=pid==GetCurrentProcessId()&&game!=window&&GetAncestor(game,GA_ROOTOWNER)==game&&current.valid&&DWORD(GetTickCount()-current.timestamp)<250;
  if(!active){canvas.heldLarge=canvas.heldMini=true;ShowWindow(window,SW_HIDE);return 0;}
  unsigned pad=mapPad();bool large=(GetAsyncKeyState(VK_F8)&0x8000)!=0||(pad&1),mini=(GetAsyncKeyState(VK_F9)&0x8000)!=0||(pad&2);
  if(large&&!canvas.heldLarge){canvas.large=!canvas.large;if(canvas.large)canvas.mini=false;}
  if(mini&&!canvas.heldMini){canvas.mini=!canvas.mini;if(canvas.mini)canvas.large=false;}canvas.heldLarge=large;canvas.heldMini=mini;
  canvas.player=current;if(canvas.loaded!=current.identifier)load(current.identifier);
  if(!canvas.image||(!canvas.large&&!canvas.mini)){ShowWindow(window,SW_HIDE);return 0;}
  RECT client{};GetClientRect(game,&client);POINT origin{};ClientToScreen(game,&origin);
  canvas.scale=std::clamp(float(client.bottom)/1080.f,.75f,2.f);
  int width=canvas.large?std::min(int(1000*canvas.scale),int(client.right*.72f)):std::min(int(320*canvas.scale),int(client.right/3));
  int height=canvas.large?std::min(int(1000*canvas.scale),int(client.bottom*.72f)):width+int(36*canvas.scale);
  int x=canvas.large?origin.x+(client.right-width)/2:origin.x+24;
  int y=canvas.large?origin.y+(client.bottom-height)/2:origin.y+24;
  SetWindowPos(window,HWND_TOPMOST,x,y,width,height,SWP_NOACTIVATE|SWP_SHOWWINDOW);InvalidateRect(window,nullptr,FALSE);return 0;
 }
 if(message==WM_DESTROY){PostQuitMessage(0);return 0;}
 return DefWindowProcW(window,message,w,l);
}
DWORD WINAPI threadMain(void*){
 GdiplusStartupInput input;ULONG_PTR token=0;if(GdiplusStartup(&token,&input,nullptr)!=Ok){InterlockedExchange(&initStatus,1);SetEvent(initEvent);return 1;}
 WNDCLASSW cls{};cls.lpfnWndProc=windowProc;cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"MagnaCartaTerrainOverlay";
 if(!RegisterClassW(&cls)){InterlockedExchange(&initStatus,2);SetEvent(initEvent);GdiplusShutdown(token);return 2;}
 HWND window=CreateWindowExW(WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW|WS_EX_LAYERED|WS_EX_TRANSPARENT,cls.lpszClassName,L"",WS_POPUP,0,0,320,356,nullptr,nullptr,cls.hInstance,nullptr);
 overlayWindow=window;InterlockedExchange(&initStatus,window?0:3);SetEvent(initEvent);if(trace)trace(window?L"MAP_OVERLAY_WINDOW_READY initial=hidden no_activation=true":L"MAP_OVERLAY_WINDOW_FAILED reason=window_creation");
 if(window){SetLayeredWindowAttributes(window,0,235,LWA_ALPHA);SetTimer(window,1,33,nullptr);MSG message{};while(GetMessageW(&message,nullptr,0,0)>0){TranslateMessage(&message);DispatchMessageW(&message);}}
 delete canvas.image;canvas.image=nullptr;overlayWindow=nullptr;UnregisterClassW(cls.lpszClassName,cls.hInstance);GdiplusShutdown(token);return window?0:3;
}
}
static_assert(sizeof(MapMetadata)==40,"MCM1 metadata layout");
bool mapMetadataValid(const MapMetadata& m){if(memcmp(m.magic,"MCM1",4)||m.width<128||m.width>2048||m.width!=m.height)return false;for(float f:m.bounds)if(!std::isfinite(f))return false;return m.bounds[2]>m.bounds[0]&&m.bounds[3]>m.bounds[1]&&std::isfinite(m.origin[0])&&std::isfinite(m.origin[1])&&std::isfinite(m.scale)&&m.scale>0;}
bool mapPixel(const MapMetadata& m,float x,float y,float& px,float& py){if(!mapMetadataValid(m)||!std::isfinite(x)||!std::isfinite(y))return false;px=m.origin[0]+(x-m.bounds[0])*m.scale;py=m.height-m.origin[1]-(y-m.bounds[1])*m.scale;return std::isfinite(px)&&std::isfinite(py);}
bool mapView(const MapMetadata& m,float x,float y,bool mini,MapView& v){float px=0,py=0;if(!mapPixel(m,x,y,px,py))return false;v={0,0,float(m.width)};if(mini){v.span=std::clamp(m.scale*240.f,16.f,float(m.width));v.left=px-v.span/2;v.top=py-v.span/2;}return true;}
bool mapViewPoint(const MapMetadata& m,const MapView& v,float x,float y,float size,float& px,float& py){if(!std::isfinite(v.span)||v.span<=0||!std::isfinite(v.left)||!std::isfinite(v.top)||!std::isfinite(size)||size<=0||!mapPixel(m,x,y,px,py))return false;px=(px-v.left)*size/v.span;py=(py-v.top)*size/v.span;return std::isfinite(px)&&std::isfinite(py);}
void observeMapWorld(BYTE* scene,bool controlled){MapSnapshot value;
 bool sameMap=false;
 if(engine&&readable(scene,0x1568)){
  auto level=*reinterpret_cast<BYTE**>(scene+0x1558);
  if(readable(level,0x10c)&&*reinterpret_cast<BYTE**>(level)==engine+0xc15ac){auto brush=*reinterpret_cast<BYTE**>(level+0xf0);
   if(readable(brush,0x128)&&*reinterpret_cast<BYTE**>(brush)==engine+0xbdcec){auto info=*reinterpret_cast<BYTE**>(brush+0x124);sameMap=readable(info,4)&&*reinterpret_cast<int*>(info)==*reinterpret_cast<int*>(scene+0x10d0);}}
 }
 if(sameMap&&controlled&&engine&&readable(scene,0x1568)&&*reinterpret_cast<BYTE**>(scene)==engine+0xc12bc){auto actor=*reinterpret_cast<BYTE**>(scene+0x1564);if(readable(actor,0x340)&&*reinterpret_cast<BYTE**>(actor)==engine+0xc11e4&&*reinterpret_cast<BYTE**>(actor+0x20)==scene){value.identifier=*reinterpret_cast<int*>(scene+0x10d0);auto position=reinterpret_cast<float*>(actor+0x154);value.x=position[0];value.y=position[1];value.z=position[2];value.timestamp=GetTickCount();value.valid=value.identifier>=0&&value.identifier<=9999&&std::isfinite(value.x)&&std::isfinite(value.y)&&std::isfinite(value.z);}}
 if(value.valid){
  auto actor=*reinterpret_cast<BYTE**>(scene+0x1564);auto heading=reinterpret_cast<float*>(actor+0x148);
  if(std::isfinite(heading[0])&&std::isfinite(heading[1])){value.directionX=heading[0];value.directionY=heading[1];}
  // The native proximity lookup walks scene+1594's list, whose head is +159c.
  // Its object getter reads +48/+4c/+50; IDs16a/168 are NPC/chest objects.
  if(readable(scene,0x15a0)){
   auto node=*reinterpret_cast<BYTE**>(scene+0x159c);BYTE* visited[256]{};unsigned nodes=0;
   while(node&&readable(node,8)&&nodes<256&&value.landmarkCount<64){
    bool cycle=false;for(unsigned i=0;i<nodes;++i)if(visited[i]==node){cycle=true;break;}if(cycle)break;visited[nodes++]=node;
    auto object=*reinterpret_cast<BYTE**>(node);
    if(readable(object,0xf4)&&!*reinterpret_cast<int*>(object+0xd4)){
     int type=*reinterpret_cast<int*>(object+4);auto p=reinterpret_cast<float*>(object+0x48);
     if((type==0x16a||type==0x168)&&std::isfinite(p[0])&&std::isfinite(p[1])&&std::isfinite(p[2])&&std::abs(p[0])<1e8&&std::abs(p[1])<1e8)
      value.landmarks[value.landmarkCount++]={*reinterpret_cast<int*>(object+0xf0),type==0x16a?1:2,p[0],p[1],p[2]};
    }
    node=*reinterpret_cast<BYTE**>(node+4);
   }
   value.landmarksTruncated=node!=nullptr;
  }
 }
 AcquireSRWLockExclusive(&snapshotLock);
 if(value.valid){
  bool reset=historyActor!=*reinterpret_cast<BYTE**>(scene+0x1564)||historyMap!=value.identifier;
  if(historyCount){auto p=history[historyCount-1];float dx=value.x-p.x,dy=value.y-p.y;reset|=dx*dx+dy*dy>40000;}
  if(reset){historyCount=0;historyActor=*reinterpret_cast<BYTE**>(scene+0x1564);historyMap=value.identifier;}
  bool append=!historyCount;if(historyCount){auto p=history[historyCount-1];float dx=value.x-p.x,dy=value.y-p.y;append=dx*dx+dy*dy>=16;}
  if(append){if(historyCount==128){memmove(history,history+1,127*sizeof(MapTrailPoint));--historyCount;}history[historyCount++]={value.x,value.y};}
  value.trailCount=historyCount;memcpy(value.trail,history,historyCount*sizeof(MapTrailPoint));
 }
 snapshot=value;ReleaseSRWLockExclusive(&snapshotLock);
 if(value.valid){startUi();static int reported=-1;if(reported!=value.identifier&&trace){wchar_t line[256];swprintf_s(line,L"MAP_OBSERVER_VALID map=%04d position=(%.3f,%.3f,%.3f) root_id_match=true",value.identifier,value.x,value.y,value.z);trace(line);reported=value.identifier;}}
}
MapSnapshot readMapSnapshot(){AcquireSRWLockShared(&snapshotLock);auto value=snapshot;ReleaseSRWLockShared(&snapshotLock);return value;}
bool installMapOverlay(HMODULE module,void(*logger)(const wchar_t*)){if(configured)return engine==reinterpret_cast<BYTE*>(module);engine=reinterpret_cast<BYTE*>(module);trace=logger;
 if(!GetEnvironmentVariableW(L"MC_MAP_ASSETS",assetDirectory,32768)||GetFileAttributesW(assetDirectory)==INVALID_FILE_ATTRIBUTES)return false;
 wchar_t path[32768];swprintf_s(path,L"%s\\label.txt",assetDirectory);HANDLE f=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
 if(f!=INVALID_HANDLE_VALUE){DWORD bytes=0;if(GetFileSize(f,nullptr)<sizeof(label)&&ReadFile(f,label,sizeof(label)-2,&bytes,nullptr)&&bytes%2==0)label[bytes/2]=0;CloseHandle(f);}
 swprintf_s(path,L"%s\\legend.txt",assetDirectory);f=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
 if(f!=INVALID_HANDLE_VALUE){DWORD bytes=0;if(GetFileSize(f,nullptr)<sizeof(legend)&&ReadFile(f,legend,sizeof(legend)-2,&bytes,nullptr)&&bytes%2==0)legend[bytes/2]=0;CloseHandle(f);}
 configured=true;
 if(trace)trace(L"MAP_OBSERVER_READY initial=off UI_start=deferred_to_valid_world_tick F8_large=enabled F9_mini=enabled geometry=first_frame landmarks=live_objects trail=session minimap=player_centered navigation_verified=false");return true;
}
void stopMapOverlay(){if(!uiThread){configured=false;InterlockedExchange(&uiStarted,0);engine=nullptr;return;}SetEvent(stopEvent);if(WaitForSingleObject(uiThread,2000)!=WAIT_OBJECT_0)return;CloseHandle(uiThread);CloseHandle(stopEvent);CloseHandle(initEvent);uiThread=stopEvent=initEvent=nullptr;configured=false;InterlockedExchange(&uiStarted,0);engine=nullptr;}
#ifdef MAP_OVERLAY_TEST
bool mapOverlayTestWait(){return initEvent&&WaitForSingleObject(initEvent,10000)==WAIT_OBJECT_0&&initStatus==0;}
bool mapOverlayTestClickThrough(){return overlayWindow&&SendMessageW(overlayWindow,WM_NCHITTEST,0,0)==HTTRANSPARENT&&SendMessageW(overlayWindow,WM_MOUSEACTIVATE,0,0)==MA_NOACTIVATE;}
bool mapOverlayTestHiddenWindow(){return uiThread&&overlayWindow&&IsWindow(overlayWindow)&&!IsWindowVisible(overlayWindow);}
void mapOverlayTestInitialize(BYTE* value){engine=value;}
bool mapOverlayTestRender(const wchar_t* assets,const wchar_t* output,bool mini){
 GdiplusStartupInput input;ULONG_PTR token=0;if(GdiplusStartup(&token,&input,nullptr)!=Ok)return false;
 wcscpy_s(assetDirectory,assets);canvas.player=readMapSnapshot();canvas.mini=mini;load(canvas.player.identifier);
 if(!canvas.image){GdiplusShutdown(token);return false;}
 HDC dc=CreateCompatibleDC(nullptr);BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=536;info.bmiHeader.biHeight=-584;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
 void* pixels=nullptr;HBITMAP bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,nullptr,0);auto old=SelectObject(dc,bitmap);renderCanvas(dc,536,584);
 UINT count=0,size=0;GetImageEncodersSize(&count,&size);std::unique_ptr<BYTE[]> bytes(new BYTE[size]);auto encoders=reinterpret_cast<ImageCodecInfo*>(bytes.get());GetImageEncoders(count,size,encoders);CLSID codec{};bool found=false;
 for(UINT i=0;i<count;++i)if(!wcscmp(encoders[i].MimeType,L"image/png")){codec=encoders[i].Clsid;found=true;break;}
 bool saved=false;{Bitmap image(bitmap,nullptr);saved=found&&image.Save(output,&codec,nullptr)==Ok;}
 SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);delete canvas.image;canvas.image=nullptr;GdiplusShutdown(token);return saved;
}
#endif
