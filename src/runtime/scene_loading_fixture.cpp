#include "scene_loading.h"
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>
namespace {
HDC dc=nullptr;DWORD* bits=nullptr;
int presents=0,cleanups=0,gets=0,releases=0;bool dcActive=false,failGet=false,failRelease=false;
BYTE* image=nullptr;void* job=reinterpret_cast<void*>(0x12345678);
using Invoke=void(__thiscall*)(void*);
void require(bool v,const char* m){if(!v){printf("FAIL %s\n",m);std::exit(5);}}
HRESULT WINAPI getDC(void*,HDC* out){++gets;if(failGet)return E_FAIL;*out=dc;dcActive=true;return S_OK;}
HRESULT WINAPI releaseDC(void*,HDC value){require(value==dc&&dcActive,"release matching DC");++releases;dcActive=false;return failRelease?E_FAIL:S_OK;}
BYTE __fastcall present(void*,void*){require(!dcActive&&releases==1,"release before native present");GdiFlush();require(bits[0]==0x101620,"old frame replaced before present");++presents;return 1;}
void __fastcall clean(void* value,void*){
 require(value==job&&!dcActive,"cleanup receiver and released DC preserved");require(GetLastError()==0x4567,"last error preserved");++cleanups;
}
void jump(BYTE* at,void* target){at[0]=0xe9;DWORD d=DWORD(reinterpret_cast<uintptr_t>(target)-reinterpret_cast<uintptr_t>(at+5));memcpy(at+1,&d,4);}
void reset(){GdiFlush();for(int i=0;i<320*180;++i)bits[i]=0x00ff00;presents=cleanups=gets=releases=0;failGet=failRelease=false;dcActive=false;SetLastError(0x4567);}
void run(){reinterpret_cast<Invoke>(image+0x63075)(job);GdiFlush();}
void bmp(const char* name){FILE* f=nullptr;require(!fopen_s(&f,name,"wb")&&f,"open BMP");BITMAPFILEHEADER head{};head.bfType=0x4d42;head.bfOffBits=sizeof(head)+sizeof(BITMAPINFOHEADER);head.bfSize=head.bfOffBits+320*180*4;BITMAPINFOHEADER info{};info.biSize=sizeof(info);info.biWidth=320;info.biHeight=-180;info.biPlanes=1;info.biBitCount=32;info.biCompression=BI_RGB;fwrite(&head,1,sizeof(head),f);fwrite(&info,1,sizeof(info),f);fwrite(bits,4,320*180,f);fclose(f);}
}
int main(int argc,char** argv){
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
 auto driver=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2c000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
 auto renderer=static_cast<BYTE*>(VirtualAlloc(nullptr,0x122f20,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
 require(image&&driver&&renderer,"owned allocations");initializeSceneLoadingFixture(image,driver);setSceneLoadingFixtureDriver(driver);
 *reinterpret_cast<BYTE***>(renderer)=reinterpret_cast<BYTE**>(driver+0x1a5a8);
 *reinterpret_cast<void**>(driver+0x1a5a8+0x14)=reinterpret_cast<void*>(&present);
 BYTE back[0x90]{};void* methods[27]{};methods[17]=reinterpret_cast<void*>(&getDC);methods[26]=reinterpret_cast<void*>(&releaseDC);
 void** surface=methods;*reinterpret_cast<void**>(back+4)=&surface;*reinterpret_cast<int*>(back+0x88)=320;*reinterpret_cast<int*>(back+0x8c)=180;
 *reinterpret_cast<BYTE**>(renderer+0x38)=back;*reinterpret_cast<BYTE**>(image+0xf1b70)=renderer;*reinterpret_cast<int*>(image+0xf2280)=31;
 image[0x6307a]=0xc3;jump(image+0x6315b,reinterpret_cast<void*>(&clean));
 BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=320;info.bmiHeader.biHeight=-180;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
 dc=CreateCompatibleDC(nullptr);auto bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,reinterpret_cast<void**>(&bits),nullptr,0);require(dc&&bitmap&&bits,"memory DIB only, no window");auto old=SelectObject(dc,bitmap);
 const char* mode=argc>1?argv[1]:"verify";bool baseline=!strcmp(mode,"baseline"),rollback=!strcmp(mode,"rollback");
 reset();run();require(presents==0&&cleanups==1&&bits[0]==0x00ff00,"baseline retains old frame");
 if(baseline){puts("SCENE_LOADING BASELINE retained_old_frame=true presents=0 cleanup=1 game_started=false");return 1;}
 require(installSceneLoading(reinterpret_cast<HMODULE>(image),nullptr),"install");require(installSceneLoading(reinterpret_cast<HMODULE>(image),nullptr),"repeat install");
 if(rollback){require(removeSceneLoading(reinterpret_cast<HMODULE>(image)),"rollback");reset();run();require(presents==0&&cleanups==1&&bits[0]==0x00ff00,"rollback restores old behavior");puts("SCENE_LOADING ROLLBACK restored_old_frame=true presents=0 cleanup=1 game_started=false");return 1;}
 reset();run();require(presents==1&&cleanups==1&&gets==1&&releases==1,"loading before exact cleanup");
 int lit=0;for(int i=0;i<320*180;++i)lit+=bits[i]==0xe6edf3;require(lit>400,"visible owned caption");if(argc>2)bmp(argv[2]);
 reset();*reinterpret_cast<int*>(image+0xf2280)=4;run();require(gets==0&&presents==0&&cleanups==1,"menu bypass");*reinterpret_cast<int*>(image+0xf2280)=31;
 reset();*reinterpret_cast<int*>(renderer+0x122f1c)=1;run();require(gets==0&&cleanups==1,"active scene bypass");*reinterpret_cast<int*>(renderer+0x122f1c)=0;
 reset();failGet=true;run();require(gets==1&&releases==0&&presents==0&&cleanups==1,"GetDC failure cleanup unchanged");
 reset();failRelease=true;run();require(releases==1&&presents==0&&cleanups==1,"ReleaseDC failure no present");
 reset();*reinterpret_cast<int*>(back+0x88)=0;run();require(gets==0&&cleanups==1,"invalid dimensions bypass");*reinterpret_cast<int*>(back+0x88)=320;
 reset();*reinterpret_cast<BYTE**>(renderer)=nullptr;run();require(gets==0&&cleanups==1,"foreign renderer bypass");*reinterpret_cast<BYTE***>(renderer)=reinterpret_cast<BYTE**>(driver+0x1a5a8);
 require(removeSceneLoading(reinterpret_cast<HMODULE>(image)),"remove");require(removeSceneLoading(reinterpret_cast<HMODULE>(image)),"repeat remove");
 reset();run();require(presents==0&&cleanups==1&&bits[0]==0x00ff00,"exact native behavior restored");
 image[0x63075]=0xcc;require(!installSceneLoading(reinterpret_cast<HMODULE>(image),nullptr),"foreign call rejected");image[0x63075]=0xe8;
 image[0x631a0]=0xcc;require(!installSceneLoading(reinterpret_cast<HMODULE>(image),nullptr),"loop drift rejected");image[0x631a0]=0x55;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->FileHeader.TimeDateStamp=0;require(!installSceneLoading(reinterpret_cast<HMODULE>(image),nullptr),"unknown version rejected");nt->FileHeader.TimeDateStamp=0x3ed73966;
 DWORD protect;require(VirtualProtect(image+0x63000,0x1000,PAGE_EXECUTE_READ,&protect)!=0,"RX page");require(installSceneLoading(reinterpret_cast<HMODULE>(image),nullptr)&&removeSceneLoading(reinterpret_cast<HMODULE>(image)),"RX install rollback");MEMORY_BASIC_INFORMATION region{};VirtualQuery(image+0x63075,&region,sizeof(region));require(region.Protect==PAGE_EXECUTE_READ,"RX restored");
 SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);VirtualFree(renderer,0,MEM_RELEASE);VirtualFree(driver,0,MEM_RELEASE);VirtualFree(image,0,MEM_RELEASE);
 puts("SCENE_LOADING MODIFIED PASS order=draw_release_present_cleanup rollback=exact guarded_cases=passed game_started=false");return 0;
}
