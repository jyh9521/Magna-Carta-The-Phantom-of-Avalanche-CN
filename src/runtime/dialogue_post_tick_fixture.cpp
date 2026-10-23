// Owned robustness fixture for the captured post-update field-pointer fault.
#include "dialogue_reveal.h"
#include <cstdio>
#include <cstring>
#include <initializer_list>
static unsigned targetPhase=2,calls=0;
static unsigned begins=0,ends=0;
static int& field(BYTE* p,unsigned off){return *reinterpret_cast<int*>(p+off);}
static void capture(const wchar_t* line){if(wcsstr(line,L"stage=begin"))++begins;if(wcsstr(line,L"stage=end")&&wcsstr(line,L"reason=confirmed"))++ends;}
static void __fastcall play(BYTE* p,void*){field(p,0x124)=2;}
static int __fastcall playing(void*,void*,int){return 1;}
// Deliberately reproduce the captured post-call ESI=0 condition, not its origin.
__declspec(naked) void __fastcall nativeCallback(BYTE*,void*){__asm {
 mov eax,targetPhase
 mov dword ptr[ecx+190h],eax
 inc calls
 xor esi,esi
 ret
}}
static void __fastcall noReveal(BYTE*,void*){}
static int __fastcall noEvent(void*,void*,void*,int,int,int){return 0;}
using Tick=void(__thiscall*)(void*);
static int faultCode=0;static ULONG_PTR faultAddress=0;
static int recordFault(EXCEPTION_POINTERS* p){faultCode=p->ExceptionRecord->ExceptionCode;faultAddress=p->ExceptionRecord->ExceptionInformation[1];return EXCEPTION_EXECUTE_HANDLER;}
static bool invoke(Tick t,BYTE* object){
 __try {t(object);return true;}
 __except(recordFault(GetExceptionInformation())){return false;}
}
int main(){
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 auto engine=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
 if(!engine)return 2;
 initializeDialogueRevealFixture(engine);
 configureDialogueRevealFixture(reinterpret_cast<int(__thiscall*)(void*,void*,int,int,int)>(&noEvent),reinterpret_cast<Tick>(&nativeCallback),reinterpret_cast<Tick>(&noReveal));
 BYTE original[0x400],originalCall[5];memcpy(original,engine+0xbfc00,sizeof(original));memcpy(originalCall,engine+0x5afee,5);
 if(!installDialogueReveal(HMODULE(engine),capture))return 3;
 auto tick=reinterpret_cast<Tick>(*reinterpret_cast<DWORD*>(engine+0xbfcf0));
 BYTE object[0x200]{};unsigned failures=0;
 for(unsigned phase: {2u,3u,6u}){
  targetPhase=phase;*reinterpret_cast<unsigned*>(object+0x190)=2;
  bool ok=invoke(tick,object);
  if(!ok||*reinterpret_cast<unsigned*>(object+0x190)!=phase)++failures;
  printf("POST_TICK phase=%u native_calls=%u callback_esi=0 result=%s exception=%08x access=%p\n",phase,calls,ok?"PASS":"FAIL",unsigned(faultCode),reinterpret_cast<void*>(faultAddress));
 }
 BYTE voice[0x134]{},resource[8]{},audio[0x60]{},streams[12]{};
 field(audio,0x54)=DWORD(streams);field(audio,0x58)=1;field(streams,4)=1;
 field(voice,0)=DWORD(engine+0xbe620);field(voice,0x120)=DWORD(resource);
 configureDialogueVoiceFixture(reinterpret_cast<Tick>(&play),reinterpret_cast<int(__thiscall*)(void*,int)>(&playing),audio);
 field(object,0x190)=3;field(object,0x1d0)=0;field(object,0x1e0)=123;
 startDialogueVoiceFixture(voice,object,300);targetPhase=6;
 bool cleanup=invoke(tick,object)&&begins==1&&ends==1&&field(object,0x1d0)==0;
 if(!cleanup)++failures;
 printf("POST_TICK_VOICE waiting_begin=%u confirmed_end=%u timer=%d result=%s\n",begins,ends,field(object,0x1d0),cleanup?"PASS":"FAIL");
 bool restored=removeDialogueReveal(HMODULE(engine));
 restored=restored&&!memcmp(original,engine+0xbfc00,sizeof(original))&&!memcmp(originalCall,engine+0x5afee,5);
 printf("DIALOGUE_POST_TICK checks=4 failures=%u rollback=%s game_started=false\n",failures,restored?"exact":"failed");
 VirtualFree(engine,0,MEM_RELEASE);return failures||!restored?1:0;
}
