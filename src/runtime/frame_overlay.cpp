#include "frame_overlay.h"
#include <cstring>
#include <cstdint>
#include <intrin.h>
#include <initializer_list>
namespace {
constexpr unsigned site=0xc20c,engineSize=0x10b000;
BYTE* engine=nullptr;BYTE* bridge=nullptr;
FramePanelSource sources[3]{};void(*trace)(const wchar_t*)=nullptr;
#ifdef FRAME_OVERLAY_TEST
BYTE* fixtureDriver=nullptr;bool fixtureFocus=true;
#endif
bool readable(const void* v,size_t n){
 auto p=reinterpret_cast<uintptr_t>(v);if(!p||n>~uintptr_t(0)-p)return false;
 auto end=p+n;while(p<end){MEMORY_BASIC_INFORMATION m{};
  if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  DWORD a=m.Protect&0xff;if(a!=PAGE_READONLY&&a!=PAGE_READWRITE&&a!=PAGE_WRITECOPY&&a!=PAGE_EXECUTE_READ&&a!=PAGE_EXECUTE_READWRITE&&a!=PAGE_EXECUTE_WRITECOPY)return false;
  auto next=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next<end?next:end;
 }return true;
}
bool callable(void* p){MEMORY_BASIC_INFORMATION m{};if(!p||!VirtualQuery(p,&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto a=m.Protect&0xff;return a==PAGE_EXECUTE||a==PAGE_EXECUTE_READ||a==PAGE_EXECUTE_READWRITE||a==PAGE_EXECUTE_WRITECOPY;}
bool identity(BYTE* p,DWORD stamp,DWORD size){
 if(!readable(p,64))return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096||!readable(p+d->e_lfanew,sizeof(IMAGE_NT_HEADERS32)))return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);
 return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&n->FileHeader.TimeDateStamp==stamp&&n->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&n->OptionalHeader.SizeOfImage==size;
}

void nativeBytes(BYTE* p,BYTE* bytes){const BYTE prefix[]={0x55,0x8b,0xec,0xa1,0,0,0,0};memcpy(bytes,prefix,8);*reinterpret_cast<DWORD*>(bytes+4)=DWORD(p+0xf1b70);}
bool windowMatches(HWND window,HWND focused){
 if(!window||!focused||!IsWindow(window)||!IsWindow(focused))return false;
 auto root=GetAncestor(window,GA_ROOT);if(!root||IsIconic(root)||root!=GetAncestor(focused,GA_ROOT))return false;
 DWORD owner=0,active=0;GetWindowThreadProcessId(window,&owner);GetWindowThreadProcessId(focused,&active);
 return owner==GetCurrentProcessId()&&active==owner;
}
bool foreground(){
#ifdef FRAME_OVERLAY_TEST
 return fixtureFocus;
#else
 // Use the exact HWND that native BackOut uses, including a render child.
 // No dependency on the engine's separately initialized input/HUD window.
 auto renderer=*reinterpret_cast<BYTE**>(engine+0xf1b70);
 return readable(renderer,0x10)&&windowMatches(*reinterpret_cast<HWND*>(renderer+0xc),GetForegroundWindow());
#endif
}
bool draw(){
 if(!foreground())return false;
 auto d=reinterpret_cast<BYTE*>(GetModuleHandleW(L"AsrD3DDrv.dll"));
#ifdef FRAME_OVERLAY_TEST
 if(fixtureDriver)d=fixtureDriver;
#endif
 if(!identity(d,0x3c2b7d28,0x2c000)||!readable(d+0x1a5a8,0x598))return false;
 auto r=*reinterpret_cast<BYTE**>(engine+0xf1b70);
 if(!readable(r,0x3c)||!readable(r+0x122f1c,4))return false;
 auto table=*reinterpret_cast<BYTE***>(r);
 if(reinterpret_cast<BYTE*>(table)!=d+0x1a5a8||table[0x40/4]!=d+0x3d3e||table[0x590/4]!=d+0x6522)return false;
 auto back=*reinterpret_cast<BYTE**>(r+0x38);
 if(!readable(back,0x90))return false;
 int w=*reinterpret_cast<int*>(back+0x88),h=*reinterpret_cast<int*>(back+0x8c);
 if(w<1||h<1||w>16384||h>16384)return false;
 auto surface=*reinterpret_cast<void**>(back+4);
 if(!readable(surface,4))return false;auto v=*reinterpret_cast<void***>(surface);
 if(!readable(v,0x6c)||!callable(v[0x44/4])||!callable(v[0x68/4])||!callable(table[0x14/4]))return false;

 FramePanel panels[3];bool any=false;
 for(unsigned i=0;i<3;++i)if(sources[i]&&sources[i](w,h,panels[i]))any=true;
 if(!any)return true;
 // Native BackOut (driver RVA 3155) ends the active D3D scene immediately
 // before presenting. Pixels must be inserted AFTER that same EndScene, not
 // silently skipped while a scene is active and not drawn after presentation.
 if(*reinterpret_cast<DWORD*>(r+0x122f1c)){
  auto device=*reinterpret_cast<void**>(r+0x2c);
  if(!readable(device,4))return false;auto methods=*reinterpret_cast<void***>(device);
  if(!readable(methods,28)||!callable(methods[6]))return false;
  *reinterpret_cast<DWORD*>(r+0x122f1c)=0;
  using EndScene=HRESULT(WINAPI*)(void*);
  if(FAILED(reinterpret_cast<EndScene>(methods[6])(device)))return false;
 }
 using GetDC=HRESULT(WINAPI*)(void*,HDC*);using ReleaseDC=HRESULT(WINAPI*)(void*,HDC);
 HDC dc=nullptr;if(FAILED(reinterpret_cast<GetDC>(v[17])(surface,&dc)))return false;
 bool ok=dc!=nullptr;
 if(dc)for(unsigned index:{2u,0u,1u}){
  auto& panel=panels[index];
  if(!panel.pixels)continue;
  if(panel.width<1||panel.height<1||panel.x<0||panel.y<0||panel.x+panel.width>w||panel.y+panel.height>h){ok=false;continue;}
  if(panel.alphaDC){
   BLENDFUNCTION blend{AC_SRC_OVER,0,255,AC_SRC_ALPHA};
   if(!AlphaBlend(dc,panel.x,panel.y,panel.width,panel.height,panel.alphaDC,0,0,panel.width,panel.height,blend))ok=false;
   continue;
  }
  BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=panel.width;info.bmiHeader.biHeight=-panel.height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
  int n=StretchDIBits(dc,panel.x,panel.y,panel.width,panel.height,0,0,panel.width,panel.height,panel.pixels,&info,DIB_RGB_COLORS,SRCCOPY);
  if(!n||n==GDI_ERROR)ok=false;
 }
 if(dc)GdiFlush();return SUCCEEDED(reinterpret_cast<ReleaseDC>(v[26])(surface,dc))&&ok;
}
void before(){DWORD error=GetLastError();alignas(16) BYTE fpu[512];_fxsave(fpu);draw();_fxrstor(fpu);SetLastError(error);}
void __cdecl present(){before();reinterpret_cast<void(__cdecl*)()>(bridge)();}
void jump(BYTE* p,const void* target){p[0]=0xe9;*reinterpret_cast<DWORD*>(p+1)=DWORD(target)-DWORD(p+5);}
bool replace(BYTE* p,const BYTE* from,const BYTE* to){if(memcmp(p,from,8))return false;DWORD old;if(!VirtualProtect(p,8,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(p,to,8);FlushInstructionCache(GetCurrentProcess(),p,8);DWORD ignored;return VirtualProtect(p,8,old,&ignored)!=0;}
}
bool frameOverlayAvailable(){return engine&&bridge;}
void setFramePanel(unsigned index,FramePanelSource source){if(index<3)sources[index]=source;}
bool installFrameOverlay(HMODULE m,void(*logger)(const wchar_t*)){
 auto p=reinterpret_cast<BYTE*>(m);if(!identity(p,0x3ed73966,engineSize))return false;
 BYTE native[8],patch[8];nativeBytes(p,native);memset(patch,0x90,8);
 // Build the relative branch against the actual instruction address.
 patch[0]=0xe9;*reinterpret_cast<DWORD*>(patch+1)=DWORD(&present)-DWORD(p+site+5);
 if(engine)return engine==p&&!memcmp(p+site,patch,8);
 const BYTE rest[]={0x8b,0x10,0x8b,0x0d};if(memcmp(p+site+8,rest,4)||memcmp(p+site,native,8))return false;
 auto b=static_cast<BYTE*>(VirtualAlloc(nullptr,13,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));if(!b)return false;
 memcpy(b,native,8);jump(b+8,p+site+8);DWORD old;
 if(!VirtualProtect(b,13,PAGE_EXECUTE_READ,&old)){VirtualFree(b,0,MEM_RELEASE);return false;}
 FlushInstructionCache(GetCurrentProcess(),b,13);bridge=b;engine=p;trace=logger;
 if(!replace(p+site,native,patch)){VirtualFree(b,0,MEM_RELEASE);bridge=engine=nullptr;return false;}
 if(trace)trace(L"FRAME_OVERLAY_READY order=after_native_ui_before_present surface=retained_backbuffer window_dc=false");return true;
}
bool removeFrameOverlay(HMODULE m){auto p=reinterpret_cast<BYTE*>(m);if(engine!=p)return false;BYTE native[8],patch[8];nativeBytes(p,native);memset(patch,0x90,8);patch[0]=0xe9;*reinterpret_cast<DWORD*>(patch+1)=DWORD(&present)-DWORD(p+site+5);if(!replace(p+site,patch,native))return false;VirtualFree(bridge,0,MEM_RELEASE);bridge=engine=nullptr;return true;}
#ifdef FRAME_OVERLAY_TEST
void initializeFrameOverlayFixture(BYTE* p,BYTE* d){
 auto header=[](BYTE* b,DWORD stamp,DWORD size){memset(b,0,size);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(b);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(b+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->FileHeader.TimeDateStamp=stamp;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=size;};
 header(p,0x3ed73966,engineSize);header(d,0x3c2b7d28,0x2c000);nativeBytes(p,p+site);
 const BYTE rest[]={0x8b,0x10,0x8b,0x0d,0,0,0,0,0xff,0x52,0x14,0x5d,0xc3};memcpy(p+site+8,rest,sizeof(rest));*reinterpret_cast<DWORD*>(p+site+12)=DWORD(p+0xf1b70);
 auto v=reinterpret_cast<BYTE**>(d+0x1a5a8);v[0x40/4]=d+0x3d3e;v[0x590/4]=d+0x6522;
}
void frameOverlayFixtureDriver(BYTE* d){fixtureDriver=d;}
void frameOverlayFixtureFocus(bool active){fixtureFocus=active;}
bool frameOverlayFixtureWindow(HWND window,HWND focused){return windowMatches(window,focused);}
#endif
