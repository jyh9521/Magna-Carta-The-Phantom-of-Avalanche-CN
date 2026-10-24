#include "contact_audio_trace.h"
#include <cstring>
#include <cwchar>
#include <intrin.h>
#include <cstdint>
namespace {
struct Vec {float x,y,z;};
using Contact=Vec*(__thiscall*)(void*,Vec*,void*,const Vec*,int,Vec,Vec*,Vec*,float,unsigned);
using Start=void(__thiscall*)(void*);
constexpr unsigned slotRva=0xc1304,contactRva=0x6ed4e,startRva=0x48e54;
constexpr BYTE contactPrefix[]={0x55,0x8b,0xec,0x81,0xec,0xf0,0,0,0,0x89,0x8d,0x10,0xff,0xff,0xff};
constexpr BYTE startPrefix[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc};
BYTE* engine=nullptr;BYTE* trampoline=nullptr;Contact originalContact=nullptr;Start originalStart=nullptr;
void(*trace)(const wchar_t*)=nullptr;
SRWLOCK budgetLock=SRWLOCK_INIT;
DWORD epoch=0;unsigned contacts=0,corrections=0,sounds=0,droppedContacts=0,droppedSounds=0;
volatile LONG serial=0;
bool readable(const void* value,size_t n){
 auto p=reinterpret_cast<uintptr_t>(value);if(!p||!n||n>~uintptr_t(0)-p)return false;auto end=p+n;
 while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  DWORD a=m.Protect&0xff;if(a!=PAGE_READONLY&&a!=PAGE_READWRITE&&a!=PAGE_WRITECOPY&&a!=PAGE_EXECUTE_READ&&a!=PAGE_EXECUTE_READWRITE&&a!=PAGE_EXECUTE_WRITECOPY)return false;
  auto next=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;
 }return true;
}
unsigned word(const void* p,unsigned off){return *reinterpret_cast<const unsigned*>(static_cast<const BYTE*>(p)+off);}
BYTE* ptr(const void* p,unsigned off){return reinterpret_cast<BYTE*>(word(p,off));}
bool admit(bool sound,DWORD now,bool changed=false){
 unsigned dc=0,ds=0;bool allowed;
 AcquireSRWLockExclusive(&budgetLock);
 if(DWORD(now-epoch)>=1000){epoch=now;contacts=corrections=sounds=0;dc=droppedContacts;ds=droppedSounds;droppedContacts=droppedSounds=0;}
 auto& count=sound?sounds:changed?corrections:contacts;auto& dropped=sound?droppedSounds:droppedContacts;
 allowed=count<(sound?128u:changed?96u:12u);if(allowed)++count;else ++dropped;
 ReleaseSRWLockExclusive(&budgetLock);
 if((dc||ds)&&trace){wchar_t line[128];swprintf_s(line,L"CONTACT_AUDIO_DROPPED contact=%u sound=%u window_ms=1000",dc,ds);trace(line);}
 return allowed;
}
Vec* __fastcall contactHook(void* scene,void*,Vec* out,void* actor,const Vec* offsets,int count,Vec position,Vec* reflected,Vec* velocity,float elasticity,unsigned extra){
 DWORD incomingError=GetLastError();
 // Observe only the native player of a field scene. Other calls still pass through.
 bool observe=readable(scene,0x1568)&&word(scene,0)==DWORD(engine+0xc12bc)&&ptr(scene,0x1564)==actor&&readable(actor,0x160)&&readable(velocity,sizeof(Vec));
 Vec before{};if(observe)before=*velocity;
 SetLastError(incomingError);auto result=originalContact(scene,out,actor,offsets,count,position,reflected,velocity,elasticity,extra);
 DWORD error=GetLastError();
 DWORD now=GetTickCount();
 bool changed=observe&&readable(result,sizeof(Vec))&&memcmp(result,&before,sizeof(Vec))!=0;
 if(observe&&trace&&admit(false,now,changed)){
  Vec output{},after{},actual{};bool valid=readable(result,sizeof(Vec))&&readable(velocity,sizeof(Vec))&&readable(actor,0x160);
  if(valid){output=*result;after=*velocity;actual=*reinterpret_cast<Vec*>(static_cast<BYTE*>(actor)+0x154);}
  wchar_t line[768];swprintf_s(line,L"CONTACT_AUDIO_CONTACT seq=%ld ms=%lu tid=%lu field=%u map=%u actor=%p offsets=%d position=%.9g,%.9g,%.9g velocity_in=%.9g,%.9g,%.9g result=%.9g,%.9g,%.9g velocity_after=%.9g,%.9g,%.9g actor_position=%.9g,%.9g,%.9g snapshot_valid=%d",
   InterlockedIncrement(&serial),now,GetCurrentThreadId(),word(scene,0x10cc),word(scene,0x10d0),actor,count,double(position.x),double(position.y),double(position.z),double(before.x),double(before.y),double(before.z),double(output.x),double(output.y),double(output.z),double(after.x),double(after.y),double(after.z),double(actual.x),double(actual.y),double(actual.z),int(valid));trace(line);
 }
 SetLastError(error);return result;
}
void occupancy(int& busy,int& capacity){
 busy=capacity=-1;if(!engine||!readable(engine+0xf2204,4))return;auto manager=ptr(engine,0xf2204);
 if(!readable(manager,0x6c))return;auto n=word(manager,0x68);auto rows=ptr(manager,0x64);
 if(n>4096||(!n&&!rows))return;if(n&&!readable(rows,size_t(n)*12))return;
 capacity=int(n);busy=0;for(unsigned i=0;i<n;++i)if(word(rows,i*12)!=0)++busy;
}
void __fastcall startHook(void* sound,void*){
 DWORD incomingError=GetLastError();
 auto caller=reinterpret_cast<uintptr_t>(_ReturnAddress());
 bool observe=readable(sound,0x134);unsigned stateBefore=observe?word(sound,0x128):~0u,channelBefore=observe?word(sound,0x120):~0u;
 SetLastError(incomingError);originalStart(sound);
 DWORD error=GetLastError();
 DWORD now=GetTickCount();
 if(observe&&trace&&admit(true,now)){
  bool valid=readable(sound,0x134);auto resource=valid?ptr(sound,0x124):nullptr;int busy,capacity;occupancy(busy,capacity);
  uintptr_t base=reinterpret_cast<uintptr_t>(engine);unsigned site=caller>=base&&caller-base<0x10b000?unsigned(caller-base):0;
  wchar_t line[512];swprintf_s(line,L"CONTACT_AUDIO_SOUND seq=%ld ms=%lu tid=%lu caller_rva=%x object=%p resource=%p state_before=%u channel_before=%d state_after=%u channel_after=%d sample_handle=%u slots_busy=%d slots_capacity=%d snapshot_valid=%d",
   InterlockedIncrement(&serial),now,GetCurrentThreadId(),site,sound,resource,stateBefore,int(channelBefore),valid?word(sound,0x128):~0u,valid?int(word(sound,0x120)):-1,readable(resource,8)?word(resource,4):~0u,busy,capacity,int(valid));trace(line);
 }
 SetLastError(error);
}
void jump(BYTE* p,const void* target){p[0]=0xe9;*reinterpret_cast<DWORD*>(p+1)=DWORD(target)-DWORD(p+5);}
bool write(BYTE* at,const BYTE* before,const BYTE* after,size_t n){
 if(memcmp(at,before,n))return false;DWORD old;
 if(!VirtualProtect(at,n,PAGE_EXECUTE_READWRITE,&old))return false;
 memcpy(at,after,n);FlushInstructionCache(GetCurrentProcess(),at,n);DWORD ignored;
 if(!VirtualProtect(at,n,old,&ignored)){memcpy(at,before,n);FlushInstructionCache(GetCurrentProcess(),at,n);VirtualProtect(at,n,old,&ignored);return false;}
 return true;
}
bool source(BYTE* p){
 if(!readable(p,64))return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<64||d->e_lfanew>4096||!readable(p+d->e_lfanew,sizeof(IMAGE_NT_HEADERS32)))return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);
 return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&n->FileHeader.TimeDateStamp==0x3ed73966&&n->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&n->OptionalHeader.SizeOfImage==0x10b000
  &&readable(p+slotRva,4)&&readable(p+contactRva,sizeof(contactPrefix))&&!memcmp(p+contactRva,contactPrefix,sizeof(contactPrefix))&&readable(p+startRva,7);
}
bool set(BYTE* p,bool enabled,void(*logger)(const wchar_t*)){
 if(!source(p)||(engine&&engine!=p))return false;
 BYTE hook[7]={};memset(hook,0x90,7);jump(hook,&startHook);*reinterpret_cast<DWORD*>(hook+1)=DWORD(&startHook)-DWORD(p+startRva+5);
 DWORD oldSlot=DWORD(p+contactRva),newSlot=DWORD(&contactHook);
 bool clean=word(p,slotRva)==oldSlot&&!memcmp(p+startRva,startPrefix,7);
 bool installed=engine==p&&trampoline&&word(p,slotRva)==newSlot&&!memcmp(p+startRva,hook,7);
 if(!clean&&!installed)return false;if(enabled&&installed)return true;if(!enabled&&clean)return true;
 if(enabled){
  auto t=static_cast<BYTE*>(VirtualAlloc(nullptr,12,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));if(!t)return false;
  memcpy(t,startPrefix,7);jump(t+7,p+startRva+7);DWORD old;
  if(!VirtualProtect(t,12,PAGE_EXECUTE_READ,&old)){VirtualFree(t,0,MEM_RELEASE);return false;}
  FlushInstructionCache(GetCurrentProcess(),t,12);engine=p;trampoline=t;originalContact=reinterpret_cast<Contact>(p+contactRva);originalStart=reinterpret_cast<Start>(t);trace=logger;
  if(!write(p+startRva,startPrefix,hook,7)){VirtualFree(t,0,MEM_RELEASE);engine=trampoline=nullptr;trace=nullptr;return false;}
  if(!write(p+slotRva,reinterpret_cast<BYTE*>(&oldSlot),reinterpret_cast<BYTE*>(&newSlot),4)){
   if(!write(p+startRva,hook,startPrefix,7))return false;
   VirtualFree(t,0,MEM_RELEASE);engine=trampoline=nullptr;trace=nullptr;return false;
  }
  epoch=GetTickCount();contacts=corrections=sounds=droppedContacts=droppedSounds=0;InterlockedExchange(&serial,0);
  if(trace)trace(L"CONTACT_AUDIO_READY diagnostic_only=true collision=passthrough sound_start=passthrough no_extra_collision_queries=true");
 }else{
  if(!write(p+slotRva,reinterpret_cast<BYTE*>(&newSlot),reinterpret_cast<BYTE*>(&oldSlot),4))return false;
  if(!write(p+startRva,hook,startPrefix,7)){write(p+slotRva,reinterpret_cast<BYTE*>(&oldSlot),reinterpret_cast<BYTE*>(&newSlot),4);return false;}
  VirtualFree(trampoline,0,MEM_RELEASE);trampoline=engine=nullptr;originalContact=nullptr;originalStart=nullptr;trace=nullptr;
 }
 return true;
}
}
bool installContactAudioTrace(HMODULE m,void(*logger)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(m),true,logger);}
bool removeContactAudioTrace(HMODULE m){return set(reinterpret_cast<BYTE*>(m),false,nullptr);}
