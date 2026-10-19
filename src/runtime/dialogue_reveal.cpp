#include "dialogue_reveal.h"
#include <cstring>
namespace {
constexpr unsigned imageSize=0x10b000;
constexpr unsigned tables[]={0xbfcec,0xbfee4};
constexpr BYTE updatePrefix[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc,0x8b,0x4d,0xfc,0xe8,0x35,0xa8,0xff,0xff};
constexpr BYTE revealPrefix[]={0x81,0xec,0x94,0,0,0,0x89,0x8d,0x78,0xff,0xff,0xff,0x8b,0x85,0x78,0xff,0xff,0xff,0x83,0xb8,0xbc,1,0,0,1};
using Event=int(__thiscall*)(void*,void*,int,int,int);
using Tick=void(__thiscall*)(void*);
BYTE* engine=nullptr;Event originalEvent=nullptr;Tick originalTick=nullptr,originalReveal=nullptr;
BYTE* paused=nullptr;DWORD pausedSource=0;void(*trace)(const wchar_t*)=nullptr;
int& field(BYTE* p,unsigned off){return *reinterpret_cast<int*>(p+off);}
bool readable(void* p,size_t n){
 auto current=reinterpret_cast<ULONG_PTR>(p);
 if(!current||!n||n>~ULONG_PTR(0)-current)return false;
 const auto end=current+n;
 while(current<end){
  MEMORY_BASIC_INFORMATION m{};
  if(!VirtualQuery(reinterpret_cast<void*>(current),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  const DWORD access=m.Protect&0xff;
  if(access!=PAGE_READONLY&&access!=PAGE_READWRITE&&access!=PAGE_WRITECOPY&&access!=PAGE_EXECUTE_READ&&access!=PAGE_EXECUTE_READWRITE&&access!=PAGE_EXECUTE_WRITECOPY)return false;
  const auto base=reinterpret_cast<ULONG_PTR>(m.BaseAddress);
  if(m.RegionSize>~ULONG_PTR(0)-base)return false;
  const auto next=base+m.RegionSize;if(next<=current)return false;
  current=next<end?next:end;
 }
 return true;
}
bool isPaused(BYTE* p){if(paused!=p)return false;if(field(p,0x190)==4&&DWORD(field(p,0x1e0))==pausedSource)return true;paused=nullptr;return false;}
void __fastcall tickHook(BYTE* p,void*){if(!isPaused(p))originalTick(p);}
int __fastcall eventHook(BYTE* p,void*,void* sender,int event,int a,int b){
 if(sender!=p||(event!=0x14&&event!=0x3b)||!readable(p,0x200))return originalEvent(p,sender,event,a,b);
 if(isPaused(p)){paused=nullptr;return 1;}
 if(field(p,0x190)!=2&&field(p,0x190)!=4)return originalEvent(p,sender,event,a,b);
 // Use the engine's own layout/control-code processor. Stop at the next full
 // viewport, not the final tail of a long scrolling dialogue.
 int speed=field(p,0x1cc);field(p,0x1cc)=32767;
 unsigned steps=0;
 __try {
  while(field(p,0x190)==2&&steps<4096){originalReveal(p);++steps;}
  if(field(p,0x190)==4&&field(p,0x1bc)==1){originalReveal(p);++steps;}
 } __finally {field(p,0x1cc)=speed;}
 field(p,0x1c0)=0;
 if(field(p,0x190)==4){paused=p;pausedSource=DWORD(field(p,0x1e0));}
 if(trace){wchar_t line[180];wsprintfW(line,L"DIALOGUE_REVEAL steps=%u phase=%d page_paused=%d consumed=true",steps,field(p,0x190),paused==p);trace(line);}
 return 1;
}
bool write(DWORD* p,DWORD from,DWORD to){if(*p!=from)return false;DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;*p=to;DWORD ignored;if(!VirtualProtect(p,4,old,&ignored)){*p=from;VirtualProtect(p,4,old,&ignored);return false;}return true;}
bool set(BYTE* p,bool on,void(*logger)(const wchar_t*)){
 // PE sections have independent page protections, and discarded sections may
 // be unreadable. Check only the exact headers/code/slots used by this hook.
 if(!readable(p,sizeof(IMAGE_DOS_HEADER)))return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096)return false;
 if(!readable(p+d->e_lfanew,sizeof(IMAGE_NT_HEADERS32)))return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);if(n->Signature!=IMAGE_NT_SIGNATURE||n->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||n->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||n->OptionalHeader.SizeOfImage!=imageSize)return false;
 if(!readable(p+0x5b1c5,sizeof(updatePrefix))||!readable(p+0x5b9c7,sizeof(revealPrefix))||!readable(p+0x5c277,0x5c306-0x5c277))return false;
 for(auto table:tables)if(!readable(p+table+4,4)||!readable(p+table+36,4))return false;
 if(memcmp(p+0x5b1c5,updatePrefix,sizeof(updatePrefix))||memcmp(p+0x5b9c7,revealPrefix,sizeof(revealPrefix)))return false;
 unsigned hash=2166136261u;for(unsigned i=0x5c277;i<0x5c306;++i)hash=(hash^p[i])*16777619u;
#ifndef DIALOGUE_REVEAL_TEST
 if(hash!=0xfb170950u)return false;
#endif
 unsigned rvas[]={tables[0]+4,tables[0]+36,tables[1]+4,tables[1]+36};
 DWORD native[]={DWORD(p+0x5b1c5),DWORD(p+0x5c277),DWORD(p+0x5b1c5),DWORD(p+0x5c277)};
 DWORD hooks[]={DWORD(&tickHook),DWORD(&eventHook),DWORD(&tickHook),DWORD(&eventHook)};
 bool allBase=true,allHook=true;for(unsigned i=0;i<4;++i){DWORD v=*reinterpret_cast<DWORD*>(p+rvas[i]);allBase&=v==native[i];allHook&=v==hooks[i];}
 if(!allBase&&!(allHook&&engine==p))return false;if(on&&allHook)return true;if(!on&&allBase)return true;
 if(on){engine=p;trace=logger;paused=nullptr;
#ifndef DIALOGUE_REVEAL_TEST
 originalTick=reinterpret_cast<Tick>(p+0x5b1c5);originalEvent=reinterpret_cast<Event>(p+0x5c277);originalReveal=reinterpret_cast<Tick>(p+0x5b9af);
#endif
 }
 unsigned done=0;for(;done<4;++done)if(!write(reinterpret_cast<DWORD*>(p+rvas[done]),on?native[done]:hooks[done],on?hooks[done]:native[done])){for(unsigned j=0;j<done;++j)write(reinterpret_cast<DWORD*>(p+rvas[j]),on?hooks[j]:native[j],on?native[j]:hooks[j]);return false;}
 if(!on)paused=nullptr;if(on&&trace)trace(L"DIALOGUE_REVEAL_READY mouse=left_press keyboard=space_release native_page_boundary=preserved");return true;
}
}
bool installDialogueReveal(HMODULE m,void(*l)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(m),true,l);}
bool removeDialogueReveal(HMODULE m){return set(reinterpret_cast<BYTE*>(m),false,nullptr);}
#ifdef DIALOGUE_REVEAL_TEST
void initializeDialogueRevealFixture(BYTE* p){memset(p,0,imageSize);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=imageSize;memcpy(p+0x5b1c5,updatePrefix,sizeof(updatePrefix));memcpy(p+0x5b9c7,revealPrefix,sizeof(revealPrefix));for(auto t:tables){*reinterpret_cast<DWORD*>(p+t+4)=DWORD(p+0x5b1c5);*reinterpret_cast<DWORD*>(p+t+36)=DWORD(p+0x5c277);}}
void configureDialogueRevealFixture(Event e,Tick t,Tick r){originalEvent=e;originalTick=t;originalReveal=r;}
#endif
