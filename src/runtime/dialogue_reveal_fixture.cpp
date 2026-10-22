#include "dialogue_reveal.h"
#include <cstdio>
#include <initializer_list>
#include <cstdlib>
#include <cstring>
int& f(BYTE* p,int n){return *reinterpret_cast<int*>(p+n);}
int ticks=0,reveals=0,events=0,waitBegins=0,waitEnds=0;bool full=false,stuck=false,automatic=false,playing=true,manualTick=false;
#ifdef DIALOGUE_REVEAL_BASELINE
using BaselineTick=void(__thiscall*)(void*);using BaselinePlaying=int(__thiscall*)(void*,int);
void configureDialogueVoiceFixture(BaselineTick,BaselinePlaying,void*){}
void startDialogueVoiceFixture(BYTE*,BYTE*,int){}
#endif
void __fastcall play(BYTE* p,void*){f(p,0x124)=2;}
int __fastcall isPlaying(void*,void*,int channel){return playing&&channel==7;}
void capture(const wchar_t* line){if(wcsstr(line,L"DIALOGUE_VOICE_WAIT")){if(wcsstr(line,L"stage=begin"))++waitBegins;if(wcsstr(line,L"stage=end"))++waitEnds;}}
void check(bool v,const char* s){if(!v){printf("FAIL %s\n",s);exit(1);}}
int __fastcall event(BYTE* p,void*,void* sender,int code,int,int){++events;if(sender==p&&(code==20||code==59)&&f(p,0x190)==3){f(p,0x190)=6;return 1;}return 7;}
void __fastcall tick(BYTE* p,void*){++ticks;if(automatic&&f(p,0x190)==3&&(f(p,0x1d0)==0||manualTick))f(p,0x190)=6;}
void __fastcall reveal(BYTE* p,void*){++reveals;if(stuck)return;if(f(p,0x1bc)){f(p,0x1bc)=0;return;}f(p,0x190)=full?4:3;if(full)f(p,0x1bc)=1;}
#ifndef DIALOGUE_REVEAL_BASELINE
__declspec(naked) void invokeVoiceBridge(void*,BYTE*,BYTE*,int){__asm {
 push ebp
 mov ebp,esp
 sub esp,64h
 mov eax,dword ptr [ebp+10h]
 mov dword ptr [ebp-64h],eax
 mov eax,dword ptr [ebp+14h]
 mov dword ptr [ebp-2ch],eax
 mov ecx,dword ptr [ebp+0ch]
 call dword ptr [ebp+8]
 mov esp,ebp
 pop ebp
 ret
}}
#endif
using Event=int(__thiscall*)(void*,void*,int,int,int);using Tick=void(__thiscall*)(void*);
int main(){
 auto p=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));BYTE object[0x200]{};
 initializeDialogueRevealFixture(p);configureDialogueRevealFixture(reinterpret_cast<Event>(&event),reinterpret_cast<Tick>(&tick),reinterpret_cast<Tick>(&reveal));
 BYTE* copy=static_cast<BYTE*>(malloc(0x10b000));memcpy(copy,p,0x10b000);
 check(installDialogueReveal(HMODULE(p),capture),"install");check(installDialogueReveal(HMODULE(p),nullptr),"idempotent");
 auto e=reinterpret_cast<Event>(*reinterpret_cast<DWORD*>(p+0xbfd10));auto t=reinterpret_cast<Tick>(*reinterpret_cast<DWORD*>(p+0xbfcf0));
 for(int code:{20,59}){f(object,0x190)=2;f(object,0x1cc)=5;f(object,0x1c0)=99;check(e(object,object,code,0,0)==1,"consume reveal");check(f(object,0x190)==3&&f(object,0x1cc)==5&&!f(object,0x1c0),"complete not advance restore speed");check(e(object,object,code,0,0)==1&&f(object,0x190)==6,"separate advance");}
 full=true;f(object,0x190)=4;f(object,0x1bc)=1;check(e(object,object,20,0,0)==1&&!f(object,0x1bc),"natural scrolling pauses and completes line");e(object,object,20,0,0);f(object,0x190)=2;check(e(object,object,59,0,0)==1&&f(object,0x190)==4&&!f(object,0x1bc),"long page complete");int before=ticks;t(object);check(ticks==before,"full page paused");check(e(object,object,59,0,0)==1&&f(object,0x190)==4,"next press resumes not end");t(object);check(ticks==before+1,"native scroll resumed");
 f(object,0x190)=2;e(object,object,20,0,0);f(object,0x190)=0;t(object);check(ticks==before+2,"new dialogue resets pause");
 f(object,0x190)=2;before=reveals;check(e(object,object+4,20,0,0)==7&&reveals==before,"child sender untouched");check(e(object,object,21,0,0)==7&&reveals==before,"other event untouched");
 full=false;stuck=true;before=reveals;e(object,object,59,0,0);check(reveals-before==4096,"bounded stalled update");
 BYTE voice[0x134]{},voiceResource[16]{},audio[0x60]{},streams[96]{};
 f(audio,0x54)=DWORD(streams);f(audio,0x58)=8;f(streams,7*12+4)=1;
 f(voice,0)=DWORD(p+0xbe620);f(voice,0x120)=DWORD(voiceResource);f(voiceResource,4)=7;
 configureDialogueVoiceFixture(reinterpret_cast<Tick>(&play),reinterpret_cast<int(__thiscall*)(void*,int)>(&isPlaying),audio);
 automatic=true;stuck=false;f(object,0x190)=3;f(object,0x1d0)=0;f(object,0x1e0)=123;

