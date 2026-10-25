#include "frame_overlay.h"
#include "encounter_control.h"
#include <cstdio>
#include <cstring>
#include <vector>
static unsigned ends=0;
HRESULT WINAPI endScene(void*){++ends;return S_OK;}
static HDC dc;static DWORD* bits;static unsigned presents=0,gets=0,releases=0;static bool acquired=false,lost=false;
static HDC mapDC=nullptr;static DWORD* mapBits=nullptr;
bool alphaMap(int,int,FramePanel& p){p={10,10,64,64,mapBits,mapDC};return true;}
static DWORD caption[200*40];static bool captionEnabled=true;
void require(bool x,const char* m){if(!x){printf("FRAME_OVERLAY FAIL %s\n",m);fflush(stdout);ExitProcess(1);}}
HRESULT WINAPI getDC(void*,HDC* out){++gets;if(lost)return E_FAIL;acquired=true;*out=dc;return S_OK;}
HRESULT WINAPI releaseDC(void*,HDC h){require(acquired&&h==dc,"balanced backbuffer DC");acquired=false;++releases;return S_OK;}
BYTE __fastcall present(void*,void*){require(!acquired,"release before present");require(GetLastError()==0x1234,"native LastError retained");++presents;return 1;}
bool panel(int,int,FramePanel& p){if(!captionEnabled)return false;p={20,20,200,40,caption};return true;}
void black(){GdiFlush();memset(bits,0,640*360*4);}
int main(int argc,char** argv){
 auto parent=CreateWindowExW(0,L"STATIC",L"owned render root",WS_OVERLAPPED,0,0,64,64,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
 auto child=CreateWindowExW(0,L"STATIC",L"",WS_CHILD,0,0,32,32,parent,nullptr,GetModuleHandleW(nullptr),nullptr);
 auto other=CreateWindowExW(0,L"STATIC",L"owned other root",WS_OVERLAPPED,0,0,64,64,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
 require(parent&&child&&other,"owned hidden window hierarchy");require(frameOverlayFixtureWindow(child,parent),"render child matches foreground root without engine window initialization");require(!frameOverlayFixtureWindow(child,other)&&!frameOverlayFixtureWindow(nullptr,parent),"other root and absent render window excluded");DestroyWindow(child);DestroyWindow(parent);DestroyWindow(other);
 bool baseline=argc>1&&!strcmp(argv[1],"--baseline");
 auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
 auto driver=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2c000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
 auto renderer=static_cast<BYTE*>(VirtualAlloc(nullptr,0x122f20,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
 require(image&&driver&&renderer,"owned allocations");initializeFrameOverlayFixture(image,driver);frameOverlayFixtureDriver(driver);
 *reinterpret_cast<BYTE**>(renderer)=driver+0x1a5a8;*reinterpret_cast<void**>(driver+0x1a5a8+0x14)=reinterpret_cast<void*>(&present);
 void* deviceMethods[7]{};deviceMethods[6]=reinterpret_cast<void*>(&endScene);void** device=deviceMethods;*reinterpret_cast<void**>(renderer+0x2c)=&device;*reinterpret_cast<unsigned*>(renderer+0x122f1c)=1;
 BYTE back[0x90]{};void* methods[27]{};methods[17]=reinterpret_cast<void*>(&getDC);methods[26]=reinterpret_cast<void*>(&releaseDC);void** surface=methods;
 *reinterpret_cast<void**>(back+4)=&surface;*reinterpret_cast<int*>(back+0x88)=640;*reinterpret_cast<int*>(back+0x8c)=360;
 *reinterpret_cast<BYTE**>(renderer+0x38)=back;*reinterpret_cast<BYTE**>(image+0xf1b70)=renderer;
 BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=640;info.bmiHeader.biHeight=-360;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
 dc=CreateCompatibleDC(nullptr);auto bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,reinterpret_cast<void**>(&bits),nullptr,0);require(dc&&bitmap&&bits,"owned memory DC");auto old=SelectObject(dc,bitmap);
 for(auto& p:caption)p=0x00eeeeee;
 std::vector<BYTE> original(image,image+0x10b000);
 setFramePanel(0,&panel);setFramePanel(1,&encounterFramePanel);
 encounterTestReset();BYTE keys[256]{};encounterKeyboard(keys,true);keys[VK_F5]=0x80;encounterKeyboard(keys,true);
 require(!encountersEnabled(),"first F5 edge toggles");
 if(!baseline){require(installFrameOverlay(HMODULE(image),nullptr),"install");require(installFrameOverlay(HMODULE(image),nullptr),"idempotent");}
 auto run=[&](){black();SetLastError(0x1234);reinterpret_cast<void(__cdecl*)()>(image+0xc20c)();GdiFlush();};
 run();if(baseline){require(bits[20*640+20]==0,"original curtain has no subtitle");puts("FRAME_OVERLAY BASELINE first_F5=invisible caption=under_curtain game_started=false");return 1;}
 require(bits[20*640+20]==0xeeeeee&&bits[0]==0,"subtitle above unchanged black curtain");
 require(bits[(360-24-8)*640+(640-240-8)]!=0,"F5 visible on cold first frame without window registration");
 require(presents==1&&gets==1&&releases==1&&ends==1&&!*reinterpret_cast<unsigned*>(renderer+0x122f1c),"exact first-frame EndScene/DC/present pipeline");
 frameOverlayFixtureFocus(false);run();require(bits[20*640+20]==0&&gets==1,"focus loss bypass");frameOverlayFixtureFocus(true);
 lost=true;run();require(gets==2&&releases==1,"lost surface no retry");lost=false;
 captionEnabled=false;encounterTestReset();unsigned q=gets;run();require(gets==q,"no panels no DC acquisition");
 // Third provider blends only once, BEFORE captions/notifications, into the same retained surface.
 info.bmiHeader.biWidth=64;info.bmiHeader.biHeight=-64;
 mapDC=CreateCompatibleDC(nullptr);auto mapBitmap=CreateDIBSection(mapDC,&info,DIB_RGB_COLORS,reinterpret_cast<void**>(&mapBits),nullptr,0);auto mapOld=SelectObject(mapDC,mapBitmap);
 for(unsigned i=0;i<64*64;++i)mapBits[i]=0x80643219;mapBits[0]=0;
 setFramePanel(2,&alphaMap);captionEnabled=true;unsigned oldGets=gets,oldPresents=presents;run();
 require((bits[15*640+15]&0xffffff)==0x643219,"premultiplied map alpha blends into retained surface");
 require(bits[10*640+10]==0,"transparent map pixel preserves scene");
 require((bits[20*640+20]&0xffffff)==0xeeeeee,"captions remain above map");
 require(gets==oldGets+1&&presents==oldPresents+1,"map has one DC and one native present, no independent window");
 setFramePanel(2,nullptr);captionEnabled=false;SelectObject(mapDC,mapOld);DeleteObject(mapBitmap);DeleteDC(mapDC);
 puts("MAP_FRAME_COMPOSITOR PASS alpha=premultiplied transparent=preserved layer_order=map_caption_notice presents=one window_dc=false");
 require(removeFrameOverlay(HMODULE(image)),"remove");require(!memcmp(original.data(),image,original.size()),"whole image rollback exact");
 run();require(bits[20*640+20]==0,"original behavior restored");
 image[0xc20c]^=1;require(!installFrameOverlay(HMODULE(image),nullptr),"source mismatch rejected");
 SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);
 puts("FRAME_OVERLAY PASS cold_F5=first_frame caption=above_curtain native_present=once focus=guarded surface_loss=no_retry rollback=byte_exact game_started=false");return 0;
}
