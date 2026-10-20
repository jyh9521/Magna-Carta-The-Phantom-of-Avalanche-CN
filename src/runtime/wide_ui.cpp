#include "wide_ui.h"
#include <cstring>
#include <cmath>
namespace {
#ifdef WIDE_UI_TEST
int failingWrite=-1;
#endif
BYTE* engine=nullptr;int originalWidth=0,virtualWidth=0;
ULONG_PTR widthResumeA=0,widthResumeD=0,pollResume=0,windowResume=0,compassResume[4]{};
using Warp=BOOL(WINAPI*)(int,int);Warp originalWarp=nullptr;
using Create=void*(__cdecl*)(DWORD*);Create originalCreate=nullptr;
thread_local DWORD physicalCreateInfo[7]{};
void* __cdecl createHook(DWORD* info){
 if(info==reinterpret_cast<DWORD*>(engine+0xf1b40)&&originalWidth>0&&originalWidth!=virtualWidth){
  memcpy(physicalCreateInfo,info,sizeof(physicalCreateInfo));physicalCreateInfo[2]=originalWidth;
  return originalCreate(physicalCreateInfo);
 }
 return originalCreate(info);
}
void __cdecl storeWidth(int width){originalWidth=width;virtualWidth=(width==640||width==800)?(width*4+1)/3:width;*reinterpret_cast<int*>(engine+0xf1b48)=virtualWidth;}
int __cdecl mapMouse(int x){return originalWidth>0?static_cast<int>(std::lround(static_cast<double>(x)*virtualWidth/originalWidth)):x;}
float __cdecl compassX(){return static_cast<float>(virtualWidth!=originalWidth?virtualWidth-100:(originalWidth>0&&originalWidth<700?540:700));}
BOOL __cdecl warpAtOrigin(int x,int y,int origin){int physical=virtualWidth>0?static_cast<int>(std::lround(static_cast<double>(x-origin)*originalWidth/virtualWidth))+origin:x;return originalWarp(physical,y);}
__declspec(naked) void warpPosition(){__asm {
pushfd
pushad
mov ecx,dword ptr[ebp-8]
mov eax,dword ptr[esp+40]
mov edx,dword ptr[esp+44]
push ecx
push edx
push eax
call warpAtOrigin
add esp,12
mov dword ptr[esp+28],eax
popad
popfd
ret 8
}}
__declspec(naked) void warpCenter(){__asm {
pushfd
pushad
mov ecx,dword ptr[virtualWidth]
sar ecx,1
mov eax,dword ptr[ebp-8]
sub eax,ecx
mov ecx,dword ptr[esp+40]
mov edx,dword ptr[esp+44]
push eax
push edx
push ecx
call warpAtOrigin
add esp,12
mov dword ptr[esp+28],eax
popad
popfd
ret 8
}}
__declspec(naked) void widthA(){__asm {
pushfd
pushad
push eax
call storeWidth
add esp,4
popad
popfd
jmp dword ptr[widthResumeA]
}}
__declspec(naked) void widthD(){__asm {
pushfd
pushad
push edx
call storeWidth
add esp,4
popad
popfd
jmp dword ptr[widthResumeD]
}}
__declspec(naked) void poll(){__asm {
pushfd
pushad
push dword ptr[ebp-8]
call mapMouse
mov dword ptr[ebp-8],eax
add esp,4
popad
popfd
mov ecx,dword ptr[ebp-8]
push eax
mov eax,dword ptr[engine]
mov dword ptr[eax+0f20b0h],ecx
pop eax
jmp dword ptr[pollResume]
}}
__declspec(naked) void compass0(){__asm {
pushfd
pushad
call compassX
fstp dword ptr[ebp-10h]
popad
popfd
jmp dword ptr[compassResume]
}}
__declspec(naked) void compass1(){__asm {
pushfd
pushad
call compassX
fstp dword ptr[ebp-10h]
popad
popfd
jmp dword ptr[compassResume+4]
}}
__declspec(naked) void compass2(){__asm {
pushfd
pushad
call compassX
fstp dword ptr[ebp-18h]
popad
popfd
jmp dword ptr[compassResume+8]
}}
__declspec(naked) void compass3(){__asm {
pushfd
pushad
call compassX
fstp dword ptr[ebp-18h]
popad
popfd
jmp dword ptr[compassResume+12]
}}
__declspec(naked) void physicalWindowWidth(){__asm {
pushfd
mov ecx,dword ptr[originalWidth]
test ecx,ecx
jnz haveWidth
push eax
mov eax,dword ptr[engine]
mov ecx,dword ptr[eax+0f1b48h]
pop eax
haveWidth:
popfd
jmp dword ptr[windowResume]
}}
struct Site{DWORD rva;BYTE original[10];BYTE count;void* hook;};
Site sites[]={
 {0x983b,{0xa3,0,0,0,0},5,widthA},{0x99de,{0x89,0x15,0,0,0,0},6,widthD},
 {0x2dec,{0x8b,0x4d,0xf8,0x89,0x0d,0,0,0,0},9,poll},
 {0x2ea5,{0xff,0x15,0,0,0,0},6,warpPosition},{0x2f45,{0xff,0x15,0,0,0,0},6,warpCenter},
 {0x7083a,{0xc7,0x45,0xf0,0,0,0x07,0x44},7,compass0},
 {0x70843,{0xc7,0x45,0xf0,0,0,0x2f,0x44},7,compass1},
 {0x70cd4,{0xc7,0x45,0xe8,0,0,0x07,0x44},7,compass2},
 {0x70cdd,{0xc7,0x45,0xe8,0,0,0x2f,0x44},7,compass3},
 {0xc15b,{0x8b,0x0d,0,0,0,0},6,physicalWindowWidth},
 {0xb95b,{0xff,0x15,0,0,0,0},6,createHook},
 // Resource variants are selected by the native mode, not the expanded UI canvas.
 {0xaefcc,{0x81,0x3d,0,0,0,0,0x80,0x02,0,0},10,nullptr},
 {0xaf068,{0x81,0x3d,0,0,0,0,0x20,0x03,0,0},10,nullptr}};
void expected(BYTE* image){auto base=reinterpret_cast<DWORD>(image);*reinterpret_cast<DWORD*>(sites[0].original+1)=base+0xf1b48;*reinterpret_cast<DWORD*>(sites[1].original+2)=base+0xf1b48;*reinterpret_cast<DWORD*>(sites[2].original+5)=base+0xf20b0;for(int i=3;i<=4;++i)*reinterpret_cast<DWORD*>(sites[i].original+2)=base+0xbd3e4;*reinterpret_cast<DWORD*>(sites[9].original+2)=base+0xf1b48;*reinterpret_cast<DWORD*>(sites[10].original+2)=base+0xbd048;for(int i=11;i<=12;++i)*reinterpret_cast<DWORD*>(sites[i].original+2)=base+0xf1b48;}
void changed(const Site& s,BYTE* image,BYTE* bytes){if(!s.hook){memcpy(bytes,s.original,s.count);*reinterpret_cast<DWORD*>(bytes+2)=reinterpret_cast<DWORD>(&originalWidth);return;}memset(bytes,0x90,s.count);bytes[0]=(s.rva==0x2ea5||s.rva==0x2f45||s.rva==0xb95b)?0xe8:0xe9;*reinterpret_cast<int*>(bytes+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(s.hook)-reinterpret_cast<ULONG_PTR>(image+s.rva+5));}
bool write(BYTE* p,const BYTE* data,size_t n){DWORD old;if(!VirtualProtect(p,n,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(p,data,n);FlushInstructionCache(GetCurrentProcess(),p,n);DWORD ignored;bool ok=VirtualProtect(p,n,old,&ignored)!=FALSE;
#ifdef WIDE_UI_TEST
if(failingWrite==0){failingWrite=-1;return false;}if(failingWrite>0)--failingWrite;
#endif
return ok;}
}
bool setWideUi(BYTE* image,size_t available,bool enabled){
 if(!image||available<0x10b000)return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 expected(image);BYTE patch[10];bool already=true;
 for(auto& s:sites){changed(s,image,patch);if(memcmp(image+s.rva,enabled?patch:s.original,s.count)!=0)already=false;if(memcmp(image+s.rva,s.original,s.count)&&memcmp(image+s.rva,patch,s.count))return false;}
 if(already)return true;
 if(enabled){engine=image;originalWidth=virtualWidth=*reinterpret_cast<int*>(image+0xf1b48);widthResumeA=reinterpret_cast<ULONG_PTR>(image+0x9840);widthResumeD=reinterpret_cast<ULONG_PTR>(image+0x99e4);pollResume=reinterpret_cast<ULONG_PTR>(image+0x2df5);windowResume=reinterpret_cast<ULONG_PTR>(image+0xc161);for(int i=0;i<4;++i)compassResume[i]=reinterpret_cast<ULONG_PTR>(image+sites[5+i].rva+7);originalWarp=*reinterpret_cast<Warp*>(image+0xbd3e4);originalCreate=*reinterpret_cast<Create*>(image+0xbd048);if(!originalWarp||!originalCreate)return false;}
 constexpr unsigned siteCount=sizeof(sites)/sizeof(sites[0]);BYTE previous[siteCount][10]{};for(unsigned i=0;i<siteCount;++i)memcpy(previous[i],image+sites[i].rva,sites[i].count);
 unsigned done=0;for(auto& s:sites){changed(s,image,patch);if(!write(image+s.rva,enabled?patch:s.original,s.count)){for(unsigned i=0;i<=done;++i)write(image+sites[i].rva,previous[i],sites[i].count);return false;}++done;}
 if(!enabled){*reinterpret_cast<int*>(image+0xf1b48)=originalWidth;engine=nullptr;originalWidth=virtualWidth=0;}return true;
}
bool installWideUi(HMODULE module,void(*logger)(const wchar_t*)){bool ok=setWideUi(reinterpret_cast<BYTE*>(module),0x10b000,true);if(ok&&logger)logger(L"WIDE_UI_CANVAS enabled=true width=4/3 mouse=inverse_pair compass=right_anchor validation=fixture_only");return ok;}
int wideUiPhysicalWidth(){return originalWidth;}
int wideUiCanvasWidth(){return virtualWidth;}
#ifdef WIDE_UI_TEST
void configureWideUiWriteFailureFixture(int site){failingWrite=site;}
void initializeWideUiFixture(BYTE* image){memset(image,0,0x10b000);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.SizeOfImage=0x10b000;expected(image);for(auto& s:sites)memcpy(image+s.rva,s.original,s.count);}
void configureWideUiMouseFixture(Warp fn){originalWarp=fn;}
#endif
