#include "native_scene_loading.h"
#include <cstdint>
#include <cstring>
#include <initializer_list>
namespace {
constexpr unsigned site=0x63075;
constexpr BYTE original[]={0xe8,0xe1,0,0,0};
constexpr BYTE loadingPrefix[]={0x55,0x8b,0xec,0x6a,0xff,0x68,0x64,0xb2,0x0b,0x52};
BYTE* engine=nullptr;void(*trace)(const wchar_t*)=nullptr;
using Method=void(__thiscall*)(void*);using Render=void(__cdecl*)(void*);using Clear=void(__cdecl*)();
thread_local bool busy=false;unsigned notices=0;
#ifdef NATIVE_SCENE_LOADING_TEST
BYTE* fixtureDriver=nullptr;Render fixtureRender=nullptr;Clear fixtureClear=nullptr;
#endif
bool readable(const void* v,size_t n){auto p=reinterpret_cast<uintptr_t>(v);if(!p||n>~uintptr_t(0)-p)return false;
 const auto end=p+n;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  auto a=m.Protect&0xff;if(a!=PAGE_READONLY&&a!=PAGE_READWRITE&&a!=PAGE_WRITECOPY&&a!=PAGE_EXECUTE_READ&&a!=PAGE_EXECUTE_READWRITE&&a!=PAGE_EXECUTE_WRITECOPY)return false;
  auto next=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next<end?next:end;
 }return true;}
bool executable(void* p){MEMORY_BASIC_INFORMATION m{};if(!p||!VirtualQuery(p,&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto a=m.Protect&0xff;return a==PAGE_EXECUTE||a==PAGE_EXECUTE_READ||a==PAGE_EXECUTE_READWRITE||a==PAGE_EXECUTE_WRITECOPY;}
bool identity(BYTE* p,DWORD stamp,DWORD size){if(!readable(p,64))return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096||!readable(p+d->e_lfanew,sizeof(IMAGE_NT_HEADERS32)))return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&n->FileHeader.TimeDateStamp==stamp&&n->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&n->OptionalHeader.SizeOfImage==size;}
bool source(BYTE* p){if(!identity(p,0x3ed73966,0x10b000)||!readable(p+site,5)||!readable(p+0x71085,10)||!readable(p+0x71136,5))return false;
 // Relocated SEH handler is compared to this actual image base, not preferred base.
 BYTE prefix[10];memcpy(prefix,loadingPrefix,10);DWORD handler=DWORD(uintptr_t(p+0xbb264));memcpy(prefix+6,&handler,4);
 constexpr BYTE resource[]={0x68,0xcc,0,0,0};return !memcmp(p+0x71085,prefix,10)&&!memcmp(p+0x71136,resource,5);}
bool presentNative(void* job){
 if(!readable(job,16))return false;auto scene=*reinterpret_cast<BYTE**>(static_cast<BYTE*>(job)+12);
 if(!readable(scene,0x1738)||*reinterpret_cast<BYTE**>(scene)!=engine+0xc12bc||*reinterpret_cast<int*>(scene+0x156c)!=7)return false;
 // Existing generic-root bounds guard is required by the original frame constructor.
 if(engine[0x38b45]!=0xe9||engine[0x38b4a]!=0x90)return false;
 auto gui=*reinterpret_cast<BYTE**>(scene+0x10c8);
 if(!readable(gui,0x1a0)||!readable(*reinterpret_cast<void**>(gui+0x19c),0xf4))return false;
 for(auto offset:{0x1720,0x1724}){auto value=*reinterpret_cast<void**>(scene+offset);if(!readable(value,4))return false;auto v=*reinterpret_cast<void***>(value);if(!readable(v,0x38)||!executable(v[0x34/4]))return false;}
 auto driver=reinterpret_cast<BYTE*>(GetModuleHandleW(L"AsrD3DDrv.dll"));
 auto asura=reinterpret_cast<BYTE*>(GetModuleHandleW(L"Asura.dll"));Render render=nullptr;Clear clear=nullptr;
 if(identity(asura,0x3ed70009,0x74d000)){render=reinterpret_cast<Render>(GetProcAddress(reinterpret_cast<HMODULE>(asura),"?ASRRender@@YAXPAVASURA@@@Z"));clear=reinterpret_cast<Clear>(GetProcAddress(reinterpret_cast<HMODULE>(asura),"?ASRClearRender@@YAXXZ"));}
 if((render&&reinterpret_cast<BYTE*>(render)!=asura+0x516fd)||(clear&&reinterpret_cast<BYTE*>(clear)!=asura+0x4e61f))return false;
#ifdef NATIVE_SCENE_LOADING_TEST
 if(fixtureDriver){driver=fixtureDriver;render=fixtureRender;clear=fixtureClear;}
#endif
 if(!identity(driver,0x3c2b7d28,0x2c000)||!executable(reinterpret_cast<void*>(render))||!executable(reinterpret_cast<void*>(clear)))return false;
 auto renderer=*reinterpret_cast<BYTE**>(engine+0xf1b70);
 if(!readable(renderer,4)||!readable(renderer+0x122f1c,4)||*reinterpret_cast<int*>(renderer+0x122f1c))return false;
 auto table=*reinterpret_cast<BYTE***>(renderer);if(reinterpret_cast<BYTE*>(table)!=driver+0x1a5a8||!readable(table,0x598)||table[0x40/4]!=driver+0x3d3e||!executable(table[0x14/4]))return false;
 // Original FDI 0204 frame construction, placement, visibility and drawing; no replacement image.
 reinterpret_cast<Method>(engine+0x71085)(scene);
 render(renderer);
 using Present=BYTE(__thiscall*)(void*);bool shown=reinterpret_cast<Present>(table[0x14/4])(renderer)!=0;
 // ASRRender retains CPU queue entries. Discard only the completed loading batch
 // before native cleanup destroys the frame's owned geometry/transform memory.
 clear();return shown;
}
void __fastcall beforeCleanup(void* job,void*){DWORD error=GetLastError();
 if(!busy&&*reinterpret_cast<int*>(engine+0xf2280)==0x1f){busy=true;bool ok=false;
  __try{ok=presentNative(job);}__finally{busy=false;}
  if(trace&&notices++<16)trace(ok?L"NATIVE_LOADING_PRESENTED fdi=0204 before=field_cleanup artwork=original":L"NATIVE_LOADING_SKIPPED prerequisites=unavailable cleanup=original");
 }
 SetLastError(error);reinterpret_cast<Method>(engine+0x6315b)(job);
}
void branch(BYTE* b,BYTE* p){b[0]=0xe8;DWORD relative=DWORD(uintptr_t(&beforeCleanup)-uintptr_t(p+site+5));memcpy(b+1,&relative,4);}
bool replace(BYTE* p,const BYTE* from,const BYTE* to){if(memcmp(p,from,5))return false;DWORD old;if(!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old))return false;
 memcpy(p,to,5);FlushInstructionCache(GetCurrentProcess(),p,5);DWORD ignored;if(!VirtualProtect(p,5,old,&ignored)){memcpy(p,from,5);FlushInstructionCache(GetCurrentProcess(),p,5);VirtualProtect(p,5,old,&ignored);return false;}return true;}
}
bool installNativeSceneLoading(HMODULE m,void(*logger)(const wchar_t*)){auto p=reinterpret_cast<BYTE*>(m);if(!source(p))return false;BYTE b[5];branch(b,p);
 if(engine)return engine==p&&!memcmp(p+site,b,5);if(memcmp(p+site,original,5))return false;engine=p;trace=logger;
 if(!replace(p+site,original,b)){engine=nullptr;trace=nullptr;return false;}if(trace)trace(L"NATIVE_LOADING_READY fdi=0204 scope=field_to_field artwork=original");return true;}
