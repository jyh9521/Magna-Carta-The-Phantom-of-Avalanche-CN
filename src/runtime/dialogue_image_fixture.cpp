#include "dialogue_reveal.h"
#include "native_text_step.h"
#include <cstdio>
#include <cstring>
int wmain(int argc,wchar_t** argv){
 if(argc!=2)return 2;
 HMODULE image=LoadLibraryExW(argv[1],nullptr,DONT_RESOLVE_DLL_REFERENCES);
 if(!image){printf("FAIL map_image error=%lu\n",GetLastError());return 1;}
 auto p=reinterpret_cast<BYTE*>(image);unsigned slots[]={0xbfcf0,0xbfd10,0xbfee8,0xbff08};DWORD before[4]{};
 for(unsigned i=0;i<4;++i)before[i]=*reinterpret_cast<DWORD*>(p+slots[i]);
 MEMORY_BASIC_INFORMATION m{};VirtualQuery(p,&m,sizeof(m));
 printf("MAPPED_IMAGE header_region=0x%lx image_size=0x10b000 entrypoint_executed=false\n",static_cast<unsigned long>(m.RegionSize));
 if(!installNativeTextStep(image)){puts("FAIL native_text_step");return 1;}
 if(!installDialogueReveal(image,nullptr)){puts("FAIL DIALOGUE_REVEAL_REJECTED mapped_image=true");FreeLibrary(image);return 1;}
 if(!removeDialogueReveal(image)){puts("FAIL rollback");return 1;}
 for(unsigned i=0;i<4;++i)if(before[i]!=*reinterpret_cast<DWORD*>(p+slots[i])){puts("FAIL slot_restore");return 1;}
 if(!setNativeTextStep(p,0x10b000,false)){puts("FAIL text_step_restore");return 1;}
 puts("DIALOGUE_IMAGE_FIXTURE PASS mapped_image=true production_guards=true rollback=exact entrypoint_executed=false game_started=false");
 FreeLibrary(image);return 0;
}
