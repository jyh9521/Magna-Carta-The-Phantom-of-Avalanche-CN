#include "title_version.h"
#include "title_version_data.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace {
unsigned checks=0,activated=0,allocations=0;
bool failAllocation=false;
bool nullPrimary=false;
unsigned poisonMask=2;
constexpr DWORD tint=0xffa9926d;
BYTE* image=nullptr;
BYTE parent[0x24]{},service[0x30]{},font[0x40]{};
struct Record {void* node;std::string text;DWORD color;};
std::vector<Record> records;
std::vector<void*> storage;
template<class T>T& f(void* p,size_t offset){return *reinterpret_cast<T*>(static_cast<BYTE*>(p)+offset);}
void require(bool b,const char* s){++checks;if(!b){fprintf(stderr,"FAIL %s\n",s);ExitProcess(1);}}
int width(const char* text){int n=0;for(;*text;++text)n+=*text=='i'||*text=='.'||*text=='l'?4:7;return n;}
void* owned(){void* p=calloc(1,0x15c);require(p!=nullptr,"owned allocation");storage.push_back(p);return p;}
void* __cdecl allocate(unsigned n){require(n==0x15c,"native object size");++allocations;return failAllocation?nullptr:owned();}
void __fastcall activate(void*,void*){++activated;}
void* __fastcall construct(void* self,void*,const char* text,void* owner,int id){
    f<BYTE*>(self,0)=image+0xbdeb4;f<void*>(self,8)=owner;f<int>(self,4)=id;
    auto head=f<void*>(owner,0x18);f<void*>(self,0xc)=nullptr;f<void*>(self,0x10)=head;
    if(head)f<void*>(head,0xc)=self;else f<void*>(owner,0x1c)=self;
    f<void*>(owner,0x18)=self;++f<int>(owner,0x14);
    f<int>(self,0x12c)=width(text);f<int>(self,0x130)=14;
    records.push_back({self,text,tint});return nullPrimary&&id==0x155?nullptr:self;
}
// Exercise the captured legacy ABI hazard without running game code. The
// external caller is insulated so a failure is the production hook's result,
// not register corruption in this test's own C++ bookkeeping.
__declspec(naked) void poison(){__asm {
    test dword ptr[poisonMask],1
    jz keep_bx
    xor ebx,ebx
keep_bx:
    test dword ptr[poisonMask],2
    jz keep_si
    xor esi,esi
keep_si:
    test dword ptr[poisonMask],4
    jz keep_di
    xor edi,edi
keep_di:
    ret
}}
__declspec(naked) void* __fastcall legacyConstruct(void*,void*,const char*,void*,int){__asm {
    push dword ptr[esp+12]
    push dword ptr[esp+12]
    push dword ptr[esp+12]
    call construct
    call poison
    ret 12
}}
__declspec(naked) void* __fastcall invokeConstruct(void*,void*,const char*,void*,int){__asm {
    push ebx
    push esi
    push edi
    push dword ptr[esp+24]
    push dword ptr[esp+24]
    push dword ptr[esp+24]
    call edx
    pop edi
    pop esi
    pop ebx
    ret 12
}}
void __fastcall position(void* self,void*,float x,float y,float z){f<float>(self,0x24)=x;f<float>(self,0x28)=y;f<float>(self,0x2c)=z;}
int* __fastcall measure(void* self,void*,int* result,const char* text){require(self==font,"original font service");result[0]=width(text);result[1]=14;return result;}
__declspec(naked) void __fastcall legacyPosition(void*,void*,float,float,float){__asm {
    push dword ptr[esp+12]
    push dword ptr[esp+12]
    push dword ptr[esp+12]
    call position
    call poison
    ret 12
}}
__declspec(naked) int* __fastcall legacyMeasure(void*,void*,int*,const char*){__asm {
    push dword ptr[esp+8]
    push dword ptr[esp+8]
    call measure
    call poison
    ret 8
}}
__declspec(naked) void* __cdecl legacyAllocate(unsigned){__asm {
    push dword ptr[esp+4]
    call allocate
    add esp,4
    call poison
    ret
}}
__declspec(naked) void __fastcall legacyActivate(void*,void*){__asm {
    call activate
    call poison
    ret
}}
__declspec(naked) void __fastcall invokePosition(void*,void*,float,float,float){__asm {
    push ebx
    push esi
    push edi
    push dword ptr[esp+24]
    push dword ptr[esp+24]
    push dword ptr[esp+24]
    call edx
    pop edi
    pop esi
    pop ebx
    ret 12
}}
__declspec(naked) void __fastcall invokeActivate(void*,void*){__asm {
    push ebx
    push esi
    push edi
    call edx
    pop edi
    pop esi
    pop ebx
    ret
}}
void jump(BYTE* p,void* fn){p[0]=0xe9;f<DWORD>(p,1)=DWORD(fn)-DWORD(p+5);}
void callFrame(DWORD entry,DWORD site){
    const BYTE args[]={0xff,0x74,0x24,0x0c,0xff,0x74,0x24,0x0c,0xff,0x74,0x24,0x0c};
    memcpy(image+entry,args,sizeof args);jump(image+entry+sizeof args,image+site);
    const BYTE ret[]={0xc2,0x0c,0};memcpy(image+site+5,ret,sizeof ret);
}
void reset(){for(auto p:storage)free(p);storage.clear();records.clear();activated=allocations=0;memset(parent,0,sizeof parent);}
void replay(int w=853,int h=480,const char* text="v1.04a",int id=0x155){
    reset();auto first=owned();
    auto result=invokeConstruct(first,image+0x400,text,parent,id);
    require(result!=nullptr,"MCTitle.cpp:282 pNumber != NULL");
    require(result==first,"constructor return");
    invokePosition(first,image+0x450,float(w-52),float(h-20),7.f);
    invokeActivate(first,f<void*>(image,0xbdeb4+0x18));
}
void checkPair(int w,int h){
    require(records.size()==2&&records[0].text==std::string(titleOriginalPrefix)+"v1.04a"&&records[1].text==titlePatchLine,"two exact labels");
    require(activated==2&&allocations==1,"two native activations one extra object");
    require(f<int>(parent,0x14)==2&&f<void*>(parent,0x18)==records[1].node&&f<void*>(parent,0x1c)==records[0].node,"both native children registered");
    require(f<void*>(records[1].node,0x10)==records[0].node&&f<void*>(records[0].node,0xc)==records[1].node,"native sibling links");
    const float right=float(w-52+width("v1.04a"));
    for(auto& r:records){
        require(f<void*>(r.node,8)==parent&&r.color==tint,"native owner and original font color");
        require(f<float>(r.node,0x24)+f<int>(r.node,0x12c)==right,"shared original right edge");
        require(f<float>(r.node,0x24)>=0&&right<=w,"fits canvas");
        require(f<float>(r.node,0x2c)==7.f,"depth preserved");
    }
    require(f<float>(records[0].node,0x28)==h-38&&f<float>(records[1].node,0x28)==h-20,"line spacing and original bottom");
    require(f<int>(records[0].node,4)==0x155&&f<int>(records[1].node,4)==-1,"native version id and anonymous sibling");
}
void baseline(){replay();require(records.size()==1&&records[0].text=="v1.04a"&&allocations==0,"single original text");require(f<float>(records[0].node,0x24)==801&&f<float>(records[0].node,0x28)==460,"original position");}
}
int main(int argc,char** argv){
    std::string mode=argc==2?argv[1]:"--modified";
    require(argc<=2&&(mode=="--baseline"||mode=="--modified"||mode=="--rollback"||mode=="--legacy-abi"||mode=="--null-constructor"),"known arguments");
    image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image!=nullptr,"owned image");
    initializeTitleVersionFixture(image);
    jump(image+0x45040,reinterpret_cast<void*>(&construct));jump(image+0x4d480,reinterpret_cast<void*>(&position));
    jump(image+0xb8b5a,reinterpret_cast<void*>(&allocate));jump(image+0x1ee51,reinterpret_cast<void*>(&measure));
    f<void*>(image,0xf22a8)=service;f<void*>(service,0x2c)=font;f<void*>(image,0xbdeb4+0x18)=reinterpret_cast<void*>(&activate);
    callFrame(0x400,0xb6fad);callFrame(0x450,0xb7046);
    BYTE original[2][5];memcpy(original[0],image+0xb6fad,5);memcpy(original[1],image+0xb7046,5);
    baseline();
    if(mode=="--baseline"){
        puts("TITLE_VERSION_BASELINE PASS text=v1.04a lines=1 background=none game_started=false");
        reset();VirtualFree(image,0,MEM_RELEASE);return 0;
    }
    for(DWORD at:{0x108u,0xf1748u,0xb6fadu,0xb7046u}){
        image[at]^=1;require(!installTitleVersion(reinterpret_cast<HMODULE>(image),nullptr),"mismatch rejected before writes");image[at]^=1;
        require(!memcmp(original[0],image+0xb6fad,5)&&!memcmp(original[1],image+0xb7046,5),"transaction preserves both calls");
    }
    require(installTitleVersion(reinterpret_cast<HMODULE>(image),nullptr),"install");
    require(installTitleVersion(reinterpret_cast<HMODULE>(image),nullptr),"idempotent install");
    if(mode=="--null-constructor"){nullPrimary=true;replay();require(false,"native NULL must not be suppressed");}
    if(mode=="--legacy-abi"){
        for(int boundary=0;boundary<5;++boundary)for(unsigned mask:{1u,2u,4u,7u}){
            poisonMask=mask;
            jump(image+0x45040,reinterpret_cast<void*>(boundary==0?&legacyConstruct:&construct));
            jump(image+0x4d480,reinterpret_cast<void*>(boundary==1?&legacyPosition:&position));
            jump(image+0x1ee51,reinterpret_cast<void*>(boundary==2?&legacyMeasure:&measure));
            jump(image+0xb8b5a,reinterpret_cast<void*>(boundary==3?&legacyAllocate:&allocate));
            f<void*>(image,0xbdeb4+0x18)=reinterpret_cast<void*>(boundary==4?&legacyActivate:&activate);
            for(int w:{640,800,853,1067,1280})for(int h:{480,600,720})for(int visit=0;visit<3;++visit){replay(w,h);checkPair(w,h);}
            replay(853,480,"unrelated");require(records.size()==1,"legacy unrelated text pass-through");
            failAllocation=true;replay();require(records.size()==1&&records[0].text=="v1.04a","legacy allocation failure");failAllocation=false;
        }
        require(removeTitleVersion(),"rollback after legacy callback");
        baseline();reset();VirtualFree(image,0,MEM_RELEASE);
        printf("TITLE_VERSION_LEGACY_ABI PASS checks=%u boundaries=5 masks=4 title_visits=900 constructor_return=nonnull registers=preserved rollback=exact game_started=false\n",checks);
        return 0;
    }
    for(int w:{640,800,853,1067,1280})for(int h:{480,600,720})for(int visit=0;visit<3;++visit){
        replay(w,h);
        checkPair(w,h);
    }
    replay(853,480,"unrelated");require(records.size()==1&&records[0].text=="unrelated"&&allocations==0,"other text untouched");
    replay(853,480,"v1.04a",99);require(records.size()==1&&allocations==0,"other object id untouched");
    failAllocation=true;replay();require(records.size()==1&&records[0].text=="v1.04a","allocation failure retains original");failAllocation=false;
    image[0xb7046]^=1;require(!removeTitleVersion(),"rollback rejects drift");image[0xb7046]^=1;
    require(removeTitleVersion()&&removeTitleVersion(),"rollback idempotent");
    require(!memcmp(original[0],image+0xb6fad,5)&&!memcmp(original[1],image+0xb7046,5),"original call bytes restored");
    baseline();reset();VirtualFree(image,0,MEM_RELEASE);
    if(mode=="--rollback")puts("TITLE_VERSION_ROLLBACK PASS text=v1.04a lines=1 original_calls=exact game_started=false");
    else puts("TITLE_VERSION_MODIFIED PASS lines=2 align=right style=native background=none game_started=false");
    printf("TITLE_VERSION_CHECKS PASS checks=%u canvases=15 title_visits=45 rollback=exact\n",checks);
    return 0;
}
