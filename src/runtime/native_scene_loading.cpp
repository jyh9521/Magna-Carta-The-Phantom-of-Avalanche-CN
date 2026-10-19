#include "native_scene_loading.h"
#include <cstdint>
#include <cstring>
#include <initializer_list>
namespace {
constexpr unsigned site=0x631da;
constexpr BYTE original[]={0xe8,0x43,1,0,0};
constexpr BYTE cleanupCall[]={0xe8,0xe1,0,0,0};
constexpr BYTE loadingPrefix[]={0x55,0x8b,0xec,0x6a,0xff,0x68,0x64,0xb2,0x0b,0x52};
BYTE* engine=nullptr;void(*trace)(const wchar_t*)=nullptr;
using Method=void(__thiscall*)(void*);
thread_local bool busy=false;unsigned notices=0;
bool readable(const void* v,size_t n){auto p=reinterpret_cast<uintptr_t>(v);if(!p||n>~uintptr_t(0)-p)return false;
 const auto end=p+n;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  auto a=m.Protect&0xff;if(a!=PAGE_READONLY&&a!=PAGE_READWRITE&&a!=PAGE_WRITECOPY&&a!=PAGE_EXECUTE_READ&&a!=PAGE_EXECUTE_READWRITE&&a!=PAGE_EXECUTE_WRITECOPY)return false;
  auto next=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next<end?next:end;
 }return true;}
bool executable(void* p){MEMORY_BASIC_INFORMATION m{};if(!p||!VirtualQuery(p,&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto a=m.Protect&0xff;return a==PAGE_EXECUTE||a==PAGE_EXECUTE_READ||a==PAGE_EXECUTE_READWRITE||a==PAGE_EXECUTE_WRITECOPY;}
bool source(BYTE* p){if(!readable(p,64))return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096||!readable(p+d->e_lfanew,sizeof(IMAGE_NT_HEADERS32)))return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);
 if(n->Signature!=IMAGE_NT_SIGNATURE||n->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||n->FileHeader.TimeDateStamp!=0x3ed73966||n->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||n->OptionalHeader.SizeOfImage!=0x10b000||!readable(p+site,5)||!readable(p+0x63075,5)||!readable(p+0x71085,10)||!readable(p+0x71136,5))return false;
 BYTE prefix[10];memcpy(prefix,loadingPrefix,10);DWORD handler=DWORD(uintptr_t(p+0xbb264));memcpy(prefix+6,&handler,4);
 constexpr BYTE resource[]={0x68,0xcc,0,0,0};return !memcmp(p+0x71085,prefix,10)&&!memcmp(p+0x71136,resource,5)&&!memcmp(p+0x63075,cleanupCall,5);}
void armNativeLoading(void* job){
 if(!readable(job,16)||*reinterpret_cast<int*>(engine+0xf2280)!=0x1f)return;
 auto scene=*reinterpret_cast<BYTE**>(static_cast<BYTE*>(job)+12);
 if(!readable(scene,0x1738)||*reinterpret_cast<BYTE**>(scene)!=engine+0xc12bc||*reinterpret_cast<int*>(scene+0x156c)!=7||*reinterpret_cast<int*>(scene+0x1730)!=0)return;
 // The normal frame invokes 6b3bc after the fixed update, with all render passes intact.
 // Only enable its existing native gate; never submit a second frame after fade/cleanup.
 bool ready=engine[0x38b45]==0xe9&&engine[0x38b4a]==0x90;
 auto gui=*reinterpret_cast<BYTE**>(scene+0x10c8);
 ready=ready&&readable(gui,0x1a0)&&readable(*reinterpret_cast<void**>(gui+0x19c),0xf4);
 for(auto offset:{0x1720,0x1724}){auto value=*reinterpret_cast<void**>(scene+offset);if(!readable(value,4)){ready=false;break;}auto v=*reinterpret_cast<void***>(value);if(!readable(v,0x38)||!executable(v[0x34/4])){ready=false;break;}}
 if(ready)*reinterpret_cast<int*>(scene+0x1730)=1;
 if(trace&&notices++<16)trace(ready?L"NATIVE_LOADING_ARMED flag=1730 before=native_draw standalone_present=false":L"NATIVE_LOADING_SKIPPED prerequisites=unavailable native_frame=original");
}
void __fastcall beforeDraw(void* job,void*){DWORD error=GetLastError();
 if(!busy){busy=true;__try{armNativeLoading(job);}__finally{busy=false;}}
 SetLastError(error);reinterpret_cast<Method>(engine+0x63322)(job);
}
void branch(BYTE* b,BYTE* p){b[0]=0xe8;DWORD relative=DWORD(uintptr_t(&beforeDraw)-uintptr_t(p+site+5));memcpy(b+1,&relative,4);}
bool replace(BYTE* p,const BYTE* from,const BYTE* to){if(memcmp(p,from,5))return false;DWORD old;if(!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old))return false;
 memcpy(p,to,5);FlushInstructionCache(GetCurrentProcess(),p,5);DWORD ignored;if(!VirtualProtect(p,5,old,&ignored)){memcpy(p,from,5);FlushInstructionCache(GetCurrentProcess(),p,5);VirtualProtect(p,5,old,&ignored);return false;}return true;}
}
bool installNativeSceneLoading(HMODULE m,void(*logger)(const wchar_t*)){auto p=reinterpret_cast<BYTE*>(m);if(!source(p))return false;BYTE b[5];branch(b,p);
 if(engine)return engine==p&&!memcmp(p+site,b,5);if(memcmp(p+site,original,5))return false;engine=p;trace=logger;
 if(!replace(p+site,original,b)){engine=nullptr;trace=nullptr;return false;}if(trace)trace(L"NATIVE_LOADING_READY fdi=0204 scope=field_to_field route=native_frame artwork=original");return true;}
bool removeNativeSceneLoading(HMODULE m){auto p=reinterpret_cast<BYTE*>(m);if(!source(p))return false;if(!engine)return !memcmp(p+site,original,5);if(engine!=p)return false;
 BYTE b[5];branch(b,p);if(!replace(p+site,b,original))return false;engine=nullptr;trace=nullptr;return true;}
#ifdef NATIVE_SCENE_LOADING_TEST
void initializeNativeSceneLoadingFixture(BYTE* p){memset(p,0,0x10b000);auto h=reinterpret_cast<IMAGE_DOS_HEADER*>(p);h->e_magic=IMAGE_DOS_SIGNATURE;h->e_lfanew=0x100;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->FileHeader.TimeDateStamp=0x3ed73966;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=0x10b000;
 memcpy(p+site,original,5);memcpy(p+0x63075,cleanupCall,5);memcpy(p+0x71085,loadingPrefix,10);DWORD hnd=DWORD(uintptr_t(p+0xbb264));memcpy(p+0x71085+6,&hnd,4);const BYTE resource[]={0x68,0xcc,0,0,0};memcpy(p+0x71136,resource,5);p[0x38b45]=0xe9;p[0x38b4a]=0x90;}
#endif
