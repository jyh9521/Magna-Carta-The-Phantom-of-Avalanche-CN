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
MapTrailPoint history[128]{};unsigned historyCount=0;BYTE* historyActor=nullptr;int historyMap=-1,historyField=-1;
HANDLE uiThread=nullptr,stopEvent=nullptr,initEvent=nullptr;DWORD uiThreadId=0;volatile LONG initStatus=-1,uiStarted=0;bool configured=false;HWND overlayWindow=nullptr;
wchar_t assetDirectory[32768]{};wchar_t label[256]=L"Terrain geometry";
wchar_t legend[256]=L"N NPC    B Box    P Player";
wchar_t hint[256]=L"F9: Mini > Full map > Off";int reportedMap=-1;
bool readable(const void* a,size_t n){auto p=reinterpret_cast<ULONG_PTR>(a),end=p+n;if(!p||end<p)return false;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;}
struct Canvas {MapMetadata metadata{};Bitmap* image=nullptr;MapSnapshot player;int loaded=-2,loadedField=-2;unsigned pointCount=0;MapExitPoint points[64]{};float scale=1;MapDisplayState display;};
Canvas canvas;
DWORD appearanceFlags(MapDisplayMode mode){return DWORD(LWA_ALPHA)|(mode==MapDisplayMode::Full?DWORD(LWA_COLORKEY):DWORD(0));}
bool applyAppearance(HWND window,MapDisplayMode mode){return SetLayeredWindowAttributes(window,RGB(19,32,39),mapOverlayOpacity(mode),appearanceFlags(mode))!=FALSE;}
void readLabel(const wchar_t* name,wchar_t* text,DWORD characters){
 wchar_t path[32768];swprintf_s(path,L"%s\\%s",assetDirectory,name);HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
 if(file!=INVALID_HANDLE_VALUE){DWORD bytes=0;if(GetFileSize(file,nullptr)<characters*sizeof(wchar_t)&&ReadFile(file,text,(characters-1)*sizeof(wchar_t),&bytes,nullptr)&&bytes%sizeof(wchar_t)==0)text[bytes/sizeof(wchar_t)]=0;CloseHandle(file);}
}
void readLabels(){readLabel(L"label.txt",label,256);readLabel(L"legend.txt",legend,256);readLabel(L"hint.txt",hint,256);}
unsigned mapCycles(bool active){
#ifdef MAP_OVERLAY_TEST
 (void)active;return 0;
#else
 return modernGamepadConsumeMapCycles(active);
#endif
}
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
 canvas.loaded=identifier;canvas.loadedField=-2;canvas.pointCount=0;delete canvas.image;canvas.image=nullptr;wchar_t path[32768];swprintf_s(path,L"%s\\%04d.map",assetDirectory,identifier);
 HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(file==INVALID_HANDLE_VALUE){if(trace)trace(L"MAP_OVERLAY_ASSET_UNAVAILABLE version_or_coverage=unsupported");return;}
 DWORD count=0;bool ok=GetFileSize(file,nullptr)==sizeof(MapMetadata)&&ReadFile(file,&canvas.metadata,sizeof(MapMetadata),&count,nullptr)&&count==sizeof(MapMetadata);CloseHandle(file);
 if(!ok||!mapMetadataValid(canvas.metadata))return;
 swprintf_s(path,L"%s\\%04d.png",assetDirectory,identifier);auto image=std::make_unique<Bitmap>(path);
 if(image->GetLastStatus()!=Ok||image->GetWidth()!=canvas.metadata.width||image->GetHeight()!=canvas.metadata.height)return;
 canvas.image=image.release();if(trace)trace(L"MAP_OVERLAY_ASSET_LOADED projection=first_frame geometry_only=true");
}
void loadPoints(int fieldIdentifier,int mapIdentifier){
 canvas.loadedField=fieldIdentifier;canvas.pointCount=0;
 if(fieldIdentifier<0||fieldIdentifier>9999||mapIdentifier<0||mapIdentifier>9999)return;
 wchar_t path[32768];swprintf_s(path,L"%s\\points\\%04d.poi",assetDirectory,fieldIdentifier);
 HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(file==INVALID_HANDLE_VALUE)return;
 BYTE bytes[sizeof(MapPointHeader)+64*sizeof(MapExitPoint)]{};DWORD size=GetFileSize(file,nullptr),read=0;
 bool ok=size>=sizeof(MapPointHeader)&&size<=sizeof(bytes)&&ReadFile(file,bytes,size,&read,nullptr)&&read==size;CloseHandle(file);
 MapPointHeader header{};MapExitPoint points[64]{};
 if(ok){memcpy(&header,bytes,sizeof(header));memcpy(points,bytes+sizeof(header),size-sizeof(header));ok=mapPointAssetValid(header,points,size,fieldIdentifier,mapIdentifier);}
 if(!ok){if(trace)trace(L"MAP_POINTS_REJECTED field_or_map_or_payload_mismatch=true");return;}
 canvas.pointCount=header.count;memcpy(canvas.points,points,header.count*sizeof(MapExitPoint));
 if(trace){wchar_t line[160];swprintf_s(line,L"MAP_POINTS_LOADED field=%04d map=%04d exits=%u conditions_evaluated=false",fieldIdentifier,mapIdentifier,header.count);trace(line);}
}
void renderCanvas(HDC target,int width,int height){
 HDC dc=CreateCompatibleDC(target);HBITMAP buffer=CreateCompatibleBitmap(target,std::max(width,1),std::max(height,1));auto old=SelectObject(dc,buffer);
 {
 Graphics graphics(dc);graphics.Clear(Color(255,19,32,39));graphics.SetSmoothingMode(SmoothingModeAntiAlias);
 if(canvas.image){int size=std::max(1,std::min(width-int(24*canvas.scale),height-int(84*canvas.scale)));int x=(width-size)/2,y=int(36*canvas.scale);MapView view;
  if(mapView(canvas.metadata,canvas.player.x,canvas.player.y,canvas.display.mode==MapDisplayMode::Mini,view)){
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
    float radius=5*canvas.scale;SolidBrush brush(m.kind==1?Color(255,75,220,110):Color(255,181,114,235));
    if(m.kind==1){graphics.FillEllipse(&brush,px-radius,py-radius,2*radius,2*radius);if(m.collectible==MapCollectibleState::NpcReward){Pen reward(Color(255,245,213,106),2*canvas.scale);float r=8*canvas.scale;graphics.DrawEllipse(&reward,px-r,py-r,2*r,2*r);}}
    else if(m.collectible==MapCollectibleState::ContainerAvailable)graphics.FillRectangle(&brush,px-radius,py-radius,2*radius,2*radius);
    else{Pen uncertain(Color(255,181,114,235),2*canvas.scale);graphics.DrawRectangle(&uncertain,px-radius,py-radius,2*radius,2*radius);}
   }
   for(unsigned i=0;i<canvas.pointCount;++i){const auto& exit=canvas.points[i];float px=0,py=0;if(!mapExitApplies(exit,canvas.player)||!point(exit.x,exit.y,px,py))continue;
    float r=7*canvas.scale;PointF diamond[]={{px,py-r},{px+r,py},{px,py+r},{px-r,py}};Color color(255,75,205,244);
    if(exit.flags){Pen outline(color,2*canvas.scale);graphics.DrawPolygon(&outline,diamond,4);}else{SolidBrush fill(color);graphics.FillPolygon(&fill,diamond,4);}
   }
   float px=0,py=0;if(point(canvas.player.x,canvas.player.y,px,py)){
    SolidBrush player(Color(255,255,166,35));float dx=0,dy=0,r=8*canvas.scale;
    if(mapPlayerHeading(canvas.player.directionX,canvas.player.directionY,dx,dy)){PointF arrow[]={{px+dx*r,py+dy*r},{px-dx*r*.7f-dy*r*.7f,py-dy*r*.7f+dx*r*.7f},{px-dx*r*.7f+dy*r*.7f,py-dy*r*.7f-dx*r*.7f}};graphics.FillPolygon(&player,arrow,3);}
    else graphics.FillEllipse(&player,px-r*.6f,py-r*.6f,r*1.2f,r*1.2f);
   }
   graphics.ResetClip();
  }
 }
 }
 SetBkMode(dc,TRANSPARENT);SetTextColor(dc,RGB(235,221,182));HFONT font=CreateFontW(-int(18*canvas.scale),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,L"Segoe UI");auto oldFont=SelectObject(dc,font);
 wchar_t title[320];swprintf_s(title,L"%s  %04d",label,canvas.player.identifier);TextOutW(dc,int(12*canvas.scale),int(9*canvas.scale),title,static_cast<int>(wcslen(title)));SelectObject(dc,oldFont);DeleteObject(font);
 font=CreateFontW(-int(14*canvas.scale),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,L"Segoe UI");oldFont=SelectObject(dc,font);
 if(canvas.display.mode==MapDisplayMode::Full){RECT hintRect={width/2,int(9*canvas.scale),width-int(12*canvas.scale),int(31*canvas.scale)};DrawTextW(dc,hint,-1,&hintRect,DT_RIGHT|DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);}
 RECT legendRect={int(12*canvas.scale),height-int(42*canvas.scale),width-int(12*canvas.scale),height-int(23*canvas.scale)};
 DrawTextW(dc,legend,-1,&legendRect,DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
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
  if(!active){mapCycles(false);mapDisplayStep(canvas.display,false,false);ShowWindow(window,SW_HIDE);return 0;}
  unsigned pad=mapPad();bool pressed=(pad&2)!=0;
  auto previousMode=canvas.display.mode;auto mode=mapDisplayStep(canvas.display,true,pressed);
  for(unsigned count=mapCycles(true);count;--count)mode=mapDisplayCycle(canvas.display);
  if(mode!=previousMode&&trace)trace(mode==MapDisplayMode::Mini?L"MAP_OVERLAY_MODE mini":mode==MapDisplayMode::Full?L"MAP_OVERLAY_MODE full client_translucent=true":L"MAP_OVERLAY_MODE off");
  canvas.player=current;if(canvas.loaded!=current.identifier)load(current.identifier);if(canvas.loadedField!=current.fieldIdentifier)loadPoints(current.fieldIdentifier,current.identifier);
  if(!canvas.image||mode==MapDisplayMode::Off){ShowWindow(window,SW_HIDE);return 0;}
  RECT client{};GetClientRect(game,&client);POINT origin{};ClientToScreen(game,&origin);
  MapOverlayLayout layout;if(!mapOverlayLayout(client.right,client.bottom,mode,layout)){ShowWindow(window,SW_HIDE);return 0;}
  canvas.scale=layout.scale;if(!applyAppearance(window,mode)){ShowWindow(window,SW_HIDE);return 0;}
  SetWindowPos(window,HWND_TOPMOST,origin.x+layout.x,origin.y+layout.y,layout.width,layout.height,SWP_NOACTIVATE|SWP_SHOWWINDOW);InvalidateRect(window,nullptr,FALSE);return 0;
 }
 if(message==WM_DESTROY){PostQuitMessage(0);return 0;}
 return DefWindowProcW(window,message,w,l);
}
DWORD WINAPI threadMain(void*){
 GdiplusStartupInput input;ULONG_PTR token=0;if(GdiplusStartup(&token,&input,nullptr)!=Ok){InterlockedExchange(&initStatus,1);SetEvent(initEvent);return 1;}
 WNDCLASSW cls{};cls.lpfnWndProc=windowProc;cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"MagnaCartaTerrainOverlay";
 if(!RegisterClassW(&cls)){InterlockedExchange(&initStatus,2);SetEvent(initEvent);GdiplusShutdown(token);return 2;}
 HWND window=CreateWindowExW(WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW|WS_EX_LAYERED|WS_EX_TRANSPARENT,cls.lpszClassName,L"",WS_POPUP,0,0,320,356,nullptr,nullptr,cls.hInstance,nullptr);
 bool ready=window&&applyAppearance(window,MapDisplayMode::Mini)&&SetTimer(window,1,33,nullptr)!=0;
 overlayWindow=ready?window:nullptr;InterlockedExchange(&initStatus,ready?0:3);SetEvent(initEvent);if(trace)trace(ready?L"MAP_OVERLAY_WINDOW_READY initial=hidden no_activation=true":L"MAP_OVERLAY_WINDOW_FAILED reason=window_or_timer_creation");
 if(ready){MSG message{};while(GetMessageW(&message,nullptr,0,0)>0){TranslateMessage(&message);DispatchMessageW(&message);}}
 else if(window)DestroyWindow(window);
 delete canvas.image;canvas.image=nullptr;canvas.loaded=-2;canvas.display={};overlayWindow=nullptr;UnregisterClassW(cls.lpszClassName,cls.hInstance);GdiplusShutdown(token);return ready?0:3;
}
}
static_assert(sizeof(MapMetadata)==40,"MCM1 metadata layout");
static_assert(sizeof(MapPointHeader)==16&&sizeof(MapExitPoint)==36,"MCP1 point layout");
bool mapPointAssetValid(const MapPointHeader& h,const MapExitPoint* points,size_t bytes,int fieldIdentifier,int mapIdentifier){
 if(fieldIdentifier<0||fieldIdentifier>9999||mapIdentifier<0||mapIdentifier>9999||memcmp(h.magic,"MCP1",4)||h.fieldIdentifier!=unsigned(fieldIdentifier)||h.mapIdentifier!=unsigned(mapIdentifier)||h.count>64||bytes!=sizeof(h)+h.count*sizeof(MapExitPoint)||(h.count&&!points))return false;
 for(unsigned i=0;i<h.count;++i){const auto& p=points[i];if(p.eventIndex<0||p.regionId<0||p.targetField<0||p.targetField>9999||p.targetMap< -1||p.targetMap>9999||p.triggerActor<0||p.triggerActor>9999||p.flags>3||!std::isfinite(p.x)||!std::isfinite(p.y)||!std::isfinite(p.z)||std::abs(p.x)>=1e8||std::abs(p.y)>=1e8||std::abs(p.z)>=1e8)return false;}return true;
}
bool mapExitApplies(const MapExitPoint& point,const MapSnapshot& player){return player.valid&&player.actorIdentifier>=0&&player.actorIdentifier<=9999&&point.triggerActor==player.actorIdentifier;}
bool mapMetadataValid(const MapMetadata& m){if(memcmp(m.magic,"MCM1",4)||m.width<128||m.width>2048||m.width!=m.height)return false;for(float f:m.bounds)if(!std::isfinite(f))return false;return m.bounds[2]>m.bounds[0]&&m.bounds[3]>m.bounds[1]&&std::isfinite(m.origin[0])&&std::isfinite(m.origin[1])&&std::isfinite(m.scale)&&m.scale>0;}
bool mapPixel(const MapMetadata& m,float x,float y,float& px,float& py){if(!mapMetadataValid(m)||!std::isfinite(x)||!std::isfinite(y))return false;px=m.origin[0]+(x-m.bounds[0])*m.scale;py=m.height-m.origin[1]-(y-m.bounds[1])*m.scale;return std::isfinite(px)&&std::isfinite(py);}
bool mapView(const MapMetadata& m,float x,float y,bool mini,MapView& v){float px=0,py=0;if(!mapPixel(m,x,y,px,py))return false;v={0,0,float(m.width)};if(mini){v.span=std::clamp(m.scale*240.f,16.f,float(m.width));v.left=px-v.span/2;v.top=py-v.span/2;}return true;}
bool mapViewPoint(const MapMetadata& m,const MapView& v,float x,float y,float size,float& px,float& py){if(!std::isfinite(v.span)||v.span<=0||!std::isfinite(v.left)||!std::isfinite(v.top)||!std::isfinite(size)||size<=0||!mapPixel(m,x,y,px,py))return false;px=(px-v.left)*size/v.span;py=(py-v.top)*size/v.span;return std::isfinite(px)&&std::isfinite(py);}
bool mapPlayerHeading(float worldX,float worldY,float& screenX,float& screenY){
 screenX=screenY=0;float length=std::hypot(worldX,worldY);if(!std::isfinite(worldX)||!std::isfinite(worldY)||!std::isfinite(length)||length<=.001f)return false;
 screenX=worldX/length;screenY=-worldY/length;return true;
}
MapDisplayMode mapDisplayStep(MapDisplayState& state,bool active,bool pressed){
 if(!active){state.held=true;return MapDisplayMode::Off;}
 if(pressed&&!state.held)mapDisplayCycle(state);
 state.held=pressed;return state.mode;
}
MapDisplayMode mapDisplayCycle(MapDisplayState& state){switch(state.mode){case MapDisplayMode::Off:state.mode=MapDisplayMode::Mini;break;case MapDisplayMode::Mini:state.mode=MapDisplayMode::Full;break;case MapDisplayMode::Full:state.mode=MapDisplayMode::Off;break;}return state.mode;}
bool mapOverlayLayout(int clientWidth,int clientHeight,MapDisplayMode mode,MapOverlayLayout& layout){
 layout={};if(clientWidth<128||clientHeight<128||mode==MapDisplayMode::Off)return false;
 layout.scale=std::clamp(float(clientHeight)/1080.f,.75f,2.f);
 if(mode==MapDisplayMode::Full){layout.width=clientWidth;layout.height=clientHeight;return true;}
 layout.x=layout.y=std::min(24,std::min(clientWidth,clientHeight)/16);
 layout.width=std::min(int(320*layout.scale),clientWidth/3);
 layout.height=std::min(layout.width+int(36*layout.scale),clientHeight-layout.y);
 return layout.width>0&&layout.height>0;
}
BYTE mapOverlayOpacity(MapDisplayMode mode){return mode==MapDisplayMode::Full?BYTE(150):BYTE(235);}
void observeMapWorld(BYTE* scene,bool controlled){MapSnapshot value;
 bool sameMap=false;
 if(engine&&readable(scene,0x1568)){
  auto level=*reinterpret_cast<BYTE**>(scene+0x1558);
  if(readable(level,0x10c)&&*reinterpret_cast<BYTE**>(level)==engine+0xc15ac){auto brush=*reinterpret_cast<BYTE**>(level+0xf0);
   if(readable(brush,0x128)&&*reinterpret_cast<BYTE**>(brush)==engine+0xbdcec){auto info=*reinterpret_cast<BYTE**>(brush+0x124);sameMap=readable(info,4)&&*reinterpret_cast<int*>(info)==*reinterpret_cast<int*>(scene+0x10d0);}}
 }
 if(sameMap&&controlled&&engine&&readable(scene,0x1568)&&*reinterpret_cast<BYTE**>(scene)==engine+0xc12bc){auto actor=*reinterpret_cast<BYTE**>(scene+0x1564);if(readable(actor,0x340)&&*reinterpret_cast<BYTE**>(actor)==engine+0xc11e4&&*reinterpret_cast<BYTE**>(actor+0x20)==scene){value.identifier=*reinterpret_cast<int*>(scene+0x10d0);auto position=reinterpret_cast<float*>(actor+0x154);value.x=position[0];value.y=position[1];value.z=position[2];value.timestamp=GetTickCount();value.valid=value.identifier>=0&&value.identifier<=9999&&std::isfinite(value.x)&&std::isfinite(value.y)&&std::isfinite(value.z);}}
 if(value.valid){
  int field=*reinterpret_cast<int*>(scene+0x10cc);value.fieldIdentifier=(field>=0&&field<=9999)?field:-1;
  auto actor=*reinterpret_cast<BYTE**>(scene+0x1564);auto heading=reinterpret_cast<float*>(actor+0x148);
  int actorId=*reinterpret_cast<int*>(actor+0x328);value.actorIdentifier=(actorId>=0&&actorId<=9999)?actorId:-1;
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
     if((type==0x16a||type==0x168)&&std::isfinite(p[0])&&std::isfinite(p[1])&&std::isfinite(p[2])&&std::abs(p[0])<1e8&&std::abs(p[1])<1e8){
      int id=*reinterpret_cast<int*>(object+0xf0);auto collectible=classifyMapCollectible(engine,scene,id,type);
      if(type!=0x168||collectible!=MapCollectibleState::ContainerConsumed)value.landmarks[value.landmarkCount++]={id,type==0x16a?1:2,p[0],p[1],p[2],collectible};
     }
    }
    node=*reinterpret_cast<BYTE**>(node+4);
   }
   value.landmarksTruncated=node!=nullptr;
  }
 }
 AcquireSRWLockExclusive(&snapshotLock);
 if(value.valid){
  bool reset=historyActor!=*reinterpret_cast<BYTE**>(scene+0x1564)||historyMap!=value.identifier||historyField!=value.fieldIdentifier;
  if(historyCount){auto p=history[historyCount-1];float dx=value.x-p.x,dy=value.y-p.y;reset|=dx*dx+dy*dy>40000;}
  if(reset){historyCount=0;historyActor=*reinterpret_cast<BYTE**>(scene+0x1564);historyMap=value.identifier;historyField=value.fieldIdentifier;}
  bool append=!historyCount;if(historyCount){auto p=history[historyCount-1];float dx=value.x-p.x,dy=value.y-p.y;append=dx*dx+dy*dy>=16;}
  if(append){if(historyCount==128){memmove(history,history+1,127*sizeof(MapTrailPoint));--historyCount;}history[historyCount++]={value.x,value.y};}
  value.trailCount=historyCount;memcpy(value.trail,history,historyCount*sizeof(MapTrailPoint));
 }
 snapshot=value;ReleaseSRWLockExclusive(&snapshotLock);
