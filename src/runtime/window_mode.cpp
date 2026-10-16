#include "window_mode.h"
#include <cstring>
bool setNativeWindowed(BYTE* image,size_t available,bool enabled){
 if(!image||available<0x10b000)return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+dos->e_lfanew);
 if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 // 原生设置装载器：mov dword ptr [engine+f1b40],1；仅将立即数切换为0。
 BYTE expected[]={0xc7,0x05,0,0,0,0,1,0,0,0};
 *reinterpret_cast<DWORD*>(expected+2)=reinterpret_cast<DWORD>(image+0xf1b40);
 BYTE* site=image+0x9a0e;
 if(memcmp(site,expected,6)||site[6]>1||memcmp(site+7,expected+7,3))return false;
 BYTE desired=enabled?0:1;if(site[6]==desired)return true;
 DWORD old=0;if(!VirtualProtect(site+6,1,PAGE_EXECUTE_READWRITE,&old))return false;
 BYTE before=site[6];site[6]=desired;
 bool ok=FlushInstructionCache(GetCurrentProcess(),site+6,1)!=FALSE;DWORD unused=0;
 if(!ok||!VirtualProtect(site+6,1,old,&unused)){site[6]=before;FlushInstructionCache(GetCurrentProcess(),site+6,1);VirtualProtect(site+6,1,old,&unused);return false;}
 return true;
}
