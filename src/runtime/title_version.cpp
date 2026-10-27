#include "title_version.h"
#include "title_version_data.h"
#include <algorithm>
#include <cstdio>
#include <cstring>

namespace {
constexpr DWORD imageSize=0x10b000;
using Construct=void*(__thiscall*)(void*,const char*,void*,int);
using Position=void(__thiscall*)(void*,float,float,float);
using Allocate=void*(__cdecl*)(unsigned);
using Measure=int*(__thiscall*)(void*,int*,const char*);
using Activate=void(__thiscall*)(void*);
BYTE* engine=nullptr;
Construct construct=nullptr;
Position position=nullptr;
Allocate allocate=nullptr;
Measure measure=nullptr;
// Consumed by the immediately following, source-locked title position call.
// No pointer survives title construction, so revisiting the title cannot reuse
// a destroyed text node. Both objects belong to the native parent/destructor.
struct Pending {void* first=nullptr;void* second=nullptr;int originalWidth=0;};
thread_local Pending pending;
template<class T>T& field(void* p,size_t offset){return *reinterpret_cast<T*>(static_cast<BYTE*>(p)+offset);}

// Legacy engine callbacks can alter EBX/ESI/EDI. Modern C++ keeps live object
// pointers in those registers: in particular, the second text construction
// used to erase the first constructor's return value cached in ESI. Preserve
// the caller's registers at every native boundary, while retaining native EAX
// results and thiscall argument cleanup. Do not suppress the game's assertion.
__declspec(naked) void* __fastcall callConstruct(void*,void*,const char*,void*,int){__asm {
    push ebx
    push esi
    push edi
    push dword ptr[esp+24]
    push dword ptr[esp+24]
    push dword ptr[esp+24]
    call dword ptr[construct]
    pop edi
    pop esi
    pop ebx
    ret 12
}}
__declspec(naked) void __fastcall callPosition(void*,void*,float,float,float){__asm {
    push ebx
    push esi
    push edi
    push dword ptr[esp+24]
    push dword ptr[esp+24]
    push dword ptr[esp+24]
    call dword ptr[position]
    pop edi
    pop esi
    pop ebx
    ret 12
}}
__declspec(naked) void* __cdecl callAllocate(unsigned){__asm {
    push ebx
    push esi
    push edi
    push dword ptr[esp+16]
    call dword ptr[allocate]
    add esp,4
    pop edi
    pop esi
    pop ebx
    ret
}}
__declspec(naked) int* __fastcall callMeasure(void*,void*,int*,const char*){__asm {
    push ebx
    push esi
    push edi
    push dword ptr[esp+20]
    push dword ptr[esp+20]
    call dword ptr[measure]
    pop edi
    pop esi
    pop ebx
    ret 8
}}
__declspec(naked) void __fastcall callActivate(void*){__asm {
    push ebx
    push esi
    push edi
    mov eax,dword ptr[ecx]
    call dword ptr[eax+18h]
    pop edi
    pop esi
    pop ebx
    ret
}}

void* __fastcall constructHook(void* self,void*,const char* text,void* parent,int id){
    pending={};
    // This is not a global text replacement and never writes the original
    // eight-byte sprintf stack buffer or changes the game's version metadata.
    if(!text||strcmp(text,"v1.04a")||id!=0x155)return callConstruct(self,nullptr,text,parent,id);
    auto service=field<BYTE*>(engine,0xf22a8);
    int originalSize[2]{};
    callMeasure(field<void*>(service,0x2c),nullptr,originalSize,text);
    void* extra=callAllocate(0x15c);
    if(!extra)return callConstruct(self,nullptr,text,parent,id);
    char first[96]{};
    sprintf_s(first,"%s%s",titleOriginalPrefix,text);
    void* result=callConstruct(self,nullptr,first,parent,id);
    void* second=callConstruct(extra,nullptr,titlePatchLine,parent,-1);
    pending={result,second,originalSize[0]};
    return result;
}

void __fastcall positionHook(void* self,void*,float x,float y,float z){
    auto pair=pending;
    pending={};
    if(pair.first!=self||!pair.second){callPosition(self,nullptr,x,y,z);return;}
    const float right=x+pair.originalWidth;
    const int firstWidth=field<int>(self,0x12c),secondWidth=field<int>(pair.second,0x12c);
    const int height=std::max(field<int>(self,0x130),field<int>(pair.second,0x130));
    callPosition(self,nullptr,right-firstWidth,y-height-4,z);
    callPosition(pair.second,nullptr,right-secondWidth,y,z);
    // The existing call activates the first line; activate its sibling through
    // exactly the same native virtual method. Font, tint, alpha and blending
    // remain entirely native; no panel, background, GDI or frame overlay.
    callActivate(pair.second);
}

struct Site {DWORD rva;BYTE original[5];void* hook;};
const Site sites[]={
    {0xb6fad,{0xe8,0x8e,0xe0,0xf8,0xff},reinterpret_cast<void*>(&constructHook)},
    {0xb7046,{0xe8,0x35,0x64,0xf9,0xff},reinterpret_cast<void*>(&positionHook)},
};
bool readable(const void* p,size_t n){
    auto at=reinterpret_cast<ULONG_PTR>(p),end=at+n;
    if(!at||end<at)return false;
    while(at<end){MEMORY_BASIC_INFORMATION m{};
        if(!VirtualQuery(reinterpret_cast<void*>(at),&m,sizeof m)||m.State!=MEM_COMMIT||(m.Protect&(PAGE_NOACCESS|PAGE_GUARD)))return false;
        auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;
        if(next<=at)return false;at=next;
    }return true;
}
bool identity(BYTE* p){
    if(!readable(p,imageSize))return false;
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<64||dos->e_lfanew>4096)return false;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);
    return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&
        nt->FileHeader.TimeDateStamp==0x3ed73966&&nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&
        nt->OptionalHeader.SizeOfImage==imageSize&&!memcmp(p+0xf1748,"v%.2f%s",8);
}
void branch(BYTE* bytes,BYTE* address,void* hook){bytes[0]=0xe8;*reinterpret_cast<DWORD*>(bytes+1)=DWORD(hook)-DWORD(address+5);}
bool write(BYTE* p,const BYTE* data){
    DWORD old=0;if(!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old))return false;
    memcpy(p,data,5);bool ok=FlushInstructionCache(GetCurrentProcess(),p,5)!=0;
    DWORD ignored=0;return VirtualProtect(p,5,old,&ignored)!=0&&ok;
}
}