#ifndef DIALOGUE_REVEAL_BASELINE
 auto bridge=p+0x5afee+5+*reinterpret_cast<int*>(p+0x5afef);
 invokeVoiceBridge(bridge,voice,object,300);
#else
 startDialogueVoiceFixture(voice,object,300);
#endif
 t(object);
 check(f(object,0x190)==3&&f(object,0x1d0)==0,"autoplay must wait for still-playing original voice");
 t(object);check(waitBegins==1&&waitEnds==0,"voice wait begin logged once, not per tick");
 playing=false;t(object);check(waitEnds==1,"voice wait end logged once");check(f(object,0x190)==6,"autoplay ends when original voice stops");
 playing=true;f(object,0x190)=3;startDialogueVoiceFixture(voice,object,300);
 check(e(object,object,20,0,0)==1&&f(object,0x190)==6,"manual confirmation bypasses voice wait");t(object);
 f(object,0x190)=3;startDialogueVoiceFixture(voice,object,300);manualTick=true;t(object);manualTick=false;
 check(f(object,0x190)==6,"native input during tick bypasses voice wait");
 f(object,0x190)=3;startDialogueVoiceFixture(voice,object,300);f(object,0x1e0)=456;t(object);
 check(f(object,0x190)==6,"recycled dialogue source must not inherit voice wait");
 f(object,0x190)=3;startDialogueVoiceFixture(voice,object,300);f(voice,0x124)=5;t(object);
 check(f(object,0x190)==6,"completed or destroyed voice must not block");
 f(object,0x190)=3;startDialogueVoiceFixture(voice,object,0);t(object);
 check(f(object,0x190)==6,"invalid voice duration fails open");
 f(object,0x190)=3;f(object,0x1d0)=-1;startDialogueVoiceFixture(voice,object,300);t(object);
 check(f(object,0x190)==3&&f(object,0x1d0)==-1,"manual-wait mode preserved");
 f(object,0x190)=3;f(object,0x1d0)=0;startDialogueVoiceFixture(voice,object,300);f(streams,7*12+4)=2;t(object);
 check(f(object,0x190)==6,"recycled channel stream must not inherit voice wait");
 f(streams,7*12+4)=1;
 f(object,0x190)=3;startDialogueVoiceFixture(voice,object,1);Sleep(3100);t(object);
 check(f(object,0x190)==6,"stalled audio lifetime is bounded");
 automatic=false;
 puts("DIALOGUE_AUTOPLAY_VOICE PASS playing=held stopped=advance manual=immediate source_reuse=cleared voice_ended=cleared invalid_duration=passthrough manual_wait=preserved channel_reuse=cleared bridge=constructor_stack deadline=bounded logs=transitions_only");
 check(removeDialogueReveal(HMODULE(p)),"rollback");check(!memcmp(copy,p,0x10b000),"byte exact rollback");
 p[0x5afee]^=1;check(!installDialogueReveal(HMODULE(p),nullptr),"voice callsite mismatch rejected");p[0x5afee]^=1;
 p[0x6329]^=1;check(!installDialogueReveal(HMODULE(p),nullptr),"voice query mismatch rejected");p[0x6329]^=1;
 p[0x5b1c5]^=1;check(!installDialogueReveal(HMODULE(p),nullptr),"mismatch rejected");p[0x5b1c5]^=1;
 *reinterpret_cast<DWORD*>(p+0xbff08)=123;check(!installDialogueReveal(HMODULE(p),nullptr),"partial table rejected");
 *reinterpret_cast<DWORD*>(p+0xbff08)=DWORD(p+0x5c277);
 DWORD previous=0;
 check(VirtualProtect(p,0x1000,PAGE_READONLY,&previous)!=FALSE,"split header protection");
 check(VirtualProtect(p+0x5b000,0x2000,PAGE_EXECUTE_READ,&previous)!=FALSE,"split code protection");
 check(VirtualProtect(p+0xbf000,0x1000,PAGE_READONLY,&previous)!=FALSE,"split vtable protection");
 check(VirtualProtect(p+0x100000,0x1000,PAGE_NOACCESS,&previous)!=FALSE,"discarded unrelated section");
 check(installDialogueReveal(HMODULE(p),nullptr),"split PE sections admitted");
 check(removeDialogueReveal(HMODULE(p)),"split PE rollback");
 check(VirtualProtect(p+0xbf000,0x1000,PAGE_NOACCESS,&previous)!=FALSE,"guard target table");
 check(!installDialogueReveal(HMODULE(p),nullptr),"unreadable target table rejected");
 check(VirtualProtect(p+0xbf000,0x1000,PAGE_READONLY,&previous)!=FALSE,"restore target table");
 check(VirtualProtect(p+0x5c000,0x1000,PAGE_EXECUTE,&previous)!=FALSE,"execute-only code");
 check(!installDialogueReveal(HMODULE(p),nullptr),"execute-only target rejected");
 check(VirtualProtect(p,0x10b000,PAGE_READWRITE,&previous)!=FALSE,"restore image access");
 check(!memcmp(copy,p,0x10b000),"split image byte exact rollback");
 puts("DIALOGUE_MEMORY_REGRESSION PASS split_sections=admitted unrelated_noaccess=ignored target_noaccess=rejected execute_only=rejected rollback=exact");
 puts("DIALOGUE_REVEAL_FIXTURE PASS inputs=mouse_space reveal=complete advance=separate long_page=paused_resume bounds=4096 rollback=exact guards=2 game_started=false");VirtualFree(p,0,MEM_RELEASE);free(copy);return 0;
}
