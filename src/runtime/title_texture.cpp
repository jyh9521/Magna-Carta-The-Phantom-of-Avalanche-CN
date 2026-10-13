#include "title_texture.h"
#include <cstring>
#include <cstdio>
namespace {
using Selector=unsigned(__cdecl*)(unsigned,unsigned,unsigned);
Selector original=nullptr;ULONG_PTR allowedCaller=0,deviceResume=0;
void(*trace)(const wchar_t*)=nullptr;
thread_local bool requested=false;
unsigned __cdecl choose(unsigned w,unsigned h,unsigned quality,ULONG_PTR caller){
 unsigned legacy=original(w,h,quality);
 requested=caller==allowedCaller&&w==2048&&h==2048&&quality==1;
 if(requested){if(trace)trace(L"TITLE_TEXTURE_REQUEST source=2048 legacy_selected=256 requested=2048");return 2048;}
 return legacy;
}
void __cdecl deviceResult(unsigned actual,ULONG_PTR caller){
 if(requested&&caller==allowedCaller&&trace){wchar_t line[128];swprintf_s(line,L"TITLE_TEXTURE_DEVICE requested=2048 selected=%u",actual);trace(line);}
 requested=false;
}
// Outer EBP is ASRLoadTexture's frame; [EBP+4] identifies its engine caller.
__declspec(naked) void selectorHook(){__asm {
 push dword ptr[ebp+4]
 push dword ptr[esp+16]
 push dword ptr[esp+16]
 push dword ptr[esp+16]
 call choose
 add esp,16
 ret
}}
__declspec(naked) void deviceHook(){__asm {
 pushfd
 pushad
 push dword ptr[ebp+4]
 push eax
 call deviceResult
 add esp,8
 popad
 popfd
 mov dword ptr[ebp-4],eax
 mov ecx,dword ptr[ebp+0ch]
 jmp dword ptr[deviceResume]
}}
bool header(BYTE* p,DWORD size){if(!p)return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<1||d->e_lfanew>4096)return false;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&n->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&n->OptionalHeader.SizeOfImage==size;}
bool write(BYTE* p,const BYTE* bytes,unsigned count){DWORD old;if(!VirtualProtect(p,count,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(p,bytes,count);bool ok=FlushInstructionCache(GetCurrentProcess(),p,count)!=FALSE;DWORD ignored;return VirtualProtect(p,count,old,&ignored)!=FALSE&&ok;}
void callPatch(BYTE* out,BYTE* site,void* hook){out[0]=0xe8;*reinterpret_cast<int*>(out+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(hook)-reinterpret_cast<ULONG_PTR>(site+5));}
}
bool setTitleTexture(BYTE* e,BYTE* a,bool enabled,void(*logger)(const wchar_t*)){
 if(!header(e,0x10b000)||!header(a,0x74d000))return false;
 BYTE engineCall[]={0xff,0x15,0,0,0,0};*reinterpret_cast<DWORD*>(engineCall+2)=reinterpret_cast<DWORD>(e+0xbd1d0);
 DWORD caps[]={512,256,128};if(memcmp(e+0x326e6,engineCall,6)||memcmp(a+0x74fd0,caps,12))return false;
 BYTE sourceA[]={0xe8,0x3e,0xea,0xff,0xff},sourceB[]={0x89,0x45,0xfc,0x8b,0x4d,0x0c};
 BYTE patchA[5],patchB[6]={0xe9,0,0,0,0,0x90};callPatch(patchA,a+0x5338f,selectorHook);
 *reinterpret_cast<int*>(patchB+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(&deviceHook)-reinterpret_cast<ULONG_PTR>(a+0x533b5));
 if((memcmp(a+0x5338f,sourceA,5)&&memcmp(a+0x5338f,patchA,5))||(memcmp(a+0x533b0,sourceB,6)&&memcmp(a+0x533b0,patchB,6)))return false;
 BYTE beforeA[5],beforeB[6];memcpy(beforeA,a+0x5338f,5);memcpy(beforeB,a+0x533b0,6);
 original=reinterpret_cast<Selector>(a+0x51dd2);allowedCaller=reinterpret_cast<ULONG_PTR>(e+0x326ec);deviceResume=reinterpret_cast<ULONG_PTR>(a+0x533b6);trace=logger;
 if(!write(a+0x5338f,enabled?patchA:sourceA,5)){write(a+0x5338f,beforeA,5);return false;}
 if(!write(a+0x533b0,enabled?patchB:sourceB,6)){write(a+0x533b0,beforeB,6);write(a+0x5338f,beforeA,5);return false;}
 return true;
}
bool installTitleTexture(HMODULE e,HMODULE a,void(*logger)(const wchar_t*)){
 bool ok=setTitleTexture(reinterpret_cast<BYTE*>(e),reinterpret_cast<BYTE*>(a),true,logger);
 if(ok&&logger)logger(L"TITLE_TEXTURE_READY scope=BGR_2048 legacy_quality_cap_bypassed=true device_caps=retained");return ok;
}
