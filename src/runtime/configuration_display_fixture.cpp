#include "advanced_display.h"
#include "configuration_display_presets.h"
#include "window_mode.h"
#include <iostream>
#include <stdexcept>
#include <cstring>
static unsigned checks=0;
void check(bool b){++checks;if(!b)throw std::runtime_error("configuration display fixture failed");}
int main(){try{
 for(const auto& p:configurationDisplayPresets){
  check(advancedConfigMatches(p.name,p.hash));check(!advancedConfigMatches(p.name,"unknown"));
  check(advancedProfileWide(p.name));check(advancedProfileRender60(p.name)==p.render60);
 }
 check(!advancedConfigMatches(L"md3-8k-borderless-30",configurationDisplayPresets[0].hash));
 check(!advancedProfileWide(L"unknown"));check(!advancedProfileRender60(L"unknown"));
 auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(image);
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 BYTE instruction[]={0xc7,0x05,0,0,0,0,1,0,0,0,0xc3};
 *reinterpret_cast<DWORD*>(instruction+2)=reinterpret_cast<DWORD>(image+0xf1b40);memcpy(image+0x9a0e,instruction,sizeof(instruction));
 using Store=void(__cdecl*)();auto call=reinterpret_cast<Store>(image+0x9a0e);
 call();check(*reinterpret_cast<DWORD*>(image+0xf1b40)==1);
 check(setNativeWindowed(image,0x10b000,true));call();check(*reinterpret_cast<DWORD*>(image+0xf1b40)==0);
 check(setNativeWindowed(image,0x10b000,true));
 check(setNativeWindowed(image,0x10b000,false));call();check(*reinterpret_cast<DWORD*>(image+0xf1b40)==1);
 check(!memcmp(image+0x9a0e,instruction,sizeof(instruction)));
 for(unsigned i=0;i<10;++i){if(i==6)continue;image[0x9a0e+i]^=1;check(!setNativeWindowed(image,0x10b000,true));image[0x9a0e+i]^=1;}
 check(!setNativeWindowed(image,52,true));image[0x9a14]=2;check(!setNativeWindowed(image,0x10b000,true));image[0x9a14]=1;
 nt->OptionalHeader.SizeOfImage=0x1000;check(!setNativeWindowed(image,0x10b000,true));
 VirtualFree(image,0,MEM_RELEASE);
 std::cout<<"CONFIGURATION_DISPLAY_FIXTURE PASS checks="<<checks<<" profiles=24 native_window_store=0 rollback=1 mismatch=rejected game_started=false"<<std::endl;return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}}
