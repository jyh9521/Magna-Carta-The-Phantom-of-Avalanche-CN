#include "advanced_display.h"
#include <intrin.h>
#include <cmath>
#include <cstring>

bool advancedConfigMatches(const std::wstring& mode,const std::string& hash) {
    if(mode==L"baseline")return hash=="0c49061b62b51e4e4dc91458d8c09650d3233895528aea80fafff06ff6b64ea3";
    if(mode==L"render4k")return hash=="ece87e97b2333081e5ef1fda202aa479c8fe14e9aac2fbae4df8adfea0519975";
    if(mode==L"wide4k")return hash=="558b2404afbc166d13b87dd182cfebc2cd1e0c9add5a52e82287d9b762fa5223";
    if(mode==L"fps60")return hash=="1a16654d038fe4ab2ba34db1e6ab5c495750a67eb9d66025ba4a236d0e58cb18";
    if(mode==L"combined")return hash=="6360e39cac131e79393d160ba340d23aa75278038ffe022b60173a3fbf010149";
    return false;
}
double expandedAspect(double original,int mode,bool enabled) {
    // Only the original 4:3 perspective. Never alter orthographic or nonstandard shots.
    if(enabled&&mode==0x1701&&std::isfinite(original)&&std::abs(original-4.0/3.0)<0.002)return 16.0/9.0;
    return original;
}
unsigned fixedUpdates(unsigned elapsed,unsigned& remaining,unsigned interval) {
    if(!interval)return 0;
    unsigned long long sum=static_cast<unsigned long long>(remaining)+elapsed;
    unsigned n=static_cast<unsigned>(sum/interval);if(n>5)n=5;
    remaining=n==5?0:static_cast<unsigned>(sum-n*interval);return n;
}
namespace {
constexpr BYTE waitGuard[]={0x8b,0x45,0xf8,0x8b,0x50,0x08,0x8b,0x45,0xf8,0x03,0x50,0x18,0x3b,0xca,0x77,0x09};
constexpr BYTE updateGuard[]={0x8b,0x50,0x10,0x3b,0x51,0x08,0x73,0x02,0xeb,0x46};
constexpr BYTE projectionPrefix[]={0x55,0x8b,0xec,0x81,0xec,0xd8,0x01,0x00,0x00,0x56,0x57};
constexpr BYTE presentPrefix[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc};
constexpr BYTE cameraStore[]={0xdd,0x5a,0x18,0x8b,0x45,0xfc};
ULONG_PTR cameraResume=0;volatile LONG cameraWrites=0;
double __cdecl correctedCameraAspect(double value){double changed=expandedAspect(value,0x1701,true);if(changed!=value)InterlockedIncrement(&cameraWrites);return changed;}
__declspec(naked) void cameraThunk() {
    __asm {
        pushfd
        pushad
        sub esp,8
        fstp qword ptr [esp]
        call correctedCameraAspect
        add esp,8
        popad
        popfd
        fstp qword ptr [edx+18h]
        mov eax,dword ptr [ebp-4]
        jmp dword ptr [cameraResume]
    }
}
using Perspective=void(__thiscall*)(void*,double,double,double,double);
using Present=BYTE(__thiscall*)(void*);
Perspective originalPerspective=nullptr;Present originalPresent=nullptr;
bool widen=false,pace=false;
ULONG_PTR fpsResume=0;
double __cdecl safeFps(float elapsed){return std::isfinite(elapsed)&&elapsed>0?1000.0/elapsed:0.0;}
__declspec(naked) void fpsThunk() {
    __asm {
        pushfd
        pushad
        push dword ptr [ebp-2ch]
        call safeFps
        add esp,4
        popad
        popfd
        jmp dword ptr [fpsResume]
    }
}
void(*trace)(const wchar_t*)=nullptr;
SRWLOCK paceLock=SRWLOCK_INIT;
LONGLONG deadline=0,frequency=0,windowStart=0;unsigned frameCount=0,projectionCount=0;
void* lastObject=nullptr;
HANDLE pacingTimer=nullptr;bool timerTried=false;
bool imageMatches(BYTE* p,size_t n,DWORD expected) {
    if(!p||n<expected)return false;
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);
    return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&
        nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&nt->OptionalHeader.SizeOfImage==expected;
}
bool writeMemory(void* p,const void* data,size_t count) {
    DWORD old;if(!VirtualProtect(p,count,PAGE_EXECUTE_READWRITE,&old))return false;
    BYTE before[16];if(count>sizeof(before)){DWORD unused;VirtualProtect(p,count,old,&unused);return false;}
    memcpy(before,p,count);memcpy(p,data,count);
    bool ok=FlushInstructionCache(GetCurrentProcess(),p,count)!=FALSE;DWORD ignored;
    if(!ok||!VirtualProtect(p,count,old,&ignored)) {
        memcpy(p,before,count);FlushInstructionCache(GetCurrentProcess(),p,count);VirtualProtect(p,count,old,&ignored);return false;
    }
    return true;
}
void __fastcall projectionHook(void* object,void*,double fov,double aspect,double nearZ,double farZ) {
    int mode=*reinterpret_cast<int*>(static_cast<BYTE*>(object)+0x58);
    double changed=expandedAspect(aspect,mode,widen);
    if((changed!=aspect||(cameraWrites&&std::abs(aspect-16.0/9.0)<0.002))&&projectionCount++==0&&trace)trace(L"WIDE_PROJECTION_APPLIED aspect=1.333333->1.777778 vertical_fov=unchanged camera_aspect=corrected");
    originalPerspective(object,fov,changed,nearZ,farZ);
}
BYTE __fastcall presentHook(void* object,void*) {
    BYTE result=originalPresent(object);
    if(!pace)return result;
    AcquireSRWLockExclusive(&paceLock);
    LARGE_INTEGER now{};QueryPerformanceCounter(&now);
    if(!frequency){LARGE_INTEGER f{};if(QueryPerformanceFrequency(&f))frequency=f.QuadPart;}
    if(frequency) {
        LONGLONG period=frequency/60;
        if(!deadline||lastObject!=object||now.QuadPart>deadline+frequency/4){deadline=now.QuadPart;lastObject=object;windowStart=now.QuadPart;frameCount=0;}
        if(!timerTried){timerTried=true;pacingTimer=CreateWaitableTimerExW(nullptr,nullptr,0x00000002,TIMER_ALL_ACCESS);}
        while(now.QuadPart<deadline){
            LONGLONG remaining=deadline-now.QuadPart;
            if(pacingTimer&&remaining>frequency/1000){
                LARGE_INTEGER due{};due.QuadPart=-((remaining-frequency/2000)*10000000/frequency);
                if(SetWaitableTimer(pacingTimer,&due,0,nullptr,nullptr,FALSE))WaitForSingleObject(pacingTimer,1000);else Sleep(0);
            }else Sleep(0);
            QueryPerformanceCounter(&now);
        }
        deadline=now.QuadPart+period;
        if(++frameCount>=120){
            if(trace&&now.QuadPart>windowStart){wchar_t text[180];swprintf_s(text,L"RENDER_PACING frames=%u update_frame_hz=%.3f logic_interval_ms=33",frameCount,frameCount*static_cast<double>(frequency)/(now.QuadPart-windowStart));trace(text);}
            frameCount=0;windowStart=now.QuadPart;
        }
    }
    ReleaseSRWLockExclusive(&paceLock);return result;
}
}
bool setRenderWait(BYTE* image,size_t available,bool unlocked) {
    if(!imageMatches(image,available,0x10b000)||memcmp(image+0xcf01,updateGuard,sizeof(updateGuard)))return false;
    for(size_t i=0;i<sizeof(waitGuard);++i)if(i!=14&&image[0xce4e+i]!=waitGuard[i])return false;
    BYTE old=image[0xce5c];if(old!=0x77&&old!=0xeb)return false;
    BYTE desired=unlocked?0xeb:0x77;return old==desired||writeMemory(image+0xce5c,&desired,1);
}
bool setCameraAspect(BYTE* p,size_t available,bool enabled) {
    if(!imageMatches(p,available,0x10b000))return false;
    BYTE patch[6]={0xe9,0,0,0,0,0x90};
    *reinterpret_cast<int32_t*>(patch+1)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(&cameraThunk)-reinterpret_cast<ULONG_PTR>(p+0x1d4ba));
    if(memcmp(p+0x1d4b5,cameraStore,6)&&memcmp(p+0x1d4b5,patch,6))return false;
    cameraResume=reinterpret_cast<ULONG_PTR>(p+0x1d4bb);
    return writeMemory(p+0x1d4b5,enabled?patch:cameraStore,6);
}
bool installAdvancedEngine(HMODULE module,bool wide,bool render60,void(*logger)(const wchar_t*)) {
    auto p=reinterpret_cast<BYTE*>(module);
    if(!imageMatches(p,0x10b000,0x10b000))return false;
    if(wide&&!setCameraAspect(p,0x10b000,true))return false;
    if(!render60){if(logger)logger(L"WIDE_CAMERA_READY field=aspect source_locked=true");return true;}
    BYTE old=p[0xce5c];if(!setRenderWait(p,0x10b000,true))return false;
    if(!setZeroDeltaFps(p,0x10b000,true)){setRenderWait(p,0x10b000,old==0xeb);return false;}
    if(logger)logger(L"RENDER_WAIT_UNLOCKED logic_interval_ms=33 real_clock=unchanged zero_delta=guarded");
    return true;
}
bool setZeroDeltaFps(BYTE* p,size_t available,bool enabled) {
    if(!imageMatches(p,available,0x10b000)||*reinterpret_cast<float*>(p+0xbd654)!=1000.0f)return false;
    BYTE original[]={0xd9,0x05,0,0,0,0,0xd8,0x75,0xd4};*reinterpret_cast<DWORD*>(original+2)=reinterpret_cast<DWORD>(p+0xbd654);
    BYTE patch[]={0xe9,0,0,0,0,0x90,0x90,0x90,0x90};*reinterpret_cast<int32_t*>(patch+1)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(&fpsThunk)-reinterpret_cast<ULONG_PTR>(p+0xced1));
    if(memcmp(p+0xcecc,original,9)&&memcmp(p+0xcecc,patch,9))return false;
    fpsResume=reinterpret_cast<ULONG_PTR>(p+0xced5);
    return writeMemory(p+0xcecc,enabled?patch:original,9);
}
bool installAdvancedDriver(HMODULE module,bool wide,bool render60,void(*logger)(const wchar_t*)) {
    auto p=reinterpret_cast<BYTE*>(module);
    if(!imageMatches(p,0x2c000,0x2c000)||memcmp(p+0x85cd,projectionPrefix,sizeof(projectionPrefix))||memcmp(p+0x3262,presentPrefix,sizeof(presentPrefix)))return false;
    auto projection=reinterpret_cast<DWORD*>(p+0x1ab28);auto frame=reinterpret_cast<DWORD*>(p+0x1a5bc);
    DWORD wideHook=reinterpret_cast<DWORD>(&projectionHook),frameHook=reinterpret_cast<DWORD>(&presentHook);
    DWORD expectedWide=reinterpret_cast<DWORD>(p+0x85cd),expectedFrame=reinterpret_cast<DWORD>(p+0x3262);
    if((*projection!=expectedWide&&*projection!=wideHook)||(*frame!=expectedFrame&&*frame!=frameHook))return false;
    originalPerspective=reinterpret_cast<Perspective>(expectedWide);originalPresent=reinterpret_cast<Present>(expectedFrame);
    widen=wide;pace=render60;trace=logger;
    DWORD before=*projection;
    if(wide&&*projection!=wideHook&&!writeMemory(projection,&wideHook,4))return false;
    if(render60&&*frame!=frameHook&&!writeMemory(frame,&frameHook,4)){if(*projection!=before)writeMemory(projection,&before,4);return false;}
    if(logger)logger(L"ADVANCED_DRIVER_READY projection=source_locked pacing=source_locked");
    return true;
}
#ifdef ADVANCED_DISPLAY_TEST
void configureAdvancedFixture(PerspectiveFn a,PresentFn b){originalPerspective=a;originalPresent=b;}
static void header(BYTE* p,DWORD size){memset(p,0,size);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=size;}
void initializeAdvancedEngineFixture(BYTE* p){header(p,0x10b000);memcpy(p+0xce4e,waitGuard,sizeof(waitGuard));memcpy(p+0xcf01,updateGuard,sizeof(updateGuard));memcpy(p+0x1d4b5,cameraStore,sizeof(cameraStore));*reinterpret_cast<float*>(p+0xbd654)=1000.0f;BYTE fps[]={0xd9,0x05,0,0,0,0,0xd8,0x75,0xd4};*reinterpret_cast<DWORD*>(fps+2)=reinterpret_cast<DWORD>(p+0xbd654);memcpy(p+0xcecc,fps,9);}
void initializeAdvancedDriverFixture(BYTE* p){header(p,0x2c000);memcpy(p+0x85cd,projectionPrefix,sizeof(projectionPrefix));memcpy(p+0x3262,presentPrefix,sizeof(presentPrefix));*reinterpret_cast<DWORD*>(p+0x1ab28)=reinterpret_cast<DWORD>(p+0x85cd);*reinterpret_cast<DWORD*>(p+0x1a5bc)=reinterpret_cast<DWORD>(p+0x3262);}
#endif