bool removeNativeSceneLoading(HMODULE m){auto p=reinterpret_cast<BYTE*>(m);if(!source(p))return false;if(!engine)return !memcmp(p+site,original,5);if(engine!=p)return false;
 BYTE b[5];branch(b,p);if(!replace(p+site,b,original))return false;engine=nullptr;trace=nullptr;return true;}
#ifdef NATIVE_SCENE_LOADING_TEST
void initializeNativeSceneLoadingFixture(BYTE* p,BYTE* d){auto header=[](BYTE* b,DWORD stamp,DWORD size){memset(b,0,size);auto h=reinterpret_cast<IMAGE_DOS_HEADER*>(b);h->e_magic=IMAGE_DOS_SIGNATURE;h->e_lfanew=0x100;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(b+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->FileHeader.TimeDateStamp=stamp;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=size;};
 header(p,0x3ed73966,0x10b000);header(d,0x3c2b7d28,0x2c000);memcpy(p+site,original,5);memcpy(p+0x71085,loadingPrefix,10);DWORD h=DWORD(uintptr_t(p+0xbb264));memcpy(p+0x71085+6,&h,4);const BYTE resource[]={0x68,0xcc,0,0,0};memcpy(p+0x71136,resource,5);p[0x38b45]=0xe9;p[0x38b4a]=0x90;*reinterpret_cast<BYTE**>(d+0x1a5a8+0x40)=d+0x3d3e;}
void configureNativeSceneLoadingFixture(BYTE* d,void(__cdecl* render)(void*),void(__cdecl* clear)()){fixtureDriver=d;fixtureRender=render;fixtureClear=clear;}
#endif