bool installTitleVersion(HMODULE module,void(*log)(const wchar_t*)){
    auto p=reinterpret_cast<BYTE*>(module);
    if(!identity(p)||(engine&&engine!=p))return false;
    BYTE replacements[2][5];
    for(unsigned i=0;i<2;++i){
        branch(replacements[i],p+sites[i].rva,sites[i].hook);
        if(memcmp(p+sites[i].rva,engine?replacements[i]:sites[i].original,5))return false;
    }
    if(engine)return true;
    construct=reinterpret_cast<Construct>(p+0x45040);
    position=reinterpret_cast<Position>(p+0x4d480);
    allocate=reinterpret_cast<Allocate>(p+0xb8b5a);
    measure=reinterpret_cast<Measure>(p+0x1ee51);
    for(unsigned i=0;i<2;++i)if(!write(p+sites[i].rva,replacements[i])){
        for(unsigned j=0;j<=i;++j)write(p+sites[j].rva,sites[j].original);
        return false;
    }
    engine=p;
    if(log)log(L"TITLE_VERSION_V2 lines=2 alignment=right font=native background=none native_abi=preserved");
    return true;
}
bool removeTitleVersion(){
    if(!engine)return true;
    BYTE replacements[2][5];
    for(unsigned i=0;i<2;++i){branch(replacements[i],engine+sites[i].rva,sites[i].hook);if(memcmp(engine+sites[i].rva,replacements[i],5))return false;}
    for(unsigned i=0;i<2;++i)if(!write(engine+sites[i].rva,sites[i].original)){
        for(unsigned j=0;j<=i;++j)write(engine+sites[j].rva,replacements[j]);return false;
    }
    engine=nullptr;pending={};return true;
}
#ifdef TITLE_VERSION_TEST
void initializeTitleVersionFixture(BYTE* p){
    memset(p,0,imageSize);
    auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;
    auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);n->Signature=IMAGE_NT_SIGNATURE;
    n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->FileHeader.TimeDateStamp=0x3ed73966;
    n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=imageSize;
    memcpy(p+0xf1748,"v%.2f%s",8);
    for(const auto& s:sites)memcpy(p+s.rva,s.original,5);
}
#endif