#ifndef MAP_OVERLAY_TEST
 modernGamepadMapContext(scene,(unsigned(value.identifier)<<16)|(unsigned(value.fieldIdentifier)&0xffffu),value.valid);
#endif
 if(value.valid){startUi();if(reportedMap!=value.identifier&&trace){wchar_t line[256];swprintf_s(line,L"MAP_OBSERVER_VALID map=%04d position=(%.3f,%.3f,%.3f) root_id_match=true",value.identifier,value.x,value.y,value.z);trace(line);reportedMap=value.identifier;}}
}
MapSnapshot readMapSnapshot(){AcquireSRWLockShared(&snapshotLock);auto value=snapshot;ReleaseSRWLockShared(&snapshotLock);return value;}
bool installMapOverlay(HMODULE module,void(*logger)(const wchar_t*)){if(configured)return engine==reinterpret_cast<BYTE*>(module);engine=reinterpret_cast<BYTE*>(module);trace=logger;
 if(!GetEnvironmentVariableW(L"MC_MAP_ASSETS",assetDirectory,32768)||GetFileAttributesW(assetDirectory)==INVALID_FILE_ATTRIBUTES)return false;
 readLabels();
 configured=true;
 if(trace)trace(L"MAP_OBSERVER_READY MAP_F9_CYCLE_V1 initial=off UI_start=deferred_to_valid_world_tick F9_cycle=off_mini_full_off F8=preserved full=client_translucent geometry=first_frame landmarks=live_objects trail=session minimap=player_centered navigation_verified=false");return true;
}
void stopMapOverlay(){
 if(uiThread){SetEvent(stopEvent);if(WaitForSingleObject(uiThread,2000)!=WAIT_OBJECT_0)return;CloseHandle(uiThread);CloseHandle(stopEvent);CloseHandle(initEvent);uiThread=stopEvent=initEvent=nullptr;}
 configured=false;InterlockedExchange(&uiStarted,0);engine=nullptr;trace=nullptr;canvas.display={};canvas.loaded=canvas.loadedField=-2;canvas.pointCount=0;reportedMap=-1;
 AcquireSRWLockExclusive(&snapshotLock);snapshot={};historyCount=0;historyActor=nullptr;historyMap=historyField=-1;ReleaseSRWLockExclusive(&snapshotLock);
 wcscpy_s(label,L"Terrain geometry");wcscpy_s(legend,L"N NPC    B Box    P Player");wcscpy_s(hint,L"F9: Mini > Full map > Off");assetDirectory[0]=0;
#ifndef MAP_OVERLAY_TEST
 modernGamepadMapContext(nullptr,0,false);
#endif
}
#ifdef MAP_OVERLAY_TEST
bool mapOverlayTestWait(){return initEvent&&WaitForSingleObject(initEvent,10000)==WAIT_OBJECT_0&&initStatus==0;}
bool mapOverlayTestClickThrough(){return overlayWindow&&SendMessageW(overlayWindow,WM_NCHITTEST,0,0)==HTTRANSPARENT&&SendMessageW(overlayWindow,WM_MOUSEACTIVATE,0,0)==MA_NOACTIVATE;}
bool mapOverlayTestWindowAppearance(MapDisplayMode mode){
 COLORREF key=0;BYTE alpha=0;DWORD flags=0;
 return overlayWindow&&applyAppearance(overlayWindow,mode)&&GetLayeredWindowAttributes(overlayWindow,&key,&alpha,&flags)&&(mode!=MapDisplayMode::Full||key==RGB(19,32,39))&&alpha==mapOverlayOpacity(mode)&&flags==appearanceFlags(mode);
}
bool mapOverlayTestResetState(){return !configured&&!uiThread&&!overlayWindow&&canvas.display.mode==MapDisplayMode::Off&&!readMapSnapshot().valid&&historyCount==0;}
unsigned mapOverlayTestLoadPoints(const wchar_t* assets,int fieldIdentifier,int mapIdentifier){wcscpy_s(assetDirectory,assets);loadPoints(fieldIdentifier,mapIdentifier);return canvas.pointCount;}
MapExitPoint mapOverlayTestPoint(unsigned index){return index<canvas.pointCount?canvas.points[index]:MapExitPoint{};}
bool mapOverlayTestHiddenWindow(){return uiThread&&overlayWindow&&IsWindow(overlayWindow)&&!IsWindowVisible(overlayWindow);}
void mapOverlayTestInitialize(BYTE* value){engine=value;}
bool mapOverlayTestRender(const wchar_t* assets,const wchar_t* output,bool mini){
 return mapOverlayTestRenderMode(assets,output,mini?MapDisplayMode::Mini:MapDisplayMode::Full,536,584,false);
}
bool mapOverlayTestRenderMode(const wchar_t* assets,const wchar_t* output,MapDisplayMode mode,int width,int height,bool encodeTransparency){
 if(mode==MapDisplayMode::Off||width<128||height<128||width>8192||height>8192)return false;
 GdiplusStartupInput input;ULONG_PTR token=0;if(GdiplusStartup(&token,&input,nullptr)!=Ok)return false;
 wcscpy_s(assetDirectory,assets);readLabels();canvas.player=readMapSnapshot();canvas.display.mode=mode;canvas.scale=1;load(canvas.player.identifier);loadPoints(canvas.player.fieldIdentifier,canvas.player.identifier);
 if(!canvas.image){GdiplusShutdown(token);return false;}
 HDC dc=CreateCompatibleDC(nullptr);BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=width;info.bmiHeader.biHeight=-height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
 void* pixels=nullptr;HBITMAP bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,nullptr,0);auto old=SelectObject(dc,bitmap);renderCanvas(dc,width,height);GdiFlush();
 UINT count=0,size=0;GetImageEncodersSize(&count,&size);std::unique_ptr<BYTE[]> bytes(new BYTE[size]);auto encoders=reinterpret_cast<ImageCodecInfo*>(bytes.get());GetImageEncoders(count,size,encoders);CLSID codec{};bool found=false;
 for(UINT i=0;i<count;++i)if(!wcscmp(encoders[i].MimeType,L"image/png")){codec=encoders[i].Clsid;found=true;break;}
 bool saved=false;
 if(mode==MapDisplayMode::Full&&encodeTransparency){
  // Encode the same color-key/constant-alpha policy in the offline full-view PNG.
  // This verifies the owned canvas, not desktop/game compositor acceptance.
  Bitmap image(width,height,PixelFormat32bppARGB);BitmapData data{};Rect rect(0,0,width,height);
  if(image.LockBits(&rect,ImageLockModeWrite,PixelFormat32bppARGB,&data)==Ok){
   auto source=static_cast<const BYTE*>(pixels);
   for(int row=0;row<height;++row){auto destination=static_cast<BYTE*>(data.Scan0)+row*data.Stride;for(int col=0;col<width;++col){auto p=source+(row*width+col)*4;auto q=destination+col*4;q[0]=p[0];q[1]=p[1];q[2]=p[2];q[3]=(p[0]==39&&p[1]==32&&p[2]==19)?0:mapOverlayOpacity(mode);}}
   image.UnlockBits(&data);saved=found&&image.Save(output,&codec,nullptr)==Ok;
  }
 }else{Bitmap image(bitmap,nullptr);saved=found&&image.Save(output,&codec,nullptr)==Ok;}
 SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);delete canvas.image;canvas.image=nullptr;GdiplusShutdown(token);return saved;
}
#endif
