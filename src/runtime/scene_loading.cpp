#include "scene_loading.h"
#include <cstdint>
#include <cstring>
namespace {
constexpr unsigned site=0x63075, engineSize=0x10b000;
constexpr BYTE call[]={0xe8,0xe1,0,0,0};
constexpr BYTE loop[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d};
constexpr int width=320,height=180;
DWORD pixels[width*height]{};
BYTE* engine=nullptr;
void(*trace)(const wchar_t*)=nullptr;
using Cleanup=void(__thiscall*)(void*);
Cleanup cleanup=nullptr;
thread_local bool presenting=false;
unsigned notices=0;
#ifdef SCENE_LOADING_TEST
BYTE* fixtureDriver=nullptr;
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
bool source(BYTE* p){return identity(p,0x3ed73966,engineSize)&&readable(p+site,5)&&readable(p+0x631a0,sizeof(loop))&&!memcmp(p+0x631a0,loop,sizeof(loop));}
void preparePixels(){
 // Owned, locale-neutral prelude. No font, texture, filesystem or allocation at transition time.
 for(auto& p:pixels)p=0x101620;
 const BYTE glyphs[][7]={{16,16,16,16,16,16,31},{14,17,17,17,17,17,14},
  {14,17,17,31,17,17,17},{30,17,17,17,17,17,30},{31,4,4,4,4,4,31},
  {17,25,25,21,19,19,17},{14,17,16,23,17,17,14},{0,0,0,0,0,12,12}};
 const unsigned text[]={0,1,2,3,4,5,6,7,7,7};
 constexpr int scale=2,left=(width-(10*6-1)*scale)/2,top=80;
 for(int k=0;k<10;++k)for(int y=0;y<7;++y)for(int x=0;x<5;++x)
  if(glyphs[text[k]][y]&(1<<(4-x)))for(int a=0;a<scale;++a)for(int b=0;b<scale;++b)
   pixels[(top+y*scale+a)*width+left+(k*6+x)*scale+b]=0xe6edf3;
 for(int y=104;y<106;++y)for(int x=144;x<176;++x)pixels[y*width+x]=0x6cd4c5;
}
bool draw(){
 auto d=reinterpret_cast<BYTE*>(GetModuleHandleW(L"AsrD3DDrv.dll"));
#ifdef SCENE_LOADING_TEST
 if(fixtureDriver)d=fixtureDriver;
#endif
 if(!identity(d,0x3c2b7d28,0x2c000)||!readable(d+0x1a5a8,0x598))return false;
 auto r=*reinterpret_cast<BYTE**>(engine+0xf1b70);
 if(!readable(r,0x3c)||!readable(r+0x122f1c,4)||*reinterpret_cast<DWORD*>(r+0x122f1c))return false;
 auto table=*reinterpret_cast<BYTE***>(r);
 if(reinterpret_cast<BYTE*>(table)!=d+0x1a5a8||table[0x40/4]!=d+0x3d3e||table[0x590/4]!=d+0x6522)return false;
 auto back=*reinterpret_cast<BYTE**>(r+0x38);
 if(!readable(back,0x90))return false;
 int w=*reinterpret_cast<int*>(back+0x88),h=*reinterpret_cast<int*>(back+0x8c);
 if(w<1||h<1||w>16384||h>16384)return false;
 auto surface=*reinterpret_cast<void**>(back+4);
 if(!readable(surface,4))return false;auto v=*reinterpret_cast<void***>(surface);
 if(!readable(v,0x6c)||!callable(v[0x44/4])||!callable(v[0x68/4])||!callable(table[0x14/4]))return false;
 // Same retained backbuffer and COM ABI as the native driver's BackOut.
 // Unlike its retrying wrapper, a lost/busy surface is skipped without a loop.
 using GetDC=HRESULT(WINAPI*)(void*,HDC*);using ReleaseDC=HRESULT(WINAPI*)(void*,HDC);
 HDC dc=nullptr;HRESULT acquired=reinterpret_cast<GetDC>(v[0x44/4])(surface,&dc);
 if(FAILED(acquired))return false;
 int lines=0;
 if(dc){BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=width;info.bmiHeader.biHeight=-height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
  // StretchDIBits leaves the DC's persistent mapping/font/palette state untouched.
  lines=StretchDIBits(dc,0,0,w,h,0,0,width,height,pixels,&info,DIB_RGB_COLORS,SRCCOPY);
 }
 if(dc)GdiFlush();
 HRESULT released=reinterpret_cast<ReleaseDC>(v[0x68/4])(surface,dc);
 if(!dc||lines==0||lines==GDI_ERROR||FAILED(released))return false;
 using Present=BYTE(__thiscall*)(void*);
 return reinterpret_cast<Present>(table[0x14/4])(r)!=0;
}
void __fastcall beforeCleanup(void* job,void*){
 DWORD lastError=GetLastError();
 // Only Field -> Field; menu, title, shutdown and failed startup retain native behavior.
 if(!presenting&&*reinterpret_cast<int*>(engine+0xf2280)==0x1f){
  presenting=true;bool ok=false;
  __try {ok=draw();} __finally {presenting=false;}
  if(trace&&notices++<16)trace(ok?L"SCENE_LOADING_PRESENTED before=field_cleanup asset=owned_prepared sync_loading=original":L"SCENE_LOADING_SKIPPED surface=unavailable cleanup=original");
 }
 SetLastError(lastError);cleanup(job);
}
void branch(BYTE* b,BYTE* p){b[0]=0xe8;DWORD rel=DWORD(reinterpret_cast<uintptr_t>(&beforeCleanup)-reinterpret_cast<uintptr_t>(p+site+5));memcpy(b+1,&rel,4);}
bool replace(BYTE* p,const BYTE* from,const BYTE* to){
 if(memcmp(p,from,5))return false;DWORD old;if(!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old))return false;
 memcpy(p,to,5);FlushInstructionCache(GetCurrentProcess(),p,5);DWORD ignored;
 if(!VirtualProtect(p,5,old,&ignored)){memcpy(p,from,5);FlushInstructionCache(GetCurrentProcess(),p,5);VirtualProtect(p,5,old,&ignored);return false;}return true;
}
}
bool installSceneLoading(HMODULE m,void(*logger)(const wchar_t*)){
 auto p=reinterpret_cast<BYTE*>(m);if(!source(p))return false;BYTE b[5];branch(b,p);
 if(engine)return engine==p&&!memcmp(p+site,b,5);
 if(memcmp(p+site,call,5))return false;
 preparePixels();engine=p;cleanup=reinterpret_cast<Cleanup>(p+0x6315b);trace=logger;
 if(!replace(p+site,call,b)){engine=nullptr;cleanup=nullptr;trace=nullptr;return false;}
 if(trace)trace(L"SCENE_LOADING_READY scope=field_to_field before=cleanup renderer=existing_backbuffer");return true;
}
bool removeSceneLoading(HMODULE m){
 auto p=reinterpret_cast<BYTE*>(m);if(!source(p))return false;
 if(!engine)return !memcmp(p+site,call,5);if(engine!=p)return false;
 BYTE b[5];branch(b,p);if(!replace(p+site,b,call))return false;
 // Quiescent fixture/maintenance only; normal rollback uses stopped-process file routing.
 engine=nullptr;cleanup=nullptr;trace=nullptr;return true;
}
#ifdef SCENE_LOADING_TEST
void initializeSceneLoadingFixture(BYTE* p,BYTE* d){
 auto header=[](BYTE* b,DWORD stamp,DWORD size){memset(b,0,size);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(b);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(b+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->FileHeader.TimeDateStamp=stamp;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=size;};
 header(p,0x3ed73966,engineSize);header(d,0x3c2b7d28,0x2c000);memcpy(p+site,call,5);memcpy(p+0x631a0,loop,sizeof(loop));
 auto v=reinterpret_cast<BYTE**>(d+0x1a5a8);v[0x40/4]=d+0x3d3e;v[0x590/4]=d+0x6522;
}
void setSceneLoadingFixtureDriver(BYTE* d){fixtureDriver=d;}
#endif
