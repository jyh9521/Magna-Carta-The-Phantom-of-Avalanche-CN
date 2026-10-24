#include "dialogue_reveal.h"
#include "native_text_step.h"
#include <cstdio>
#include <cstring>
#include <filesystem>
int wmain(int argc,wchar_t** argv){
 if(argc!=2)return 2;
 HMODULE image=LoadLibraryExW(argv[1],nullptr,DONT_RESOLVE_DLL_REFERENCES);
 if(!image){printf("FAIL map_image error=%lu\n",GetLastError());return 1;}
 // Mapping without resolving imports now also requires an explicit bounded
 // pause-stream import. Resolve that one SDK symbol; never run game entry.
 auto sdkPath=std::filesystem::path(argv[1]).parent_path()/L"Mss32.dll";
 HMODULE sdk=LoadLibraryExW(sdkPath.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
 if(!sdk){puts("FAIL source_sdk_load");return 1;}
 auto pause=GetProcAddress(sdk,"_AIL_pause_stream@8");if(!pause){puts("FAIL source_pause_api");return 1;}
 auto p=reinterpret_cast<BYTE*>(image);DWORD sourcePause=*reinterpret_cast<DWORD*>(p+0xbd4ec),protect=0,ignored=0;
 if(!VirtualProtect(p+0xbd4ec,4,PAGE_READWRITE,&protect))return 1;
 *reinterpret_cast<DWORD*>(p+0xbd4ec)=DWORD(pause);VirtualProtect(p+0xbd4ec,4,protect,&ignored);
unsigned slots[]={0xbfcf0,0xbfd10,0xbfee8,0xbff08};DWORD before[4]{};
 for(unsigned i=0;i<4;++i)before[i]=*reinterpret_cast<DWORD*>(p+slots[i]);
 MEMORY_BASIC_INFORMATION m{};VirtualQuery(p,&m,sizeof(m));
 printf("MAPPED_IMAGE header_region=0x%lx image_size=0x10b000 entrypoint_executed=false\n",static_cast<unsigned long>(m.RegionSize));
 if(!installNativeTextStep(image)){puts("FAIL native_text_step");return 1;}
 if(!installDialogueReveal(image,nullptr)){puts("FAIL DIALOGUE_REVEAL_REJECTED mapped_image=true");FreeLibrary(image);return 1;}
 if(!removeDialogueReveal(image)){puts("FAIL rollback");return 1;}
 for(unsigned i=0;i<4;++i)if(before[i]!=*reinterpret_cast<DWORD*>(p+slots[i])){puts("FAIL slot_restore");return 1;}
 if(!setNativeTextStep(p,0x10b000,false)){puts("FAIL text_step_restore");return 1;}
 if(*reinterpret_cast<DWORD*>(p+0xbd4ec)!=DWORD(pause)){puts("FAIL pause_import_restore");return 1;}
 if(!VirtualProtect(p+0xbd4ec,4,PAGE_READWRITE,&protect))return 1;
 *reinterpret_cast<DWORD*>(p+0xbd4ec)=sourcePause;VirtualProtect(p+0xbd4ec,4,protect,&ignored);
 puts("DIALOGUE_IMAGE_FIXTURE PASS mapped_image=true production_guards=true rollback=exact entrypoint_executed=false game_started=false");
 FreeLibrary(image);FreeLibrary(sdk);return 0;
}
