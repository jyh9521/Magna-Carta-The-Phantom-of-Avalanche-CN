#include "dialogue_reveal.h"
#include <cstring>
#include <vector>
namespace {
constexpr unsigned imageSize=0x10b000;
constexpr unsigned tables[]={0xbfcec,0xbfee4};
constexpr BYTE updatePrefix[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc,0x8b,0x4d,0xfc,0xe8,0x35,0xa8,0xff,0xff};
constexpr BYTE revealPrefix[]={0x81,0xec,0x94,0,0,0,0x89,0x8d,0x78,0xff,0xff,0xff,0x8b,0x85,0x78,0xff,0xff,0xff,0x83,0xb8,0xbc,1,0,0,1};
using Event=int(__thiscall*)(void*,void*,int,int,int);
using Tick=void(__thiscall*)(void*);
using Playing=int(__thiscall*)(void*,int);
constexpr unsigned voiceCallRva=0x5afee;
constexpr BYTE nativeVoiceCall[]={0xe8,0xd8,0xee,0xfe,0xff};
constexpr BYTE playingPrefix[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xf8,0x8b,0x45,0x08,0x50,0x8b,0x4d,0xf8};
Tick originalVoice=nullptr;Playing originalPlaying=nullptr;
struct Voice {BYTE* dialogue;DWORD source;BYTE* object;DWORD resource;int channel;DWORD stream;ULONGLONG deadline;bool waiting;};
std::vector<Voice> voices;
#ifdef DIALOGUE_REVEAL_TEST
void* audioFixture=nullptr;
#endif
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
void* audioManager(){
#ifdef DIALOGUE_REVEAL_TEST
 return audioFixture;
#else
 return engine&&readable(engine+0xf2204,4)?*reinterpret_cast<void**>(engine+0xf2204):nullptr;
#endif
}
DWORD voiceStream(void* audio,int channel){
 auto a=static_cast<BYTE*>(audio);if(!readable(a,0x5c)||channel<0||channel>=field(a,0x58))return 0;
 auto slots=static_cast<ULONG_PTR>(DWORD(field(a,0x54)));
 auto offset=static_cast<ULONG_PTR>(channel)*12+4;if(slots>~ULONG_PTR(0)-offset)return 0;
 auto handle=reinterpret_cast<BYTE*>(slots+offset);return readable(handle,4)?DWORD(field(handle,0)):0;
}
void voiceWaitTrace(const Voice& voice,const wchar_t* stage,const wchar_t* reason){
 if(trace){wchar_t line[180];wsprintfW(line,L"DIALOGUE_VOICE_WAIT channel=%d stage=%s reason=%s",voice.channel,stage,reason);trace(line);}
}
bool voicePlaying(BYTE* p){
 for(auto i=voices.begin();i!=voices.end();){
  if(i->dialogue!=p){++i;continue;}
  if(i->source!=DWORD(field(p,0x1e0))||field(p,0x190)==6||GetTickCount64()>=i->deadline||
     !readable(i->object,0x134)||!readable(reinterpret_cast<void*>(i->resource),8)||
     DWORD(field(i->object,0))!=DWORD(engine+0xbe620)||DWORD(field(i->object,0x120))!=i->resource||field(i->object,0x124)!=2||
     field(reinterpret_cast<BYTE*>(i->resource),4)!=i->channel){if(i->waiting)voiceWaitTrace(*i,L"end",L"identity_or_lifetime");i=voices.erase(i);continue;}
  void* audio=audioManager();if(!i->stream||voiceStream(audio,i->channel)!=i->stream){if(i->waiting)voiceWaitTrace(*i,L"end",L"stream_changed");voices.erase(i);return false;}
  bool playing=audio&&originalPlaying&&originalPlaying(audio,i->channel)>0;
  if(playing&&!i->waiting)voiceWaitTrace(*i,L"begin",L"automatic_expiry");
  if(!playing&&i->waiting)voiceWaitTrace(*i,L"end",L"playback_complete");
  i->waiting=playing;return playing;
 }
 return false;
}
void __fastcall voiceStartHook(BYTE* object,BYTE* dialogue,int duration){
 for(auto i=voices.begin();i!=voices.end();)if(i->dialogue==dialogue)i=voices.erase(i);else ++i;
 originalVoice(object);
 if(!readable(dialogue,0x200)||!readable(object,0x134)||DWORD(field(object,0))!=DWORD(engine+0xbe620)||duration<=0||duration>30*60*30)return;
 auto resource=DWORD(field(object,0x120));if(!readable(reinterpret_cast<void*>(resource),8)||field(object,0x124)!=2)return;
 int channel=field(reinterpret_cast<BYTE*>(resource),4);DWORD stream=voiceStream(audioManager(),channel);if(channel<0||!stream)return;
 for(auto i=voices.begin();i!=voices.end();)if(i->dialogue==dialogue||i->channel==channel)i=voices.erase(i);else ++i;
 if(voices.size()>=64)voices.erase(voices.begin());
 voices.push_back({dialogue,DWORD(field(dialogue,0x1e0)),object,resource,channel,stream,
                   GetTickCount64()+ULONGLONG(duration)*34+3000,false});
}
// The guarded native call site is inside the original constructor frame.
// Capture both values before entering an ordinary C++ stack frame.
__declspec(naked) void voiceStartBridge(){__asm {
 push dword ptr [ebp-2ch]
 mov edx,dword ptr [ebp-64h]
 call voiceStartHook
 ret
}}
// Recompute the interior field address after the engine callback. The captured
// continue-game fault had a valid dialogue object but a null cached phase
// pointer in ESI. Keep this boundary out of line so /O2 cannot hoist that
// address across the callback again; do not skip the native update or cleanup.
__declspec(noinline) void finishTick(BYTE* p){
 if(readable(p,0x200)&&field(p,0x190)==6)
  for(auto i=voices.begin();i!=voices.end();)if(i->dialogue==p){if(i->waiting)voiceWaitTrace(*i,L"end",L"confirmed");i=voices.erase(i);}else ++i;
}
void __fastcall tickHook(BYTE* p,void*){
 // Keep the object itself in a stack slot too: changing the helper alone can
 // make the optimizer reuse ESI for p instead of for p+0x190.
 BYTE* volatile afterTick=p;
 if(isPaused(p))return;
 if(readable(p,0x200)&&field(p,0x190)==3&&field(p,0x1d0)==0&&voicePlaying(p)){
  // Only suppress automatic expiry; native input dispatch still runs and a
  // genuine confirmation may set phase 6 during this very update.
  field(p,0x1d0)=-1;
  __try {originalTick(p);} __finally {field(afterTick,0x1d0)=0;}
 }else originalTick(p);
 finishTick(afterTick);
}
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
bool codeWrite(BYTE* p,const BYTE* from,const BYTE* to){
 if(memcmp(p,from,5))return false;DWORD old;if(!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old))return false;
 memcpy(p,to,5);bool ok=FlushInstructionCache(GetCurrentProcess(),p,5)!=FALSE;
 if(!ok)memcpy(p,from,5);DWORD ignored;
 if(!VirtualProtect(p,5,old,&ignored)){memcpy(p,from,5);FlushInstructionCache(GetCurrentProcess(),p,5);VirtualProtect(p,5,old,&ignored);return false;}return ok;
}
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
 if(!readable(p+voiceCallRva-3,8)||memcmp(p+voiceCallRva-3,"\x8b\x4d\xe0",3)||!readable(p+0x6329,sizeof(playingPrefix))||memcmp(p+0x6329,playingPrefix,sizeof(playingPrefix)))return false;
 BYTE voiceHook[5]={0xe8};*reinterpret_cast<DWORD*>(voiceHook+1)=DWORD(&voiceStartBridge)-DWORD(p+voiceCallRva+5);
 bool voiceBase=!memcmp(p+voiceCallRva,nativeVoiceCall,5),voiceInstalled=!memcmp(p+voiceCallRva,voiceHook,5);
 unsigned rvas[]={tables[0]+4,tables[0]+36,tables[1]+4,tables[1]+36};
 DWORD native[]={DWORD(p+0x5b1c5),DWORD(p+0x5c277),DWORD(p+0x5b1c5),DWORD(p+0x5c277)};
 DWORD hooks[]={DWORD(&tickHook),DWORD(&eventHook),DWORD(&tickHook),DWORD(&eventHook)};
 bool allBase=true,allHook=true;for(unsigned i=0;i<4;++i){DWORD v=*reinterpret_cast<DWORD*>(p+rvas[i]);allBase&=v==native[i];allHook&=v==hooks[i];}
 allBase&=voiceBase;allHook&=voiceInstalled;if(!allBase&&!(allHook&&engine==p))return false;if(on&&allHook)return true;if(!on&&allBase)return true;
 if(on){engine=p;trace=logger;paused=nullptr;voices.clear();
#ifndef DIALOGUE_REVEAL_TEST
 originalVoice=reinterpret_cast<Tick>(p+0x49ecb);originalPlaying=reinterpret_cast<Playing>(p+0x6329);originalTick=reinterpret_cast<Tick>(p+0x5b1c5);originalEvent=reinterpret_cast<Event>(p+0x5c277);originalReveal=reinterpret_cast<Tick>(p+0x5b9af);
#endif
 }
 unsigned done=0;for(;done<4;++done)if(!write(reinterpret_cast<DWORD*>(p+rvas[done]),on?native[done]:hooks[done],on?hooks[done]:native[done])){for(unsigned j=0;j<done;++j)write(reinterpret_cast<DWORD*>(p+rvas[j]),on?hooks[j]:native[j],on?native[j]:hooks[j]);return false;}
 if(!codeWrite(p+voiceCallRva,on?nativeVoiceCall:voiceHook,on?voiceHook:nativeVoiceCall)){
  for(unsigned j=0;j<4;++j)write(reinterpret_cast<DWORD*>(p+rvas[j]),on?hooks[j]:native[j],on?native[j]:hooks[j]);return false;
 }
 if(!on){paused=nullptr;voices.clear();}if(on&&trace)trace(L"DIALOGUE_REVEAL_READY mouse=left_press keyboard=space_release native_page_boundary=preserved");return true;
}
}
bool installDialogueReveal(HMODULE m,void(*l)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(m),true,l);}
bool removeDialogueReveal(HMODULE m){return set(reinterpret_cast<BYTE*>(m),false,nullptr);}
#ifdef DIALOGUE_REVEAL_TEST
void initializeDialogueRevealFixture(BYTE* p){memset(p,0,imageSize);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=imageSize;memcpy(p+voiceCallRva-3,"\x8b\x4d\xe0",3);memcpy(p+voiceCallRva,nativeVoiceCall,5);memcpy(p+0x6329,playingPrefix,sizeof(playingPrefix));memcpy(p+0x5b1c5,updatePrefix,sizeof(updatePrefix));memcpy(p+0x5b9c7,revealPrefix,sizeof(revealPrefix));for(auto t:tables){*reinterpret_cast<DWORD*>(p+t+4)=DWORD(p+0x5b1c5);*reinterpret_cast<DWORD*>(p+t+36)=DWORD(p+0x5c277);}}
void configureDialogueRevealFixture(Event e,Tick t,Tick r){originalEvent=e;originalTick=t;originalReveal=r;}
void configureDialogueVoiceFixture(Tick start,Playing playing,void* audio){originalVoice=start;originalPlaying=playing;audioFixture=audio;}
void startDialogueVoiceFixture(BYTE* voice,BYTE* dialogue,int duration){voiceStartHook(voice,dialogue,duration);}
#endif
