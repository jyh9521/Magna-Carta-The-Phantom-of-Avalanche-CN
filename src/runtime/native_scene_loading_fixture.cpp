#include "native_scene_loading.h"
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <initializer_list>
namespace {
BYTE *engine=nullptr,*scene=nullptr; BYTE job[16]{};int draws=0,cleanups=0;bool expectArmed=false;
void require(bool v,const char* m){if(!v){printf("FAIL %s\n",m);std::exit(5);}}
void __fastcall hide(void*,void*,int){}
void __fastcall draw(void* s,void*){require(s==job,"original draw job receiver");++draws;require(GetLastError()==0x4567,"LastError preserved before native draw");if(expectArmed)require(*reinterpret_cast<int*>(scene+0x1730)==1,"loading flag must be armed BEFORE original draw, not after cleanup");}
void __fastcall cleanup(void* s,void*){require(s==job&&draws==1,"cleanup follows normal frame");++cleanups;}
void jump(BYTE* p,void* target){p[0]=0xe9;DWORD r=DWORD(uintptr_t(target)-uintptr_t(p+5));memcpy(p+1,&r,4);}
using Invoke=void(__thiscall*)(void*);
void run(){draws=cleanups=0;SetLastError(0x4567);reinterpret_cast<Invoke>(engine+0x631da)(job);reinterpret_cast<Invoke>(engine+0x63075)(job);}
}
int main(int argc,char** argv){
 engine=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));

 scene=static_cast<BYTE*>(VirtualAlloc(nullptr,0x1738,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(engine&&scene,"owned allocations");
 initializeNativeSceneLoadingFixture(engine);
 *reinterpret_cast<BYTE**>(scene)=engine+0xc12bc;*reinterpret_cast<int*>(scene+0x156c)=7;*reinterpret_cast<BYTE**>(job+12)=scene;*reinterpret_cast<int*>(engine+0xf2280)=31;
 BYTE gui[0x1a0]{},window[0xf4]{};void* methods[14]{};methods[13]=reinterpret_cast<void*>(&hide);void** win=methods;
 *reinterpret_cast<BYTE**>(gui+0x19c)=window;*reinterpret_cast<BYTE**>(scene+0x10c8)=gui;*reinterpret_cast<void**>(scene+0x1720)=&win;*reinterpret_cast<void**>(scene+0x1724)=&win;
 const BYTE call[]={0xe8,0x43,1,0,0};memcpy(engine+0x631da,call,5);engine[0x631df]=engine[0x6307a]=0xc3;
 jump(engine+0x63322,reinterpret_cast<void*>(&draw));jump(engine+0x6315b,reinterpret_cast<void*>(&cleanup));
 bool baseline=argc>1&&!strcmp(argv[1],"baseline"),rollback=argc>1&&!strcmp(argv[1],"rollback");
 auto m=reinterpret_cast<HMODULE>(engine);
 if(!baseline){require(installNativeSceneLoading(m,nullptr),"install");if(rollback)require(removeNativeSceneLoading(m),"remove");}
 expectArmed=!baseline&&!rollback;run();require(draws==1&&cleanups==1,"one normal draw and cleanup");
 if(baseline||rollback){require(*reinterpret_cast<int*>(scene+0x1730)==0,"original gate unchanged");printf("NATIVE_LOADING_ORDER %s flag=0 draws=1 cleanup=1 original_gate=restored game_started=false\n",baseline?"BASELINE":"ROLLBACK");return 1;}
 require(installNativeSceneLoading(m,nullptr),"idempotent install");
 require(!memcmp(engine+0x63075,"\xe8\xe1\x00\x00\x00",5),"cleanup call remains original; no standalone present");
 for(int mode:{2,7}){expectArmed=false;*reinterpret_cast<int*>(scene+0x1730)=0;*reinterpret_cast<int*>(scene+0x156c)=mode;*reinterpret_cast<int*>(engine+0xf2280)=mode==7?4:31;run();require(*reinterpret_cast<int*>(scene+0x1730)==0,"non-transition bypass");}
 *reinterpret_cast<int*>(scene+0x156c)=7;*reinterpret_cast<int*>(engine+0xf2280)=31;engine[0x38b45]=0;run();require(!*reinterpret_cast<int*>(scene+0x1730),"missing GUI guard bypass");engine[0x38b45]=0xe9;
 *reinterpret_cast<int*>(scene+0x1730)=9;run();require(*reinterpret_cast<int*>(scene+0x1730)==9,"existing native loading flag retained");
 require(removeNativeSceneLoading(m)&&removeNativeSceneLoading(m),"exact idempotent rollback");require(!memcmp(engine+0x631da,call,5),"exact draw call restored");
 engine[0x71137]=0xcd;require(!installNativeSceneLoading(m,nullptr),"source resource drift rejected");engine[0x71137]=0xcc;engine[0x631da]=0xcc;require(!installNativeSceneLoading(m,nullptr),"foreign draw hook rejected");
 puts("NATIVE_LOADING_ORDER MODIFIED PASS flag_before_native_draw=1 normal_draws=1 standalone_presents=0 cleanup_call=original rollback=exact game_started=false");return 0;
}
