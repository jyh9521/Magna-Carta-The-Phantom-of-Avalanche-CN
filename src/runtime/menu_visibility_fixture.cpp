#include "menu_visibility.h"
#include <cstdio>
#include <cstring>
#include <vector>
static unsigned calls=0,checks=0,failures=0;
static void __cdecl countDraw(){++calls;}
#define CHECK(c) do{++checks;if(!(c)){++failures;printf("MENU_VISIBILITY_FAILED line=%d\n",__LINE__);}}while(0)
using Draw=void(__thiscall*)(void*);
int main(int argc,char** argv){
    auto p=static_cast<unsigned char*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
    if(!p)return 1;
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=128;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+128);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
    const unsigned char context[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xf8,0x8b,0x45,0xf8,0x8b,0x48,0x1c,0x89,0x4d,0xfc,0x8b,0x55,0xf8,0x8b,0x8a,0xec,0,0,0,0xe8,0x21,0x0c,0,0};
    memcpy(p+0x4c6ff,context,sizeof(context));auto slot=reinterpret_cast<DWORD*>(p+0xc2350);*slot=reinterpret_cast<DWORD>(p+0x4c6ff);
    CHECK(menuVisibilityImageMatches(p,0x10b000));CHECK(!menuVisibilityImageMatches(p,0x10b000-1));
    p[0x4c6ff+20]^=1;CHECK(!menuVisibilityImageMatches(p,0x10b000));p[0x4c6ff+20]^=1;
    // Owned executable counter stub. No commercial function body is executed.
    unsigned char stub[]={0x55,0x8b,0xec,0x83,0xec,0x08,0xb8,0,0,0,0,0xff,0xd0,0xc9,0xc3};
    *reinterpret_cast<DWORD*>(stub+7)=reinterpret_cast<DWORD>(&countDraw);memcpy(p+0x4c6ff,stub,sizeof(stub));
    unsigned char owner[0x80]={},menu[0x1b0]={};*reinterpret_cast<unsigned char**>(menu+0x1a8)=owner;
    *reinterpret_cast<DWORD*>(owner)=reinterpret_cast<DWORD>(p+0xc22f0);
    auto draw=[&](){reinterpret_cast<Draw>(*slot)(menu);};
    // Baseline reproduces menu draw during start/exit transition states.
    for(int phase:{0,1,2,3,6,7,11,12}){*reinterpret_cast<int*>(owner+0x70)=phase;unsigned n=calls;draw();CHECK(calls==n+1);}
    printf("MENU_VISIBILITY_BASELINE_REPRODUCED transition_draws=%u\n",calls);
    if(argc==2 && !strcmp(argv[1],"--baseline-check")){VirtualFree(p,0,MEM_RELEASE);printf("MENU_RESIDUE_REGRESSION FAIL transition_buttons_drawn=true states=0,1,2,3,6,7,11,12\n");return 1;}
    CHECK(!installMenuVisibility(nullptr,nullptr));DWORD original=*slot;*slot=0;CHECK(!installMenuVisibility(reinterpret_cast<HMODULE>(p),nullptr));*slot=original;
    CHECK(installMenuVisibility(reinterpret_cast<HMODULE>(p),nullptr));CHECK(installMenuVisibility(reinterpret_cast<HMODULE>(p),nullptr));
    for(int phase=-3;phase<25;++phase){
        const bool expectedVisible=!(phase>=0&&phase<=3)&&phase!=6&&phase!=7&&phase!=11&&phase!=12;
        *reinterpret_cast<int*>(owner+0x70)=phase;unsigned n=calls;draw();CHECK(calls==n+(expectedVisible?1:0));
    }
    *reinterpret_cast<DWORD*>(owner)=0;unsigned forwarded=calls;draw();CHECK(calls==forwarded+1);
    *reinterpret_cast<DWORD*>(owner)=reinterpret_cast<DWORD>(p+0xc22f0);
    *reinterpret_cast<unsigned char**>(menu+0x1a8)=nullptr;unsigned n=calls;draw();CHECK(calls==n+1);
    DWORD hook=*slot;*slot=0;CHECK(!removeMenuVisibility());*slot=hook;CHECK(removeMenuVisibility());CHECK(*slot==original);
    *reinterpret_cast<unsigned char**>(menu+0x1a8)=owner;*reinterpret_cast<int*>(owner+0x70)=11;n=calls;draw();CHECK(calls==n+1);
    VirtualFree(p,0,MEM_RELEASE);
    if(failures)return 1;
    printf("MENU_VISIBILITY_FIXTURE PASS checks=%u transitions=hidden interactive_fadein_load_unknown=preserved null_owner=forwarded mismatch=rejected rollback=exact commercial_code_executed=false game_started=false\n",checks);return 0;
}
