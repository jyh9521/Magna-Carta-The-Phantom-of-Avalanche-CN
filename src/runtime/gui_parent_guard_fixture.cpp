#include "gui_parent_guard.h"
#include <cstdio>
#include <cstring>
#include <cstdint>
int main(int argc,char** argv){
 BYTE code[256]{};size_t size=encodeGuiParentGuard(code,0x52000000,0x60001200);
 if(argc==2){FILE* f=nullptr;if(fopen_s(&f,argv[1],"wb")||!f)return 2;bool ok=fwrite(code,1,size,f)==size;fclose(f);if(!ok)return 3;}
 auto p=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));if(!p)return 4;
 initializeGuiParentGuardFixture(p);BYTE original[6];memcpy(original,p+0x38b45,6);
 auto h=reinterpret_cast<HMODULE>(p);
 if(!installGuiParentGuard(h,nullptr)||!installGuiParentGuard(h,nullptr)||!memcmp(original,p+0x38b45,6))return 5;
 // Inspect the installed rel32 target and RX bridge; no commercial code runs.
 auto target=p+0x38b45+5+*reinterpret_cast<LONG*>(p+0x38b45+1);
 BYTE expected[256]{};auto actualSize=encodeGuiParentGuard(expected,DWORD(uintptr_t(p)),DWORD(uintptr_t(target)));
 MEMORY_BASIC_INFORMATION region{};
 if(p[0x38b45]!=0xe9||p[0x38b4a]!=0x90||memcmp(target,expected,actualSize)||!VirtualQuery(target,&region,sizeof(region))||(region.Protect&0xff)!=PAGE_EXECUTE_READ)return 12;
 BYTE hook[6];memcpy(hook,p+0x38b45,6);p[0x38b45]=0xcc;
 if(removeGuiParentGuard(h)||installGuiParentGuard(h,nullptr))return 6;
 memcpy(p+0x38b45,hook,6);
 if(!removeGuiParentGuard(h)||memcmp(original,p+0x38b45,6)||!removeGuiParentGuard(h))return 7;
 DWORD old;
 if(!VirtualProtect(p,0x1000,PAGE_READONLY,&old)||!VirtualProtect(p+0x1000,0x10a000,PAGE_EXECUTE_READ,&old))return 13;
 if(!installGuiParentGuard(h,nullptr)||!removeGuiParentGuard(h))return 14;
 if(!VirtualQuery(p+0x38b45,&region,sizeof(region))||(region.Protect&0xff)!=PAGE_EXECUTE_READ)return 15;
 if(!VirtualProtect(p,0x10b000,PAGE_READWRITE,&old))return 16;
 p[0x38b45]=0xcc;if(installGuiParentGuard(h,nullptr))return 8;memcpy(p+0x38b45,original,6);
 p[0xba4d]=0x55;if(installGuiParentGuard(h,nullptr))return 9;p[0xba4d]=0x54;
 reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100)->FileHeader.TimeDateStamp=0;if(installGuiParentGuard(h,nullptr))return 10;
 if(installGuiParentGuard(nullptr,nullptr))return 11;
 VirtualFree(p,0,MEM_RELEASE);
 printf("GUI_PARENT_GUARD_FIXTURE PASS install=idempotent rollback=exact drift=rejected game_started=false\n");return 0;
}
