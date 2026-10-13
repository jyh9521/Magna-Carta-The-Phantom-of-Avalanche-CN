#include "title_style.h"
#include <cstdio>
#include <cstring>
#include <cstdint>
static BYTE* image=nullptr;static BYTE bgr[0x174]{},background[0x174]{};
static unsigned checks=0,observed=0,unrelated=0,baseColor=0xffffffff;static bool throwDraw=false;static float colorState[4]={1,1,1,1};
void require(bool b,const char* s){++checks;if(!b){fprintf(stderr,"FAIL %s\n",s);ExitProcess(1);}}
using Render=void(__cdecl*)(unsigned,unsigned,void*,unsigned,unsigned,int,int,unsigned,unsigned,unsigned,unsigned,unsigned,void*,unsigned);
void __cdecl renderer(unsigned,unsigned,void* vertices,unsigned,unsigned,int,int,unsigned color,unsigned,unsigned,unsigned,unsigned,void*,unsigned){require(color==baseColor,"unused integer argument preserved");unsigned queued=unsigned(colorState[3]*255+.5f)<<24;for(unsigned i=0;i<3;++i)queued|=unsigned(colorState[i]*255+.5f)<<(16-i*8);if(vertices==bgr+0x124)observed=queued;else unrelated=queued;}
void __fastcall draw(void*,void*){
 auto fn=reinterpret_cast<Render>(*reinterpret_cast<DWORD*>(image+0xbd01c));
 fn(0x102,5,bgr+0x124,0,4,-1,3,baseColor,2,100,0,100,nullptr,0);
 fn(0x102,5,background+0x124,0,4,-1,3,0xffffffff,2,100,0,100,nullptr,0);
 if(throwDraw)RaiseException(0xe0004242,0,0,nullptr);
}
using Draw=void(__thiscall*)(void*);
bool probe(Draw fn,void* p){__try{fn(p);}__except(GetExceptionCode()==0xe0004242?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH){return true;}return false;}
int main(int argc,char** argv){
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image!=nullptr,"owned image");
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 BYTE stub[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x8b,0xe5,0x5d,0xe9};memcpy(image+0x4c6ff,stub,sizeof(stub));*reinterpret_cast<int32_t*>(image+0x4c709)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(&draw)-reinterpret_cast<ULONG_PTR>(image+0x4c70d));
 image[0x4258b]=0xff;image[0x4258c]=0x15;*reinterpret_cast<DWORD*>(image+0x4258d)=reinterpret_cast<DWORD>(image+0xbd01c);
 auto drawSlot=reinterpret_cast<DWORD*>(image+0xbee90),renderSlot=reinterpret_cast<DWORD*>(image+0xbd01c);*drawSlot=reinterpret_cast<DWORD>(image+0x4c6ff);*renderSlot=reinterpret_cast<DWORD>(&renderer);titleStyleFixtureRenderer(reinterpret_cast<void*>(&renderer),colorState);
 BYTE button[0x1a8]{},menu[0x1ac]{},owner[0x74]{},visual[0x120]{};
 *reinterpret_cast<BYTE**>(button)=image+0xbee80;*reinterpret_cast<int*>(button+4)=0x16c;*reinterpret_cast<int*>(button+0x160)=1;*reinterpret_cast<BYTE**>(button+0x17c)=menu;*reinterpret_cast<BYTE**>(button+0xec)=visual;
 *reinterpret_cast<BYTE**>(menu)=image+0xc2340;*reinterpret_cast<BYTE**>(menu+0x1a8)=owner;*reinterpret_cast<BYTE**>(owner)=image+0xc22f0;*reinterpret_cast<int*>(owner+0x70)=4;*reinterpret_cast<BYTE**>(visual+0x1c)=bgr;*reinterpret_cast<BYTE**>(bgr)=image+0xbdb9c;
 auto invoke=[&](){reinterpret_cast<Draw>(*drawSlot)(button);};
 invoke();require(observed==0xffffffff&&unrelated==0xffffffff,"baseline original white rendering");
 if(argc==2&&!strcmp(argv[1],"--baseline-only")){VirtualFree(image,0,MEM_RELEASE);printf("TITLE_STYLE_BASELINE PASS original_white=true hooks=not_installed game_started=false\n");return 0;}
 if(argc==2&&!strcmp(argv[1],"--baseline-check")){require(observed==0xffaaa69e,"normal title buttons should be muted instead of bright white");return 1;}
 require(installTitleStyle(reinterpret_cast<HMODULE>(image),nullptr),"install known source");require(installTitleStyle(reinterpret_cast<HMODULE>(image),nullptr),"install idempotence");
 invoke();require(observed==0xffaaa69e&&unrelated==0xffffffff,"normal muted, shared background untouched");
 *reinterpret_cast<int*>(button+0x198)=1;invoke();require(observed==0xffffbd66,"focus amber");
 *reinterpret_cast<int*>(button+0x19c)=1;invoke();require(observed==0xffff8f35,"pressed orange");
 *reinterpret_cast<int*>(button+0x160)=0;invoke();require(observed==0xff706e68,"disabled distinct");
 *reinterpret_cast<int*>(button+0x160)=1;*reinterpret_cast<int*>(button+0x198)=*reinterpret_cast<int*>(button+0x19c)=0;
 colorState[3]=128.f/255;invoke();require(observed==0x80aaa69e,"original alpha preserved");colorState[3]=1;
 for(int id=0x16c;id<=0x16f;++id){*reinterpret_cast<int*>(button+4)=id;invoke();require(observed==0xffaaa69e,"all four title button identifiers");}
 *reinterpret_cast<int*>(button+4)=0x170;invoke();require(observed==0xffffffff,"other buttons unaffected");*reinterpret_cast<int*>(button+4)=0x16c;
 *reinterpret_cast<int*>(owner+0x70)=3;invoke();require(observed==0xffffffff,"intro untouched");*reinterpret_cast<int*>(owner+0x70)=8;invoke();require(observed==0xffffffff,"load window untouched");*reinterpret_cast<int*>(owner+0x70)=4;
 *reinterpret_cast<BYTE**>(menu+0x1a8)=nullptr;invoke();require(observed==0xffffffff,"null owner forwarded");*reinterpret_cast<BYTE**>(menu+0x1a8)=owner;
 throwDraw=true;require(probe(reinterpret_cast<Draw>(*drawSlot),button),"SEH propagated");throwDraw=false;
 reinterpret_cast<Render>(*renderSlot)(0x102,5,bgr+0x124,0,4,-1,3,0xffffffff,2,100,0,100,nullptr,0);require(observed==0xffffffff,"scope cleared after SEH");
 auto hook=*renderSlot;*renderSlot=1;require(!removeTitleStyle(),"foreign renderer blocks rollback");*renderSlot=hook;
 require(removeTitleStyle(),"rollback");require(*drawSlot==reinterpret_cast<DWORD>(image+0x4c6ff)&&*renderSlot==reinterpret_cast<DWORD>(&renderer),"exact two slots restored");invoke();require(observed==0xffffffff,"rollback restores white baseline");
 image[0x4258b]^=1;require(!installTitleStyle(reinterpret_cast<HMODULE>(image),nullptr),"unknown callsite rejected");
 VirtualFree(image,0,MEM_RELEASE);printf("TITLE_STYLE_FIXTURE PASS checks=%u normal=muted focus=amber pressed=orange background=unchanged alpha=preserved rollback=exact game_started=false\n",checks);
 if(argc==2&&!strcmp(argv[1],"--rollback-check"))printf("TITLE_STYLE_ROLLBACK PASS original_white=restored slots=exact active_runtime=unchanged game_started=false\n");
}
