#include "title_texture.h"
#include <cstring>
#include <iostream>
#include <vector>
#include <string>
#include <stdexcept>
unsigned checks=0,hardware=2048;std::vector<std::wstring> logs;
void check(bool value){++checks;if(!value)throw std::runtime_error("texture check="+std::to_string(checks));}
void logLine(const wchar_t* value){logs.emplace_back(value);}
unsigned __cdecl legacy(unsigned w,unsigned h,unsigned q){unsigned caps[]={512,256,128};if(w>=h*2)w/=2;else if(h>=w*2)h/=2;unsigned n=w>h?w:h;return q<3?(n<caps[q]?n:caps[q]):73;}
unsigned __cdecl device(unsigned size){return size<hardware?size:hardware;}
void jump(BYTE* p,void* to){p[0]=0xe9;*reinterpret_cast<int*>(p+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(to)-reinterpret_cast<ULONG_PTR>(p+5));}
void call(BYTE* p,void* to){jump(p,to);p[0]=0xe8;}
void header(BYTE* p,DWORD size){auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x80;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x80);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=size;}
int main(int argc,char** argv){try{
 BYTE* e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));BYTE* a=static_cast<BYTE*>(VirtualAlloc(nullptr,0x74d000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(e&&a);header(e,0x10b000);header(a,0x74d000);
 BYTE ec[]={0xff,0x15,0,0,0,0};*reinterpret_cast<DWORD*>(ec+2)=reinterpret_cast<DWORD>(e+0xbd1d0);memcpy(e+0x326e6,ec,6);e[0x326ec]=0xc3;memcpy(e+0x33000,ec,6);e[0x33006]=0xc3;*reinterpret_cast<DWORD*>(e+0xbd1d0)=reinterpret_cast<DWORD>(a+0x53320);
 DWORD caps[]={512,256,128};memcpy(a+0x74fd0,caps,12);jump(a+0x51dd2,reinterpret_cast<void*>(&legacy));
 BYTE sourceA[]={0xe8,0x3e,0xea,0xff,0xff},sourceB[]={0x89,0x45,0xfc,0x8b,0x4d,0x0c};memcpy(a+0x5338f,sourceA,5);memcpy(a+0x533b0,sourceB,6);
 BYTE frame[]={0x55,0x8b,0xec,0x83,0xec,0x0c,0xff,0x75,0x10,0xff,0x75,0x0c,0xff,0x75,0x08};memcpy(a+0x53320,frame,sizeof(frame));jump(a+0x5332f,a+0x5338f);
 BYTE after[]={0x83,0xc4,0x0c,0x50};memcpy(a+0x53394,after,4);call(a+0x53398,reinterpret_cast<void*>(&device));a[0x5339d]=0x83;a[0x5339e]=0xc4;a[0x5339f]=0x04;jump(a+0x533a0,a+0x533b0);BYTE end[]={0x8b,0x45,0xfc,0xc9,0xc3};memcpy(a+0x533b6,end,5);
 BYTE args[]={0xff,0x74,0x24,0x0c,0xff,0x74,0x24,0x0c,0xff,0x74,0x24,0x0c};memcpy(e+0x500,args,12);jump(e+0x50c,e+0x326e6);memcpy(e+0x540,args,12);jump(e+0x54c,e+0x33000);BYTE cleanup[]={0x83,0xc4,0x0c,0xc3};memcpy(e+0x326ec,cleanup,4);memcpy(e+0x33006,cleanup,4);
 using Load=unsigned(__cdecl*)(unsigned,unsigned,unsigned);auto title=reinterpret_cast<Load>(e+0x500),other=reinterpret_cast<Load>(e+0x540);check(title(2048,2048,1)==256);
 if(argc==2&&!strcmp(argv[1],"--baseline-check")){std::cout<<"TITLE_TEXTURE_BASELINE FAIL source=2048 selected=256 pixel_budget=1/64 game_started=false\n";return 1;}
 a[0x533b0]^=1;check(!setTitleTexture(e,a,true,logLine));check(!memcmp(a+0x5338f,sourceA,5));a[0x533b0]^=1;
 *reinterpret_cast<DWORD*>(a+0x74fd4)=255;check(!setTitleTexture(e,a,true,logLine));*reinterpret_cast<DWORD*>(a+0x74fd4)=256;
 check(setTitleTexture(e,a,true,logLine));check(setTitleTexture(e,a,true,logLine));check(title(2048,2048,1)==2048);check(logs.size()==2&&logs[1].find(L"selected=2048")!=std::wstring::npos);check(other(2048,2048,1)==256);check(title(256,256,1)==256);check(title(2048,1024,1)==256);check(title(2048,2048,0)==512);check(title(2048,2048,3)==73);
 hardware=512;check(title(2048,2048,1)==512);check(logs.back().find(L"selected=512")!=std::wstring::npos);hardware=2048;
 check(setTitleTexture(e,a,false,logLine));check(!memcmp(a+0x5338f,sourceA,5)&&!memcmp(a+0x533b0,sourceB,6));check(title(2048,2048,1)==256);check(!memcmp(a+0x74fd0,caps,12));
 VirtualFree(e,0,MEM_RELEASE);VirtualFree(a,0,MEM_RELEASE);std::cout<<"TITLE_TEXTURE_FIXTURE PASS checks="<<checks<<" source=2048 requested=2048 device_caps=retained other_textures=unchanged rollback=256 game_started=false\n";return 0;
}catch(const std::exception& ex){std::cerr<<ex.what()<<'\n';return 1;}}
