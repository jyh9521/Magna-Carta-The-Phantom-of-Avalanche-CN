#include "menu_visibility.h"
#include <cstring>
#include <cstdint>
#include <cstdio>

bool menuPhaseVisible(int phase) {
    switch(phase){case 0:case 1:case 2:case 3:case 6:case 7:case 11:case 12:return false;default:return true;}
}
namespace {
constexpr size_t slotRva=0xc2350,drawRva=0x4c6ff;
constexpr unsigned char drawContext[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xf8,0x8b,0x45,0xf8,0x8b,0x48,0x1c,0x89,0x4d,0xfc,0x8b,0x55,0xf8,0x8b,0x8a,0xec,0,0,0,0xe8,0x21,0x0c,0,0};
using Draw=void(__thiscall*)(void*);
Draw original=nullptr;DWORD* installedSlot=nullptr;HMODULE installed=nullptr;
void(*trace)(const wchar_t*)=nullptr;volatile LONG suppressed=0;
bool image(unsigned char* p,size_t available){
    if(!p||available<0x10b000)return false;
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<1||dos->e_lfanew>4096)return false;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);
    return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&
        nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&nt->OptionalHeader.SizeOfImage==0x10b000;
}
bool replace(DWORD* slot,DWORD expected,DWORD value){
    if(*slot!=expected)return false;
    DWORD old;if(!VirtualProtect(slot,4,PAGE_READWRITE,&old))return false;
    // Never overwrite an independently changed slot.
    bool good=InterlockedCompareExchange(reinterpret_cast<volatile LONG*>(slot),static_cast<LONG>(value),static_cast<LONG>(expected))==static_cast<LONG>(expected);
    DWORD ignored;if(!VirtualProtect(slot,4,old,&ignored)){
        if(good)InterlockedCompareExchange(reinterpret_cast<volatile LONG*>(slot),static_cast<LONG>(expected),static_cast<LONG>(value));
        VirtualProtect(slot,4,old,&ignored);return false;
    }
    return good;
}
void __fastcall drawHook(void* menu,void*){
    if(menu){
        auto owner=*reinterpret_cast<unsigned char**>(static_cast<unsigned char*>(menu)+0x1a8);
        MEMORY_BASIC_INFORMATION region{};
        bool ownerReadable=owner && VirtualQuery(owner,&region,sizeof(region)) && region.State==MEM_COMMIT &&
            !(region.Protect&(PAGE_NOACCESS|PAGE_GUARD)) && reinterpret_cast<ULONG_PTR>(owner)+0x74>=reinterpret_cast<ULONG_PTR>(owner) &&
            reinterpret_cast<ULONG_PTR>(owner)+0x74<=reinterpret_cast<ULONG_PTR>(region.BaseAddress)+region.RegionSize;
        if(ownerReadable && *reinterpret_cast<DWORD*>(owner)==reinterpret_cast<DWORD>(installed)+0xc22f0){
            const int phase=*reinterpret_cast<int*>(owner+0x70);
            if(!menuPhaseVisible(phase)){
                const LONG bit=1L<<phase;
                if(!(InterlockedOr(&suppressed,bit)&bit)&&trace){
                    wchar_t text[120];swprintf_s(text,L"MENU_VISIBILITY_SUPPRESSED title_phase=%d transition_buttons=hidden",phase);trace(text);
                }
                return;
            }
        }
    }
    original(menu);
}
}
bool menuVisibilityImageMatches(unsigned char* p,size_t available){
    return image(p,available)&&!memcmp(p+drawRva,drawContext,sizeof(drawContext))&&
        *reinterpret_cast<DWORD*>(p+slotRva)==reinterpret_cast<DWORD>(p+drawRva);
}
bool installMenuVisibility(HMODULE module,void(*logger)(const wchar_t*)){
    if(installed)return installed==module;
    auto p=reinterpret_cast<unsigned char*>(module);if(!image(p,0x10b000))return false;
#ifdef MENU_VISIBILITY_TEST
    if(memcmp(p+drawRva,drawContext,6))return false;
#else
    if(!menuVisibilityImageMatches(p,0x10b000))return false;
#endif
    auto slot=reinterpret_cast<DWORD*>(p+slotRva);DWORD expected=reinterpret_cast<DWORD>(p+drawRva);
    if(*slot!=expected)return false;
    original=reinterpret_cast<Draw>(expected);trace=logger;suppressed=0;
    if(!replace(slot,expected,reinterpret_cast<DWORD>(&drawHook))){original=nullptr;trace=nullptr;return false;}
    installedSlot=slot;installed=module;return true;
}
bool removeMenuVisibility(){
    if(!installed)return true;
    if(!replace(installedSlot,reinterpret_cast<DWORD>(&drawHook),reinterpret_cast<DWORD>(original)))return false;
    installedSlot=nullptr;installed=nullptr;original=nullptr;trace=nullptr;suppressed=0;return true;
}
