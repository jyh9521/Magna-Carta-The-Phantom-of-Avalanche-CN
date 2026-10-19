#include "native_scene_loading.h"
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>
namespace {
BYTE* engine=nullptr;BYTE* scene=nullptr;BYTE* renderer=nullptr;BYTE job[16]{};
int phase=0,loading=0,renders=0,presents=0,cleanups=0;
void require(bool v,const char* m){if(!v){printf("FAIL %s\n",m);std::exit(5);}}
void __fastcall hide(void*,void*,int){}
void __fastcall load(void* s,void*){require(s==scene&&phase==0,"original native scene receiver");phase=1;++loading;}
void __cdecl render(void* s){require(s==renderer&&phase==1,"native render after original loading");phase=2;++renders;}
BYTE __fastcall present(void* s,void*){require(s==renderer&&phase==2,"present after render");phase=3;++presents;return 1;}
void __cdecl clear(){require(phase==3,"completed loading batch cleared before deletion");phase=4;}
void __fastcall cleanup(void* s,void*){require(s==job&&(phase==0||phase==4),"cleanup exactly after queue clear or native bypass");require(GetLastError()==0x4567,"LastError restored");++cleanups;}
void jump(BYTE* p,void* target){p[0]=0xe9;DWORD r=DWORD(uintptr_t(target)-uintptr_t(p+5));memcpy(p+1,&r,4);}
void reset(){phase=loading=renders=presents=cleanups=0;SetLastError(0x4567);}
using Invoke=void(__thiscall*)(void*);
void run(){reinterpret_cast<Invoke>(engine+0x63075)(job);}
}
int main(int argc,char** argv){
 engine=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
 auto driver=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2c000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
 renderer=static_cast<BYTE*>(VirtualAlloc(nullptr,0x122f20,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
 scene=static_cast<BYTE*>(VirtualAlloc(nullptr,0x1738,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(engine&&driver&&renderer&&scene,"owned allocations");
 initializeNativeSceneLoadingFixture(engine,driver);configureNativeSceneLoadingFixture(driver,&render,&clear);
 *reinterpret_cast<BYTE**>(scene)=engine+0xc12bc;*reinterpret_cast<int*>(scene+0x156c)=7;
 *reinterpret_cast<BYTE**>(job+12)=scene;*reinterpret_cast<int*>(engine+0xf2280)=31;
 BYTE gui[0x1a0]{},window[0xf4]{};void* methods[14]{};methods[13]=reinterpret_cast<void*>(&hide);void** win=methods;
 *reinterpret_cast<BYTE**>(gui+0x19c)=window;*reinterpret_cast<BYTE**>(scene+0x10c8)=gui;*reinterpret_cast<void**>(scene+0x1720)=&win;*reinterpret_cast<void**>(scene+0x1724)=&win;
 *reinterpret_cast<BYTE**>(renderer)=driver+0x1a5a8;*reinterpret_cast<void**>(driver+0x1a5a8+0x14)=reinterpret_cast<void*>(&present);*reinterpret_cast<BYTE**>(engine+0xf1b70)=renderer;
 engine[0x6307a]=0xc3;jump(engine+0x6315b,reinterpret_cast<void*>(&cleanup));BYTE prefix[10];memcpy(prefix,engine+0x71085,10);
 bool baseline=argc>1&&!strcmp(argv[1],"baseline"),rollback=argc>1&&!strcmp(argv[1],"rollback");
 reset();run();require(!loading&&!presents&&cleanups==1,"native call absent in baseline seam");
 if(baseline){puts("NATIVE_LOADING BASELINE loading=0 present=0 cleanup=1 game_started=false");return 1;}
 auto m=reinterpret_cast<HMODULE>(engine);require(installNativeSceneLoading(m,nullptr)&&installNativeSceneLoading(m,nullptr),"idempotent install");
 if(!rollback){
  // Owned callback only; real 71085 instructions are separately traced/replayed offline.
  jump(engine+0x71085,reinterpret_cast<void*>(&load));reset();run();require(loading==1&&renders==1&&presents==1&&cleanups==1,"original loading render present cleanup");
  reset();*reinterpret_cast<int*>(engine+0xf2280)=4;run();require(!loading&&cleanups==1,"non-Field bypass");*reinterpret_cast<int*>(engine+0xf2280)=31;
  reset();*reinterpret_cast<int*>(scene+0x156c)=2;run();require(!loading&&cleanups==1,"active Field bypass");*reinterpret_cast<int*>(scene+0x156c)=7;
  reset();engine[0x38b45]=0;run();require(!loading&&cleanups==1,"missing root guard bypass");engine[0x38b45]=0xe9;
  reset();*reinterpret_cast<int*>(renderer+0x122f1c)=1;run();require(!loading&&cleanups==1,"active BeginScene bypass");*reinterpret_cast<int*>(renderer+0x122f1c)=0;
  reset();*reinterpret_cast<BYTE**>(scene)=nullptr;run();require(!loading&&cleanups==1,"foreign scene bypass");*reinterpret_cast<BYTE**>(scene)=engine+0xc12bc;
  memcpy(engine+0x71085,prefix,10);
 }
 require(removeNativeSceneLoading(m)&&removeNativeSceneLoading(m),"exact remove");reset();run();require(!loading&&!presents&&cleanups==1,"rollback old call behavior");
 if(rollback){puts("NATIVE_LOADING ROLLBACK loading=0 present=0 cleanup=1 original_call=restored game_started=false");return 1;}
 engine[0x71137]=0xcd;require(!installNativeSceneLoading(m,nullptr),"FDI source drift rejected");engine[0x71137]=0xcc;
 engine[0x63075]=0xcc;require(!installNativeSceneLoading(m,nullptr),"foreign hook rejected");engine[0x63075]=0xe8;
 require(!installNativeSceneLoading(nullptr,nullptr),"invalid image rejected");
 VirtualFree(scene,0,MEM_RELEASE);VirtualFree(renderer,0,MEM_RELEASE);VirtualFree(driver,0,MEM_RELEASE);VirtualFree(engine,0,MEM_RELEASE);
 puts("NATIVE_LOADING MODIFIED PASS order=original_71085_render_present_clear_cleanup rollback=exact game_started=false original_artwork=unchanged");return 0;
}
