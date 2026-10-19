#include "dialogue_reveal.h"
#include <cstdio>
#include <initializer_list>
#include <cstdlib>
#include <cstring>
int& f(BYTE* p,int n){return *reinterpret_cast<int*>(p+n);}
int ticks=0,reveals=0,events=0;bool full=false,stuck=false;
void check(bool v,const char* s){if(!v){printf("FAIL %s\n",s);exit(1);}}
int __fastcall event(BYTE* p,void*,void* sender,int code,int,int){++events;if(sender==p&&(code==20||code==59)&&f(p,0x190)==3){f(p,0x190)=6;return 1;}return 7;}
void __fastcall tick(BYTE*,void*){++ticks;}
void __fastcall reveal(BYTE* p,void*){++reveals;if(stuck)return;if(f(p,0x1bc)){f(p,0x1bc)=0;return;}f(p,0x190)=full?4:3;if(full)f(p,0x1bc)=1;}
using Event=int(__thiscall*)(void*,void*,int,int,int);using Tick=void(__thiscall*)(void*);
int main(){
 auto p=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));BYTE object[0x200]{};
 initializeDialogueRevealFixture(p);configureDialogueRevealFixture(reinterpret_cast<Event>(&event),reinterpret_cast<Tick>(&tick),reinterpret_cast<Tick>(&reveal));
 BYTE* copy=static_cast<BYTE*>(malloc(0x10b000));memcpy(copy,p,0x10b000);
 check(installDialogueReveal(HMODULE(p),nullptr),"install");check(installDialogueReveal(HMODULE(p),nullptr),"idempotent");
 auto e=reinterpret_cast<Event>(*reinterpret_cast<DWORD*>(p+0xbfd10));auto t=reinterpret_cast<Tick>(*reinterpret_cast<DWORD*>(p+0xbfcf0));
 for(int code:{20,59}){f(object,0x190)=2;f(object,0x1cc)=5;f(object,0x1c0)=99;check(e(object,object,code,0,0)==1,"consume reveal");check(f(object,0x190)==3&&f(object,0x1cc)==5&&!f(object,0x1c0),"complete not advance restore speed");check(e(object,object,code,0,0)==1&&f(object,0x190)==6,"separate advance");}
 full=true;f(object,0x190)=4;f(object,0x1bc)=1;check(e(object,object,20,0,0)==1&&!f(object,0x1bc),"natural scrolling pauses and completes line");e(object,object,20,0,0);f(object,0x190)=2;check(e(object,object,59,0,0)==1&&f(object,0x190)==4&&!f(object,0x1bc),"long page complete");int before=ticks;t(object);check(ticks==before,"full page paused");check(e(object,object,59,0,0)==1&&f(object,0x190)==4,"next press resumes not end");t(object);check(ticks==before+1,"native scroll resumed");
 f(object,0x190)=2;e(object,object,20,0,0);f(object,0x190)=0;t(object);check(ticks==before+2,"new dialogue resets pause");
 f(object,0x190)=2;before=reveals;check(e(object,object+4,20,0,0)==7&&reveals==before,"child sender untouched");check(e(object,object,21,0,0)==7&&reveals==before,"other event untouched");
 full=false;stuck=true;before=reveals;e(object,object,59,0,0);check(reveals-before==4096,"bounded stalled update");
 check(removeDialogueReveal(HMODULE(p)),"rollback");check(!memcmp(copy,p,0x10b000),"byte exact rollback");
 p[0x5b1c5]^=1;check(!installDialogueReveal(HMODULE(p),nullptr),"mismatch rejected");p[0x5b1c5]^=1;
 *reinterpret_cast<DWORD*>(p+0xbff08)=123;check(!installDialogueReveal(HMODULE(p),nullptr),"partial table rejected");
 puts("DIALOGUE_REVEAL_FIXTURE PASS inputs=mouse_space reveal=complete advance=separate long_page=paused_resume bounds=4096 rollback=exact guards=2 game_started=false");VirtualFree(p,0,MEM_RELEASE);free(copy);return 0;
}
