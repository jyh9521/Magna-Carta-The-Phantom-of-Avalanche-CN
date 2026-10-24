#include "collision_guard.h"
#include "collision_kernel.h"
#include <cstring>
#include <cstdint>
#include <cwchar>
namespace {
using Physics=void(__thiscall*)(void*);
using Point=int(__thiscall*)(void*,float,float,float);
using Position=void(__thiscall*)(void*,float,float,float);
constexpr unsigned site=0x65699,size=0x10b000;
constexpr BYTE prefix[]={0x55,0x8b,0xec,0x81,0xec,0x94,0x01,0,0};
BYTE* engine=nullptr;BYTE* bridge=nullptr;Physics original=nullptr;Point point=nullptr;
Position synchronize=nullptr;
void(*trace)(const wchar_t*)=nullptr;LONG notices=0;
bool readable(const void* v,size_t n){uintptr_t p=reinterpret_cast<uintptr_t>(v);if(!p||!n||p+n<p)return false;auto end=p+n;
 while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;}
BYTE* ptr(const void* p,unsigned o){return *reinterpret_cast<BYTE*const*>(static_cast<const BYTE*>(p)+o);}
unsigned word(const void* p,unsigned o){return *reinterpret_cast<const unsigned*>(static_cast<const BYTE*>(p)+o);}
struct Context {BYTE* level;BYTE* tree;};
int __cdecl query(CollisionVec v,void* value){
 auto c=static_cast<Context*>(value);BYTE scratch[28];memcpy(scratch,c->tree+0x14,28);
 // Point queries mutate the native tree's hit/start/end scratch. Restore it even
 // on a structured exception; extra clearance checks must not change its oracle.
 DWORD incoming=GetLastError();int result=-1;
 __try {__try {result=point(c->level,v.x,v.y,v.z);}__except(EXCEPTION_EXECUTE_HANDLER){result=-1;}}
 __finally {memcpy(c->tree+0x14,scratch,28);SetLastError(incoming);}
 return result;
}
bool select(BYTE* actor,Context& c,CollisionVec* offsets){
 if(!engine||!readable(actor,0x340)||ptr(actor,0)!=engine+0xc11e4)return false;
 auto scene=ptr(actor,0x20);
 if(!readable(scene,0x1738)||ptr(scene,0)!=engine+0xc12bc||ptr(scene,0x1564)!=actor
  ||word(scene,0x156c)!=2||word(scene,0x1574)!=0||word(scene,0x28)||word(scene,0x2c)||word(scene,0x30))return false;
 auto gui=ptr(scene,0x10c8);if(!readable(gui,0x194)||word(gui,0x190)!=1)return false;
 // Read the exact eight offsets used by native 65c83 -> 47bef; no guessed radius.
 auto visual=ptr(actor,0x2dc);if(!readable(visual,0x144))return false;
 auto model=ptr(visual,0x140);if(!readable(model,0x5c))return false;
 auto bounds=ptr(model,0x58);if(!readable(bounds,0x80))return false;
 memcpy(offsets,bounds+0x20,96);
 c.level=ptr(scene,0x1558);if(!readable(c.level,0xf8)||ptr(c.level,0)!=engine+0xc15ac)return false;
 auto guide=ptr(c.level,0xf4);if(!readable(guide,0x124))return false;
 c.tree=ptr(guide,0x120);return readable(c.tree,0x34)&&readable(ptr(c.tree,0x30),0x4c);
}
void __fastcall hook(void* value,void*){
 DWORD incoming=GetLastError();auto actor=static_cast<BYTE*>(value);Context c{};CollisionVec offsets[8],before{};
 bool active=select(actor,c,offsets);if(active)memcpy(&before,actor+0x154,12);
 SetLastError(incoming);original(value);DWORD error=GetLastError();
 Context afterContext{};CollisionVec afterOffsets[8];
 if(active&&select(actor,afterContext,afterOffsets)&&c.level==afterContext.level&&c.tree==afterContext.tree
  &&!memcmp(offsets,afterOffsets,96)){
  CollisionVec after{},corrected{};memcpy(&after,actor+0x154,12);
  unsigned status=resolveCollisionStep(before,after,offsets,8,query,&c,&corrected);
  if(status==1||status==2){
   memcpy(actor+0x154,&corrected,12);
   // Native 65699 already updates the visual transform via this same slot.
   // Repeat only that position synchronization; animation/orientation stay native.
   synchronize(actor,corrected.x,corrected.y,corrected.z);
  }
  if(status&&trace&&InterlockedIncrement(&notices)<=32){wchar_t line[384];swprintf_s(line,
   L"COLLISION_GUARD_STEP status=%u before=%.9g,%.9g,%.9g native=%.9g,%.9g,%.9g corrected=%.9g,%.9g,%.9g offsets=8 map_specific=false",
   status,before.x,before.y,before.z,after.x,after.y,after.z,corrected.x,corrected.y,corrected.z);trace(line);}
 }
 SetLastError(error);
}
void jump(BYTE* p,const void* to){p[0]=0xe9;*reinterpret_cast<DWORD*>(p+1)=DWORD(to)-DWORD(p+5);}
bool write(BYTE* p,const BYTE* from,const BYTE* to,unsigned n){if(memcmp(p,from,n))return false;DWORD old;if(!VirtualProtect(p,n,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(p,to,n);FlushInstructionCache(GetCurrentProcess(),p,n);DWORD ignored;bool ok=VirtualProtect(p,n,old,&ignored)!=0;if(!ok){memcpy(p,from,n);FlushInstructionCache(GetCurrentProcess(),p,n);VirtualProtect(p,n,old,&ignored);}return ok;}
bool set(BYTE* p,bool on,void(*logger)(const wchar_t*)){
 if(!readable(p,size))return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<64||d->e_lfanew>4096)return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);
 if(n->Signature!=IMAGE_NT_SIGNATURE||n->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||n->FileHeader.TimeDateStamp!=0x3ed73966||n->OptionalHeader.SizeOfImage!=size)return false;
 BYTE target[9];memset(target,0x90,9);target[0]=0xe9;*reinterpret_cast<DWORD*>(target+1)=DWORD(&hook)-DWORD(p+site+5);
 bool clean=!memcmp(p+site,prefix,9),ours=engine==p&&bridge&&!memcmp(p+site,target,9);
 if(!clean&&!ours)return false;if(on&&ours)return true;if(!on&&clean)return true;
 if(on){auto b=static_cast<BYTE*>(VirtualAlloc(nullptr,14,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));if(!b)return false;
  memcpy(b,prefix,9);jump(b+9,p+site+9);DWORD old;if(!VirtualProtect(b,14,PAGE_EXECUTE_READ,&old)){VirtualFree(b,0,MEM_RELEASE);return false;}FlushInstructionCache(GetCurrentProcess(),b,14);
  engine=p;bridge=b;trace=logger;notices=0;
#ifndef COLLISION_GUARD_TEST
  original=reinterpret_cast<Physics>(b);point=reinterpret_cast<Point>(p+0x8a6a4);synchronize=reinterpret_cast<Position>(p+0x4cc88);
#endif
  if(!write(p+site,prefix,target,9)){VirtualFree(b,0,MEM_RELEASE);engine=bridge=nullptr;return false;}
  if(trace)trace(L"COLLISION_GUARD_READY scope=exploration_player native_physics=retained offsets=native8 clearance_step=15 recovery_max=16 map_specific=false candidate=true");
 }else{if(!write(p+site,target,prefix,9))return false;VirtualFree(bridge,0,MEM_RELEASE);engine=bridge=nullptr;trace=nullptr;}return true;
}
}
bool installCollisionGuard(HMODULE m,void(*logger)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(m),true,logger);}
bool removeCollisionGuard(HMODULE m){return set(reinterpret_cast<BYTE*>(m),false,nullptr);}
#ifdef COLLISION_GUARD_TEST
void initializeCollisionGuardFixture(BYTE* p){memset(p,0,size);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->FileHeader.TimeDateStamp=0x3ed73966;n->OptionalHeader.SizeOfImage=size;memcpy(p+site,prefix,9);}
void configureCollisionGuardFixture(Physics f,Point p,Position s){original=f;point=p;synchronize=s;}
void invokeCollisionGuardFixture(void* p){reinterpret_cast<Physics>(engine+site)(p);}
#endif
