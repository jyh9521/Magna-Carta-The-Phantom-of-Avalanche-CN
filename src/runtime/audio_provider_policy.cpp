#include "audio_provider_policy.h"
#include <cstring>
#include <cwchar>
#include <cstdint>
namespace {
using Open=int(__stdcall*)(DWORD);
BYTE* engine=nullptr;
void(*trace)(const wchar_t*)=nullptr;
constexpr DWORD site=0x6875,iat=0xbd518;
constexpr char preferred[]="DirectSound3D 7+ Software - Pan and Volume";
const DWORD priorities[20]={9,1,0,0,8,1,0,0,3,1,0,0,2,0,0,0,4,0,0,0};
bool readable(const void* p,size_t n){
 auto at=reinterpret_cast<uintptr_t>(p);if(!at||n>UINTPTR_MAX-at)return false;
 const auto end=at+n;
 while(at<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(at),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  auto next=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;if(next<=at)return false;at=next;}
 return true;
}
DWORD& word(void* p,size_t n){return *reinterpret_cast<DWORD*>(static_cast<BYTE*>(p)+n);}
bool writable(void* p,size_t n){
 MEMORY_BASIC_INFORMATION m{};return VirtualQuery(p,&m,sizeof(m))&&m.State==MEM_COMMIT&&!(m.Protect&(PAGE_GUARD|PAGE_NOACCESS))
  &&(m.Protect&(PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY))
  &&reinterpret_cast<uintptr_t>(p)+n<=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;
}
int __stdcall selectProvider(DWORD proposed,BYTE* frame){
 DWORD incoming=GetLastError();auto original=reinterpret_cast<Open>(word(engine,iat));
 // EBP locals belong to the supported native initializer at RVA 6685.
 // Attempt the preferred provider once, at the first native iteration only.
 if(readable(frame-0x274,0x278)&&writable(frame-0x260,sizeof(priorities))
    &&word(frame-0x20c,0)==0&&!memcmp(frame-0x260,priorities,sizeof(priorities))){
  DWORD count=word(frame-0x268,0);auto manager=reinterpret_cast<BYTE*>(word(frame-0x274,0));
  if(count>0&&count<=64&&readable(manager,0x400874)&&writable(manager+0x400870,4)){
   for(DWORD i=0;i<count;++i){
    auto name=reinterpret_cast<const char*>(word(frame-0x200,i*8));DWORD provider=word(frame-0x1fc,i*8);
    if(provider&&readable(name,sizeof(preferred))&&!memcmp(name,preferred,sizeof(preferred))){
     SetLastError(incoming);int result=original(provider);DWORD error=GetLastError();
     if(result==0){
      word(frame-0x260,0)=i;word(frame-0x25c,0)=0; // native software-provider accounting
      word(manager,0x400870)=provider;
      if(trace){wchar_t line[192];swprintf_s(line,L"AUDIO_PROVIDER_POLICY_SELECTED index=%lu provider_open=0 capacity=provider_reported allocation=native",i);trace(line);}
      SetLastError(error);return 0;
     }
     if(trace){wchar_t line[160];swprintf_s(line,L"AUDIO_PROVIDER_POLICY_FALLBACK index=%lu provider_open=%d priorities=unchanged",i,result);trace(line);}
     break;
    }
   }
  }
 }
 SetLastError(incoming);return original(proposed);
}
__declspec(naked) int __stdcall providerThunk(DWORD){
 __asm{
  push ebp
  push dword ptr[esp+8]
  call selectProvider
  ret 4
 }
}
void bytes(BYTE* p,BYTE(&old)[6],BYTE(&next)[6]){
 old[0]=0xff;old[1]=0x15;*reinterpret_cast<DWORD*>(old+2)=DWORD(p+iat);
 next[0]=0xe8;*reinterpret_cast<DWORD*>(next+1)=DWORD(&providerThunk)-DWORD(p+site+5);next[5]=0x90;
}
bool source(BYTE* p){
 if(!readable(p,4096))return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<64||d->e_lfanew>3500)return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);
 const BYTE init[]={0x55,0x8b,0xec,0x81,0xec,0x78,0x02,0,0,0x89,0x8d,0x8c,0xfd,0xff,0xff};
 const BYTE alloc[]={0x55,0x8b,0xec,0x83,0xec,0x0c,0x89,0x4d,0xf4};
 return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&n->FileHeader.TimeDateStamp==0x3ed73966
  &&n->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&n->OptionalHeader.SizeOfImage==0x10b000
  &&readable(p+iat,4)&&readable(p+site,6)&&readable(p+0x6685,sizeof(init))&&readable(p+0x52ae,sizeof(alloc))
  &&!memcmp(p+0x6685,init,sizeof(init))&&!memcmp(p+0x52ae,alloc,sizeof(alloc))&&word(p,iat)!=0;
}
bool set(BYTE* p,bool enable,void(*logger)(const wchar_t*)){
 if(!source(p)||(engine&&engine!=p))return false;BYTE old[6]{},next[6]{};bytes(p,old,next);
 bool clean=!memcmp(p+site,old,6),installed=engine==p&&!memcmp(p+site,next,6);
 if(!clean&&!installed)return false;if(enable&&installed)return true;if(!enable&&clean)return true;
 DWORD protect;if(!VirtualProtect(p+site,6,PAGE_EXECUTE_READWRITE,&protect))return false;
 if(enable){engine=p;trace=logger;memcpy(p+site,next,6);}else memcpy(p+site,old,6);
 FlushInstructionCache(GetCurrentProcess(),p+site,6);DWORD ignored;
 if(!VirtualProtect(p+site,6,protect,&ignored)){memcpy(p+site,enable?old:next,6);FlushInstructionCache(GetCurrentProcess(),p+site,6);VirtualProtect(p+site,6,protect,&ignored);if(enable){engine=nullptr;trace=nullptr;}return false;}
 if(enable){if(trace)trace(L"AUDIO_PROVIDER_POLICY_READY preferred=DS3D7_software_pan_volume fallback=native pool_limit=provider_reported");}
 else {engine=nullptr;trace=nullptr;}
 return true;
}
}
bool installAudioProviderPolicy(HMODULE m,void(*logger)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(m),true,logger);}
bool removeAudioProviderPolicy(HMODULE m){return set(reinterpret_cast<BYTE*>(m),false,nullptr);}
