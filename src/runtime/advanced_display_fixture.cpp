#include "advanced_display.h"
#include <iostream>
#include <stdexcept>
#include <cmath>
#include <vector>
#include <cstring>
static unsigned checks=0;static double captured=0;static unsigned presents=0;
void check(bool b){++checks;if(!b)throw std::runtime_error("advanced display fixture failed");}
struct Fake {BYTE data[0x58]{};int mode=0x1701;void __thiscall projection(double f,double a,double n,double z){check(f==45&&n==1&&z==1000);captured=a;} BYTE __thiscall present(){++presents;return 7;} };
int main(){try{
    auto e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    auto d=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2c000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));check(e&&d);
    initializeAdvancedEngineFixture(e);check(e[0xce5c]==0x77);check(setRenderWait(e,0x10b000,true));check(e[0xce5c]==0xeb);check(setRenderWait(e,0x10b000,true));check(setRenderWait(e,0x10b000,false));check(e[0xce5c]==0x77);
    e[0xcf04]^=1;check(!setRenderWait(e,0x10b000,true));check(e[0xce5c]==0x77);e[0xcf04]^=1;
    // Owned FPS reciprocal stub tests zero delta without altering the system clock.
    double fpsValue=0;BYTE fpsStub[]={0x55,0x8b,0xec,0x83,0xec,0x2c,0xc7,0x45,0xd4,0,0,0,0,0xe9,0,0,0,0};
    *reinterpret_cast<float*>(fpsStub+9)=16.0f;*reinterpret_cast<int32_t*>(fpsStub+14)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(e+0xcecc)-reinterpret_cast<ULONG_PTR>(e+0x500+18));
    memcpy(e+0x500,fpsStub,sizeof(fpsStub));e[0xced5]=0xdd;e[0xced6]=0x1d;*reinterpret_cast<DWORD*>(e+0xced7)=reinterpret_cast<DWORD>(&fpsValue);e[0xcedb]=0xc9;e[0xcedc]=0xc3;
    DWORD executableOld;check(VirtualProtect(e,0x10b000,PAGE_EXECUTE_READWRITE,&executableOld));
    using FpsCall=void(__cdecl*)();auto fpsCall=reinterpret_cast<FpsCall>(e+0x500);fpsCall();check(fpsValue==62.5);
    check(installAdvancedEngine(reinterpret_cast<HMODULE>(e),false,true,nullptr));check(installAdvancedEngine(reinterpret_cast<HMODULE>(e),false,true,nullptr));fpsCall();check(fpsValue==62.5);
    *reinterpret_cast<float*>(e+0x509)=0;fpsCall();check(fpsValue==0&&std::isfinite(fpsValue));
    check(setZeroDeltaFps(e,0x10b000,false));*reinterpret_cast<float*>(e+0x509)=16;fpsCall();check(fpsValue==62.5);check(setRenderWait(e,0x10b000,false));check(e[0xce5c]==0x77);
    // Owned x86 call stub exercises the aspect-storage thunk with preserved EBP/registers.
    double aspectData=4.0/3.0;BYTE camera[0x40]{};
    BYTE stub[]={0x55,0x8b,0xec,0x83,0xec,0x04,0xc7,0x45,0xfc,0,0,0,0,0xba,0,0,0,0,0xdd,0x05,0,0,0,0,0xe9,0,0,0,0};
    *reinterpret_cast<DWORD*>(stub+9)=reinterpret_cast<DWORD>(camera);*reinterpret_cast<DWORD*>(stub+14)=reinterpret_cast<DWORD>(camera);*reinterpret_cast<DWORD*>(stub+20)=reinterpret_cast<DWORD>(&aspectData);
    *reinterpret_cast<int32_t*>(stub+25)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(e+0x1d4b5)-reinterpret_cast<ULONG_PTR>(e+0x400+29));
    memcpy(e+0x400,stub,sizeof(stub));e[0x1d4bb]=0xc9;e[0x1d4bc]=0xc3;DWORD oldProtect;check(VirtualProtect(e,0x10b000,PAGE_EXECUTE_READWRITE,&oldProtect));
    using CameraCall=void(__cdecl*)();auto cameraCall=reinterpret_cast<CameraCall>(e+0x400);cameraCall();check(*reinterpret_cast<double*>(camera+0x18)==4.0/3.0);
    check(setCameraAspect(e,0x10b000,true));cameraCall();check(std::abs(*reinterpret_cast<double*>(camera+0x18)-16.0/9.0)<1e-9);
    aspectData=2.0;cameraCall();check(*reinterpret_cast<double*>(camera+0x18)==2.0);
    check(setCameraAspect(e,0x10b000,false));aspectData=4.0/3.0;cameraCall();check(*reinterpret_cast<double*>(camera+0x18)==4.0/3.0);
    // A full minute of presentation at 30 and 60Hz retains the same 33ms updates.
    unsigned rem30=0,rem60=0,updates30=0,updates60=0,last30=0,last60=0;
    for(unsigned i=1;i<=1800;++i){unsigned now=i*60000/1800;updates30+=fixedUpdates(now-last30,rem30);last30=now;}
    for(unsigned i=1;i<=3600;++i){unsigned now=i*60000/3600;updates60+=fixedUpdates(now-last60,rem60);last60=now;}
    check(updates30==1818&&updates60==1818&&rem30==rem60);check(fixedUpdates(0,rem60)==0);
    unsigned huge=0;check(fixedUpdates(1000,huge)==5&&huge==0);
    check(std::abs(expandedAspect(4.0/3.0,0x1701,true)-16.0/9.0)<1e-9);
    check(expandedAspect(4.0/3.0,0x1700,true)==4.0/3.0);check(expandedAspect(2,0x1701,true)==2);
    initializeAdvancedDriverFixture(d);DWORD projectionBefore=*reinterpret_cast<DWORD*>(d+0x1ab28),frameBefore=*reinterpret_cast<DWORD*>(d+0x1a5bc);
    d[0x85cd]=0;check(!installAdvancedDriver(reinterpret_cast<HMODULE>(d),true,true,nullptr));check(*reinterpret_cast<DWORD*>(d+0x1ab28)==projectionBefore);d[0x85cd]=0x55;
    check(installAdvancedDriver(reinterpret_cast<HMODULE>(d),true,true,nullptr));check(installAdvancedDriver(reinterpret_cast<HMODULE>(d),true,true,nullptr));
    // MSVC x86 single-inheritance member pointers carry the matching thiscall code address.
    auto pm=&Fake::projection;auto fm=&Fake::present;PerspectiveFn p{};PresentFn f{};static_assert(sizeof(pm)==sizeof(p));memcpy(&p,&pm,sizeof(p));memcpy(&f,&fm,sizeof(f));configureAdvancedFixture(p,f);
    Fake fake;auto wide=reinterpret_cast<PerspectiveFn>(*reinterpret_cast<DWORD*>(d+0x1ab28));wide(&fake,45,4.0/3.0,1,1000);check(std::abs(captured-16.0/9.0)<1e-9);
    fake.mode=0x1700;wide(&fake,45,4.0/3.0,1,1000);check(captured==4.0/3.0);
    auto present=reinterpret_cast<PresentFn>(*reinterpret_cast<DWORD*>(d+0x1a5bc));LARGE_INTEGER start,end,freq;QueryPerformanceFrequency(&freq);QueryPerformanceCounter(&start);
    for(unsigned i=0;i<61;++i)check(present(&fake)==7);
    QueryPerformanceCounter(&end);double elapsed=(end.QuadPart-start.QuadPart)/static_cast<double>(freq.QuadPart);check(elapsed>=0.95&&elapsed<3.0&&presents==61);
    *reinterpret_cast<DWORD*>(d+0x1ab28)=projectionBefore;*reinterpret_cast<DWORD*>(d+0x1a5bc)=frameBefore;check(*reinterpret_cast<DWORD*>(d+0x1ab28)==projectionBefore&&*reinterpret_cast<DWORD*>(d+0x1a5bc)==frameBefore);
    VirtualFree(e,0,MEM_RELEASE);VirtualFree(d,0,MEM_RELEASE);
    std::cout<<"ADVANCED_DISPLAY_FIXTURE PASS checks="<<checks<<" frames30=1800 frames60=3600 updates30=1818 updates60=1818 projection=hor_plus orthographic=unchanged pacing_seconds="<<elapsed<<" return=preserved mismatch=rejected rollback=exact commercial_code_executed=false game_started=false\n";return 0;
}catch(const std::exception& ex){std::cerr<<ex.what()<<'\n';return 1;}}
