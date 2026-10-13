#include "world_gamepad.h"
#include "modern_gamepad.h"
#include "camera_relative_input.h"
#include <intrin.h>
#include <cstring>
#include <cmath>
namespace {
using Tick=void(__thiscall*)(void*);
using SceneEvent=int(__thiscall*)(void*,void*,unsigned);
struct Vector {float x,y,z;};
using Direction=void(__thiscall*)(void*,Vector);
BYTE* engine=nullptr;Tick originalTick=nullptr,originalForward=nullptr;Direction originalDirection=nullptr;
thread_local BYTE* scene=nullptr;
WorldTickObserver observer=nullptr;
void(*trace)(const wchar_t*)=nullptr;
bool readable(const void* a,size_t n){
 auto p=reinterpret_cast<ULONG_PTR>(a),end=p+n;if(!p||end<p)return false;
 while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;
}
bool controllable(BYTE* s){
 if(!engine||!readable(s,0x15c4)||*reinterpret_cast<ULONG_PTR*>(s)!=reinterpret_cast<ULONG_PTR>(engine+0xc12bc))return false;
 auto gui=*reinterpret_cast<BYTE**>(s+0x10c8),actor=*reinterpret_cast<BYTE**>(s+0x1564);
 auto manager=*reinterpret_cast<BYTE**>(engine+0xf220c);if(readable(manager,0x3c)&&*reinterpret_cast<int*>(manager+0x38)>0)return false;
 return readable(gui,0x194)&&*reinterpret_cast<int*>(gui+0x190)==1&&readable(actor,0x340)
  &&*reinterpret_cast<ULONG_PTR*>(actor)==reinterpret_cast<ULONG_PTR>(engine+0xc11e4)&&*reinterpret_cast<BYTE**>(actor+0x20)==s;
}
void __fastcall tickHook(void* value,void*){
 BYTE* previous=scene;scene=static_cast<BYTE*>(value);modernGamepadWorldScope(controllable(scene));
 __try {
  originalTick(value);
  if(modernGamepadConsumeInteraction()&&controllable(scene)){
   auto gui=*reinterpret_cast<BYTE**>(scene+0x10c8);
   if(*reinterpret_cast<int*>(gui+4)==0x42){
    // Original world handler receives the same exploration GUI/event pair.
    // Its own proximity/request checks remain authoritative; no scripted action is forced.
    reinterpret_cast<SceneEvent>(engine+0x6e6d8)(scene,gui,0x11);
    static LONG used=0;if(InterlockedIncrement(&used)==1&&trace)trace(L"WORLD_GAMEPAD_INTERACTION_APPLIED event=0x11 edge_only=true native_proximity=retained keyboard_space=not_injected");
   }
  }
  notifyWorldTickObserver(scene,controllable(scene));
 }
 __finally {scene=previous;modernGamepadWorldScope(scene&&controllable(scene));}
}
void __fastcall forwardHook(void* actor,void*){
 auto move=modernGamepadMoveIntent();
 bool apply=reinterpret_cast<BYTE*>(_ReturnAddress())==engine+0x6e781&&move.active&&controllable(scene)&&actor==*reinterpret_cast<void**>(scene+0x1564);
 if(apply)originalDirection(actor,{move.x,move.y,0});
 originalForward(actor);
 if(apply){
  auto velocity=reinterpret_cast<float*>(static_cast<BYTE*>(actor)+0x16c);
  if(std::isfinite(velocity[0])&&std::isfinite(velocity[1])&&std::isfinite(velocity[2]))for(int i=0;i<3;++i)velocity[i]*=move.speed;
  static LONG used=0;if(InterlockedIncrement(&used)==1&&trace)trace(L"WORLD_GAMEPAD_APPLIED direction=camera_relative ground=XY speed=analog movement_collision=native");
 }
}
bool replace(DWORD* p,DWORD a,DWORD b){
 if(*p!=a)return false;DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;
 bool ok=InterlockedCompareExchange(reinterpret_cast<LONG*>(p),b,a)==static_cast<LONG>(a);DWORD ignored;
 if(!VirtualProtect(p,4,old,&ignored)){if(ok)InterlockedCompareExchange(reinterpret_cast<LONG*>(p),a,b);VirtualProtect(p,4,old,&ignored);return false;}return ok;
}
bool set(BYTE* p,bool enabled,void(*logger)(const wchar_t*),bool dry=false){
 if(!readable(p,0x10b000))return false;auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 BYTE tickBytes[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc},forwardBytes[]={0x55,0x8b,0xec,0x83,0xec,0x54,0x89,0x4d,0xac},directionBytes[]={0x55,0x8b,0xec,0x83,0xec,0x1c,0x89,0x4d,0xec};
 if(memcmp(p+0x6b2d8,tickBytes,sizeof(tickBytes))||memcmp(p+0x652b4,forwardBytes,sizeof(forwardBytes))||memcmp(p+0x65504,directionBytes,sizeof(directionBytes)))return false;
 BYTE eventBytes[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xfc};
 if(memcmp(p+0x6e6d8,eventBytes,sizeof(eventBytes)))return false;
 BYTE call[]={0xff,0x52,0x74};if(memcmp(p+0x6e77e,call,3))return false;
 auto t=reinterpret_cast<DWORD*>(p+0xc12c0),f=reinterpret_cast<DWORD*>(p+0xc1258),d=reinterpret_cast<DWORD*>(p+0xc12a0);
 DWORD oldT=reinterpret_cast<DWORD>(p+0x6b2d8),oldF=reinterpret_cast<DWORD>(p+0x652b4),newT=reinterpret_cast<DWORD>(&tickHook),newF=reinterpret_cast<DWORD>(&forwardHook);
 if(*d!=reinterpret_cast<DWORD>(p+0x65504))return false;
 bool clean=*t==oldT&&*f==oldF,patched=*t==newT&&*f==newF&&engine==p;
 if(!clean&&!patched)return false;if(enabled&&patched)return true;if(!enabled&&clean)return true;
 if(dry)return true;
 if(enabled){engine=p;originalTick=reinterpret_cast<Tick>(oldT);originalForward=reinterpret_cast<Tick>(oldF);originalDirection=reinterpret_cast<Direction>(*d);trace=logger;}
 if(!replace(t,enabled?oldT:newT,enabled?newT:oldT))return false;
 if(!replace(f,enabled?oldF:newF,enabled?newF:oldF)){replace(t,enabled?newT:oldT,enabled?oldT:newT);return false;}
 if(enabled&&logger)logger(L"WORLD_GAMEPAD_READY player_direction=source_locked movement=native keyboard=preserved");return true;
}
}
bool installWorldGamepad(HMODULE m,void(*logger)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(m),true,logger);}
bool removeWorldGamepad(HMODULE m){return set(reinterpret_cast<BYTE*>(m),false,nullptr);}
bool canSetWorldGamepad(HMODULE m,bool enabled){return set(reinterpret_cast<BYTE*>(m),enabled,nullptr,true);}
bool worldExplorationActive(){return controllable(scene);}

void setWorldTickObserver(WorldTickObserver callback){InterlockedExchangePointer(reinterpret_cast<PVOID volatile*>(&observer),reinterpret_cast<PVOID>(callback));}
void notifyWorldTickObserver(BYTE* value,bool controlled){auto callback=reinterpret_cast<WorldTickObserver>(InterlockedCompareExchangePointer(reinterpret_cast<PVOID volatile*>(&observer),nullptr,nullptr));if(callback)callback(value,controlled);}
