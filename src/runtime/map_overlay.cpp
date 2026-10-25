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
bool configured=false;ULONG_PTR gdipToken=0;
wchar_t assetDirectory[32768]{};wchar_t label[256]=L"Area map";
wchar_t legend[256]=L"N NPC    B Box    P Player";
wchar_t hint[256]=L"F9: Mini > Full map > Off";int reportedMap=-1;
bool readable(const void* a,size_t n){auto p=reinterpret_cast<ULONG_PTR>(a),end=p+n;if(!p||end<p)return false;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;}
struct Surface {
 HDC dc=nullptr;HBITMAP bitmap=nullptr;HGDIOBJ old=nullptr;DWORD* pixels=nullptr;int width=0,height=0;
 ~Surface(){clear();}
 void clear(){if(dc){if(old)SelectObject(dc,old);if(bitmap)DeleteObject(bitmap);DeleteDC(dc);}dc=nullptr;bitmap=nullptr;old=nullptr;pixels=nullptr;width=height=0;}
 bool resize(int w,int h){if(dc&&width==w&&height==h)return true;if(w<1||h<1||w>8192||h>8192||size_t(w)*h>16777216)return false;clear();
  BITMAPINFO i{};i.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);i.bmiHeader.biWidth=w;i.bmiHeader.biHeight=-h;i.bmiHeader.biPlanes=1;i.bmiHeader.biBitCount=32;i.bmiHeader.biCompression=BI_RGB;
  dc=CreateCompatibleDC(nullptr);if(!dc)return false;bitmap=CreateDIBSection(dc,&i,DIB_RGB_COLORS,reinterpret_cast<void**>(&pixels),nullptr,0);if(!bitmap){clear();return false;}old=SelectObject(dc,bitmap);width=w;height=h;return true;
 }
};
struct Canvas {MapMetadata metadata{};Bitmap* image=nullptr;MapSnapshot player;int loaded=-2,loadedField=-2;unsigned pointCount=0;MapExitPoint points[64]{};float scale=1;MapDisplayState display;};
Canvas canvas;Surface terrainSurface,frameSurface,alphaSurface;
MapView cachedView{};MapSnapshot paintedPlayer{};MapDisplayMode cachedMode=MapDisplayMode::Off;
float cachedScale=0;bool terrainValid=false,frameValid=false;unsigned terrainBuilds=0,frameBuilds=0;
DWORD lastFrameAt=0;bool wasActive=false;
void clearMapCanvas(){delete canvas.image;canvas.image=nullptr;terrainSurface.clear();frameSurface.clear();alphaSurface.clear();terrainValid=frameValid=false;cachedMode=MapDisplayMode::Off;lastFrameAt=0;wasActive=false;}
void readLabel(const wchar_t* name,wchar_t* text,DWORD characters){
 wchar_t path[32768];swprintf_s(path,L"%s\\%s",assetDirectory,name);HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
 if(file!=INVALID_HANDLE_VALUE){DWORD bytes=0;if(GetFileSize(file,nullptr)<characters*sizeof(wchar_t)&&ReadFile(file,text,(characters-1)*sizeof(wchar_t),&bytes,nullptr)&&bytes%sizeof(wchar_t)==0)text[bytes/sizeof(wchar_t)]=0;CloseHandle(file);}
}
void readLabels(){readLabel(L"label.txt",label,256);readLabel(L"legend.txt",legend,256);readLabel(L"hint.txt",hint,256);terrainValid=frameValid=false;}
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
void load(int identifier){
 canvas.loaded=identifier;canvas.loadedField=-2;canvas.pointCount=0;delete canvas.image;canvas.image=nullptr;terrainValid=frameValid=false;wchar_t path[32768];swprintf_s(path,L"%s\\%04d.map",assetDirectory,identifier);
 HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(file==INVALID_HANDLE_VALUE){if(trace)trace(L"MAP_OVERLAY_ASSET_UNAVAILABLE version_or_coverage=unsupported");return;}
 DWORD count=0;bool ok=GetFileSize(file,nullptr)==sizeof(MapMetadata)&&ReadFile(file,&canvas.metadata,sizeof(MapMetadata),&count,nullptr)&&count==sizeof(MapMetadata);CloseHandle(file);
 if(!ok||!mapMetadataValid(canvas.metadata))return;
 swprintf_s(path,L"%s\\%04d.png",assetDirectory,identifier);Bitmap source(path);
 if(source.GetLastStatus()!=Ok||source.GetWidth()!=canvas.metadata.width||source.GetHeight()!=canvas.metadata.height)return;
 // Remove only the atlas background, then tint lines to the game's bronze palette.
 auto image=std::make_unique<Bitmap>(source.GetWidth(),source.GetHeight(),PixelFormat32bppARGB);
 BitmapData in{},out{};Rect rect(0,0,source.GetWidth(),source.GetHeight());
 if(source.LockBits(&rect,ImageLockModeRead,PixelFormat32bppARGB,&in)!=Ok)return;
 if(image->LockBits(&rect,ImageLockModeWrite,PixelFormat32bppARGB,&out)!=Ok){source.UnlockBits(&in);return;}
 for(int y=0;y<rect.Height;++y){auto a=reinterpret_cast<BYTE*>(in.Scan0)+y*in.Stride;auto b=reinterpret_cast<BYTE*>(out.Scan0)+y*out.Stride;
  for(int x=0;x<rect.Width;++x){auto p=a+x*4;auto q=b+x*4;int light=std::max({int(p[0])-39,int(p[1])-32,int(p[2])-19});q[0]=125;q[1]=183;q[2]=211;q[3]=BYTE(std::clamp(light*255/179,0,255));}}
 image->UnlockBits(&out);source.UnlockBits(&in);canvas.image=image.release();
 if(trace)trace(L"MAP_OVERLAY_ASSET_LOADED projection=first_frame palette=bronze geometry_only=true");
}
void loadPoints(int fieldIdentifier,int mapIdentifier){
 canvas.loadedField=fieldIdentifier;canvas.pointCount=0;frameValid=false;
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

struct Plot {int x,y,size;};
Plot plot(int w,int h){int pad=std::max(6,int(10*canvas.scale));int size=std::max(1,std::min(w-2*pad,h-2*pad));return {(w-size)/2,(h-size)/2,size};}
void bezel(Graphics& g,int width,int height){
 float s=canvas.scale,p=std::max(1.f,2*s),c=std::max(6.f,10*s),w=float(width),h=float(height);
 PointF pts[]={{c,p},{w-c,p},{w-p,c},{w-p,h-c},{w-c,h-p},{c,h-p},{p,h-c},{p,c}};
 SolidBrush fill(Color(255,25,24,20));g.FillPolygon(&fill,pts,8);
 Pen rim(Color(255,125,78,38),std::max(1.f,2*s));g.DrawPolygon(&rim,pts,8);
 Pen gold(Color(230,203,161,89),std::max(1.f,s));g.DrawLine(&gold,c+2*s,p+3*s,w-c-2*s,p+3*s);g.DrawLine(&gold,c+2*s,h-p-3*s,w-c-2*s,h-p-3*s);
 for(auto q:{PointF(c,c),PointF(w-c,c),PointF(c,h-c),PointF(w-c,h-c)}){PointF d[]={{q.X,q.Y-3*s},{q.X+3*s,q.Y},{q.X,q.Y+3*s},{q.X-3*s,q.Y}};SolidBrush b(Color(255,172,117,56));g.FillPolygon(&b,d,4);}
}
bool composeCanvas(int width,int height){
 const bool resized=terrainSurface.width!=width||terrainSurface.height!=height;
 if(!canvas.image||!terrainSurface.resize(width,height)||!frameSurface.resize(width,height))return false;
 MapView view;if(!mapView(canvas.metadata,canvas.player.x,canvas.player.y,canvas.display.mode==MapDisplayMode::Mini,view))return false;
 Plot area=plot(width,height);const int x=area.x,y=area.y,size=area.size;
 bool rebuild=resized||!terrainValid||cachedMode!=canvas.display.mode||cachedScale!=canvas.scale||memcmp(&cachedView,&view,sizeof(view));
 if(rebuild){
  Graphics g(terrainSurface.dc);g.Clear(Color(255,19,32,39));g.SetSmoothingMode(SmoothingModeAntiAlias);
  if(canvas.display.mode==MapDisplayMode::Mini)bezel(g,width,height);
  g.SetClip(Rect(x,y,size,size));g.SetInterpolationMode(InterpolationModeBilinear);g.SetPixelOffsetMode(PixelOffsetModeHalf);
  // Explicit source crop avoids scaling the entire 2048px atlas beyond the clip.
  g.DrawImage(canvas.image,RectF(REAL(x),REAL(y),REAL(size),REAL(size)),view.left,view.top,view.span,view.span,UnitPixel);
  g.ResetClip();g.Flush(FlushIntentionSync);
  cachedMode=canvas.display.mode;cachedScale=canvas.scale;cachedView=view;terrainValid=true;frameValid=false;++terrainBuilds;
 }
 MapSnapshot comparable=canvas.player;comparable.timestamp=0;
 if(frameValid&&!memcmp(&paintedPlayer,&comparable,sizeof(comparable)))return true;
 GdiFlush();memcpy(frameSurface.pixels,terrainSurface.pixels,size_t(width)*height*4);
 {Graphics graphics(frameSurface.dc);graphics.SetSmoothingMode(SmoothingModeAntiAlias);graphics.SetClip(Rect(x,y,size,size));
  auto point=[&](float wx,float wy,float& px,float& py){if(!mapViewPoint(canvas.metadata,view,wx,wy,float(size),px,py))return false;px+=x;py+=y;return true;};
   const float markerScale=std::max(.6f,std::min(canvas.scale,float(size)/400.f));
   Pen trail(Color(120,181,145,76),std::max(1.f,1.2f*markerScale));
   for(unsigned i=1;i<canvas.player.trailCount;++i){float ax=0,ay=0,bx=0,by=0;if(point(canvas.player.trail[i-1].x,canvas.player.trail[i-1].y,ax,ay)&&point(canvas.player.trail[i].x,canvas.player.trail[i].y,bx,by))graphics.DrawLine(&trail,ax,ay,bx,by);}
   for(unsigned i=0;i<canvas.player.landmarkCount;++i){auto m=canvas.player.landmarks[i];float px=0,py=0;if(!point(m.x,m.y,px,py))continue;
    float radius=5*markerScale;SolidBrush brush(m.kind==1?Color(255,75,220,110):Color(255,181,114,235));
    if(m.kind==1){graphics.FillEllipse(&brush,px-radius,py-radius,2*radius,2*radius);if(m.collectible==MapCollectibleState::NpcReward){Pen reward(Color(255,245,213,106),2*markerScale);float r=8*markerScale;graphics.DrawEllipse(&reward,px-r,py-r,2*r,2*r);}}
    else if(m.collectible==MapCollectibleState::ContainerAvailable)graphics.FillRectangle(&brush,px-radius,py-radius,2*radius,2*radius);
    else{Pen uncertain(Color(255,181,114,235),2*markerScale);graphics.DrawRectangle(&uncertain,px-radius,py-radius,2*radius,2*radius);}
   }
   for(unsigned i=0;i<canvas.pointCount;++i){const auto& exit=canvas.points[i];float px=0,py=0;if(!mapExitApplies(exit,canvas.player)||!point(exit.x,exit.y,px,py))continue;
    float r=7*markerScale;PointF diamond[]={{px,py-r},{px+r,py},{px,py+r},{px-r,py}};Color color(255,75,205,244);
    if(exit.flags){Pen outline(color,2*markerScale);graphics.DrawPolygon(&outline,diamond,4);}else{SolidBrush fill(color);graphics.FillPolygon(&fill,diamond,4);}
   }
   float px=0,py=0;if(point(canvas.player.x,canvas.player.y,px,py)){
    SolidBrush player(Color(255,255,166,35));float dx=0,dy=0,r=8*markerScale;
    if(mapPlayerHeading(canvas.player.directionX,canvas.player.directionY,dx,dy)){PointF arrow[]={{px+dx*r,py+dy*r},{px-dx*r*.7f-dy*r*.7f,py-dy*r*.7f+dx*r*.7f},{px-dx*r*.7f+dy*r*.7f,py-dy*r*.7f-dx*r*.7f}};graphics.FillPolygon(&player,arrow,3);}
    else graphics.FillEllipse(&player,px-r*.6f,py-r*.6f,r*1.2f,r*1.2f);
   }

 }
 GdiFlush();paintedPlayer=comparable;frameValid=true;++frameBuilds;return true;
}
void renderCanvas(HDC target,int width,int height){if(composeCanvas(width,height))BitBlt(target,0,0,width,height,frameSurface.dc,0,0,SRCCOPY);}
// No HWND is created for the map. WM_PAINT can never mirror it into a wrapper's
// virtual screen. The sole presenter is the retained native backbuffer hook.

}
bool mapFramePanel(int width,int height,FramePanel& out){
 out={};auto current=readMapSnapshot();DWORD now=GetTickCount();bool active=configured&&current.valid&&DWORD(now-current.timestamp)<250;
 if(!active){mapCycles(false);mapDisplayStep(canvas.display,false,false);wasActive=false;return false;}
 auto before=canvas.display.mode;auto mode=mapDisplayStep(canvas.display,true,(mapPad()&2)!=0);
 for(unsigned count=mapCycles(true);count;--count)mode=mapDisplayCycle(canvas.display);
 if(mode!=before&&trace)trace(mode==MapDisplayMode::Mini?L"MAP_OVERLAY_MODE mini":mode==MapDisplayMode::Full?L"MAP_OVERLAY_MODE full native_frame=true":L"MAP_OVERLAY_MODE off");
 if(mode==MapDisplayMode::Off){wasActive=false;return false;}
 if(!gdipToken){GdiplusStartupInput input;if(GdiplusStartup(&gdipToken,&input,nullptr)!=Ok)return false;}
 MapOverlayLayout layout;if(!mapOverlayLayout(width,height,mode,layout,current.uiHeight))return false;
 bool changed=!wasActive||mode!=before||canvas.loaded!=current.identifier||canvas.loadedField!=current.fieldIdentifier||alphaSurface.width!=layout.width||alphaSurface.height!=layout.height||canvas.scale!=layout.scale;
 // Input is consumed each native frame; marker/canvas updates are bounded to 30Hz.
 if(changed||DWORD(now-lastFrameAt)>=33){
  canvas.player=current;canvas.scale=layout.scale;
  if(canvas.loaded!=current.identifier)load(current.identifier);
  if(canvas.loadedField!=current.fieldIdentifier){loadPoints(current.fieldIdentifier,current.identifier);frameValid=false;}
  if(!canvas.image||!alphaSurface.resize(layout.width,layout.height)||!composeCanvas(layout.width,layout.height))return false;
  const unsigned alpha=mapOverlayOpacity(mode);GdiFlush();
  for(size_t i=0,n=size_t(layout.width)*layout.height;i<n;++i){DWORD c=frameSurface.pixels[i]&0xffffffu;
   if(c==0x132027){alphaSurface.pixels[i]=0;continue;}
   unsigned r=(c>>16)&255,g=(c>>8)&255,b=c&255;
   alphaSurface.pixels[i]=(alpha<<24)|(((r*alpha+127)/255)<<16)|(((g*alpha+127)/255)<<8)|((b*alpha+127)/255);
  }
  lastFrameAt=now;
 }
 wasActive=true;out={layout.x,layout.y,layout.width,layout.height,alphaSurface.pixels,alphaSurface.dc};return true;
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
bool mapView(const MapMetadata& m,float x,float y,bool mini,MapView& v){float px=0,py=0;if(!mapPixel(m,x,y,px,py))return false;v={0,0,float(m.width)};if(mini){v.span=std::clamp(m.scale*720.f,16.f,float(m.width));v.left=px-v.span/2;v.top=py-v.span/2;}return true;}
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
bool mapOverlayLayout(int width,int height,MapDisplayMode mode,MapOverlayLayout& out,int uiHeight){
 out={};if(width<128||height<128||mode==MapDisplayMode::Off)return false;
 if(uiHeight<128||uiHeight>8192)uiHeight=480;
 const float sy=float(height)/uiHeight;
 out.scale=std::clamp(sy,.5f,8.f);
 if(mode==MapDisplayMode::Full){out.width=width;out.height=height;return true;}
 // Native FDI 136 / BGR 234 alpha extent is [0,97); reserve 108 UI units.
 out.y=int(std::ceil(108*sy));
 int margin=std::max(4,int(std::ceil(6*sy)));
 out.width=std::min({int(std::lround(152*sy)),width/3,height-out.y-margin});
 out.height=out.width;out.x=width-margin-out.width;
 return out.width>=32&&out.y+out.height<=height;
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
  if(readable(engine+0xf1b4c,4)){int h=*reinterpret_cast<int*>(engine+0xf1b4c);if(h>=128&&h<=8192)value.uiHeight=h;}
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
 if(value.valid){if(reportedMap!=value.identifier&&trace){wchar_t line[256];swprintf_s(line,L"MAP_OBSERVER_VALID map=%04d position=(%.3f,%.3f,%.3f) root_id_match=true",value.identifier,value.x,value.y,value.z);trace(line);reportedMap=value.identifier;}}
}
MapSnapshot readMapSnapshot(){AcquireSRWLockShared(&snapshotLock);auto value=snapshot;ReleaseSRWLockShared(&snapshotLock);return value;}
bool installMapOverlay(HMODULE module,void(*logger)(const wchar_t*)){
 if(configured)return engine==reinterpret_cast<BYTE*>(module);
 engine=reinterpret_cast<BYTE*>(module);trace=logger;
 if(!GetEnvironmentVariableW(L"MC_MAP_ASSETS",assetDirectory,32768)||GetFileAttributesW(assetDirectory)==INVALID_FILE_ATTRIBUTES)return false;
 readLabels();configured=true;
#ifndef MAP_OVERLAY_TEST
 setFramePanel(2,&mapFramePanel);
#endif
 if(trace)trace(L"MAP_OBSERVER_READY MAP_F9_CYCLE_V1 MAP_FRAME_PRESENT_V2 path=native_backbuffer window_dc=false mini_span=720 anchor=below_compass cache=terrain_and_buffers");
 return true;
}
void stopMapOverlay(){
#ifndef MAP_OVERLAY_TEST
 setFramePanel(2,nullptr);modernGamepadMapContext(nullptr,0,false);
#endif
 clearMapCanvas();if(gdipToken){GdiplusShutdown(gdipToken);gdipToken=0;}
 configured=false;engine=nullptr;trace=nullptr;canvas.display={};canvas.loaded=canvas.loadedField=-2;canvas.pointCount=0;reportedMap=-1;
 AcquireSRWLockExclusive(&snapshotLock);snapshot={};historyCount=0;historyActor=nullptr;historyMap=historyField=-1;ReleaseSRWLockExclusive(&snapshotLock);
 wcscpy_s(label,L"Area map");wcscpy_s(legend,L"N NPC    B Box    P Player");wcscpy_s(hint,L"F9: Mini > Full map > Off");assetDirectory[0]=0;
}
#ifdef MAP_OVERLAY_TEST
bool mapOverlayTestResetState(){return !configured&&!gdipToken&&canvas.display.mode==MapDisplayMode::Off&&!readMapSnapshot().valid&&historyCount==0;}
unsigned mapOverlayTestLoadPoints(const wchar_t* assets,int fieldIdentifier,int mapIdentifier){wcscpy_s(assetDirectory,assets);loadPoints(fieldIdentifier,mapIdentifier);return canvas.pointCount;}
MapExitPoint mapOverlayTestPoint(unsigned index){return index<canvas.pointCount?canvas.points[index]:MapExitPoint{};}
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
 SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);clearMapCanvas();GdiplusShutdown(token);return saved;
}
#endif
