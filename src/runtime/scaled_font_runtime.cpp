#include "scaled_font_runtime.h"
#include "scaled_font.h"
#include "scaled_font_output.h"
#include "native_font.h"
#include <d3d.h>
#include <bcrypt.h>
#include <filesystem>
#include <fstream>
#include <array>
#include <memory>
#include <mutex>
#include <vector>
#include <algorithm>
#include <cstring>
#include <cstdio>
#ifdef SCALED_FONT_DATA_HEADER
#include SCALED_FONT_DATA_HEADER
#else
static const char* scaledCacheHashes[]={"",""};
#endif

namespace {
constexpr unsigned scale=4;
constexpr size_t textureBudget=64*1024*1024;
BYTE* engine=nullptr;void(*trace)(const wchar_t*)=nullptr;
bool ready=false;
ScaledGlyphCache caches[2];
using Raster=void(__thiscall*)(void*,const char*,unsigned*,int);
using Allocate=void*(__thiscall*)(void*,int,int);
using Upload=void(__cdecl*)(void*,unsigned*);
using Release=void(__thiscall*)(void*,void*);
Raster raster=nullptr;Allocate allocateSlot=nullptr;Upload upload=nullptr;Release releaseSlot=nullptr;
struct Capture {
    bool collecting=false,valid=false,mapped=false;
    int width=0,height=0,cursor=0;
    std::vector<unsigned> pixels;
    std::vector<void*> privateSlots;
};
thread_local Capture capture;
// A private slot has exactly the native 28-byte ABI. Native word geometry and
// pool slots are never resized. Only text-cache words receive private pointers.
struct Slot {unsigned id,used;float u,v;int x,y;void* owner;};
static_assert(sizeof(Slot)==28,"Win32 slot ABI");
struct Owned {
    Slot slot{};std::array<unsigned,14> owner{};
    void* original=nullptr;BYTE* renderer=nullptr;IDirect3DDevice7* device=nullptr;
    IDirectDrawSurface7* surface=nullptr;unsigned texture=~0u;size_t bytes=0;
};
std::recursive_mutex stateMutex;
std::vector<std::unique_ptr<Owned>> owned;
size_t ownedBytes=0;unsigned notices=0;
template<class T>T field(void* p,size_t o){return *reinterpret_cast<T*>(static_cast<BYTE*>(p)+o);}
template<class T>T method(BYTE* p,size_t o){return reinterpret_cast<T>(field<ULONG_PTR>(field<void*>(p,0),o));}
using Bind=void(__thiscall*)(void*,unsigned,unsigned);
using Gen=void(__thiscall*)(void*,int,unsigned*);
using Image=void(__thiscall*)(void*,unsigned,int,unsigned,unsigned,unsigned,int,unsigned,unsigned,const void*);
using Parameter=void(__thiscall*)(void*,unsigned,unsigned,unsigned);
using Delete=void(__thiscall*)(void*,int,const unsigned*);
bool imageHeader(BYTE* b,DWORD size,DWORD stamp){
    if(!b)return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(b);
    if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096)return false;
    auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(b+d->e_lfanew);
    return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&
           n->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&n->OptionalHeader.SizeOfImage==size&&n->FileHeader.TimeDateStamp==stamp;
}
BYTE* renderer(){
    if(!engine)return nullptr;auto p=field<BYTE*>(engine,0xf1b70);
    auto driver=reinterpret_cast<BYTE*>(GetModuleHandleW(L"AsrD3DDrv.dll"));
    if(!imageHeader(driver,0x2c000,0x3c2b7d28)||!p||field<BYTE*>(p,0)!=driver+0x1a5a8)return nullptr;
    const size_t slots[]={0x1a0,0x4cc,0x4d8,0x4e4};const size_t rvas[]={0x51ca,0x538b,0x4de5,0x9bd8};
    for(unsigned i=0;i<4;++i)if(field<BYTE*>(driver,0x1a5a8+slots[i])!=driver+rvas[i])return nullptr;
    return p;
}
bool highTarget(BYTE* r){
    if(!field<IDirect3DDevice7*>(r,0x2c)){
        static LONG reported=0;if(trace&&InterlockedCompareExchange(&reported,1,0)==0)trace(L"SCALED_FONT_SKIP stage=device_not_ready");return false;
    }
    wchar_t text[40]{};ScaledFontOutput output;
    DWORD n=GetEnvironmentVariableW(L"MC_SCALED_FONT_OUTPUT",text,40);
    bool valid=n&&n<40&&parseScaledFontOutput(text,output);
    bool enabled=valid&&highScaledFontOutput(output);
    thread_local unsigned previousW=~0u,previousH=~0u;
    if(trace&&(output.width!=previousW||output.height!=previousH)){
        previousW=output.width;previousH=output.height;
        unsigned w=0,h=0;auto device=field<IDirect3DDevice7*>(r,0x2c);IDirectDrawSurface7* target=nullptr;
        if(device&&SUCCEEDED(device->GetRenderTarget(&target))&&target){DDSURFACEDESC2 d{};d.dwSize=sizeof d;
            if(SUCCEEDED(target->GetSurfaceDesc(&d))){w=d.dwWidth;h=d.dwHeight;}target->Release();}
        wchar_t s[240];swprintf_s(s,L"SCALED_FONT_GATE output=%ux%u logical=%ux%u enabled=%s source=launcher_snapshot reason=%s",
            output.width,output.height,w,h,enabled?L"true":L"false",!valid?L"missing_or_invalid_snapshot":enabled?L"high_output":L"low_output");trace(s);
    }
    return enabled;
}
bool loadCache(const std::filesystem::path& path,const char* expected,ScaledGlyphCache& cache){
    std::ifstream f(path,std::ios::binary|std::ios::ate);if(!f)return false;
    auto n=f.tellg();if(n<20||n>32*1024*1024)return false;
    std::vector<unsigned char> b(static_cast<size_t>(n));f.seekg(0);
    if(!f.read(reinterpret_cast<char*>(b.data()),n))return false;
    BCRYPT_ALG_HANDLE alg=nullptr;unsigned char hash[32]{};
    if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)return false;
    BCRYPT_HASH_HANDLE handle=nullptr;
    auto status=BCryptCreateHash(alg,&handle,nullptr,0,nullptr,0,0);
    if(status>=0)status=BCryptHashData(handle,b.data(),static_cast<ULONG>(b.size()),0);
    if(status>=0)status=BCryptFinishHash(handle,hash,32,0);
    if(handle)BCryptDestroyHash(handle);
    BCryptCloseAlgorithmProvider(alg,0);if(status<0)return false;
    char hex[65]{};for(unsigned i=0;i<32;++i)sprintf_s(hex+i*2,3,"%02x",hash[i]);
    std::string error;return !strcmp(expected,hex)&&cache.loadBytes(b,error)&&cache.scale()==scale;
}
bool loadCaches(){
    wchar_t path[32768]{};DWORD n=GetEnvironmentVariableW(L"MC_SCALED_FONT_ASSETS",path,32768);
    if(!n||n>=32768)return false;
    auto p=std::filesystem::path(path);if(!p.is_absolute())return false;
    return loadCache(p/L"candidate-14.sgc",scaledCacheHashes[0],caches[0])&&caches[0].height()==14&&
           loadCache(p/L"candidate-22.sgc",scaledCacheHashes[1],caches[1])&&caches[1].height()==22&&caches[0].ids()==caches[1].ids();
}
unsigned powerOfTwo(unsigned n){unsigned v=1;while(v<n)v*=2;return v;}
void eraseTexture(Owned& o){
    if(o.texture==~0u)return;
    // Do not erase a recycled ID or touch a retired device after driver reset.
    if(renderer()==o.renderer&&field<IDirect3DDevice7*>(o.renderer,0x2c)==o.device&&
       field<IDirectDrawSurface7*>(o.renderer,0x100ea0+4*o.texture)==o.surface){
        for(unsigned stage=0;stage<8;++stage){IDirectDrawSurface7* bound=nullptr;
            if(SUCCEEDED(o.device->GetTexture(stage,&bound))&&bound){
                if(bound==o.surface)o.device->SetTexture(stage,nullptr);bound->Release();
            }
        }
        method<Delete>(o.renderer,0x104)(o.renderer,1,&o.texture);
    }
    o.texture=~0u;
}
bool makeTexture(Owned& o,int w,int h,int sourceX){
    BYTE* r=renderer();if(!r||!highTarget(r))return false;
    const unsigned tw=powerOfTwo(w),th=powerOfTwo(h),pw=tw*scale,ph=th*scale;
    if(pw>1024||ph>1024)return false;
    const size_t bytes=size_t(pw)*ph*4;
    if(owned.size()>=128||bytes>textureBudget-ownedBytes)return false;
    auto device=field<IDirect3DDevice7*>(r,0x2c);D3DDEVICEDESC7 caps{};
    if(FAILED(device->GetCaps(&caps))||pw>caps.dwMaxTextureWidth||ph>caps.dwMaxTextureHeight)return false;
    unsigned free=0,id=~0u;
    for(unsigned i=0;i<4096;++i)if(!field<unsigned>(r,0x104ea0+4*i)){++free;if(id==~0u)id=i;}
    if(free<32||id==~0u)return false;
    std::vector<unsigned> tile(size_t(pw)*ph,0);
    for(int y=0;y<h*int(scale);++y)
        std::copy_n(capture.pixels.data()+size_t(y)*capture.width*scale+sourceX*scale,w*scale,tile.data()+size_t(y)*pw);
    const unsigned before=field<unsigned>(r,0x100e9c);
    unsigned actual=~0u;method<Gen>(r,0x1a0)(r,1,&actual);
    if(actual>=4096||field<IDirectDrawSurface7*>(r,0x100ea0+4*actual))return false;
    id=actual;
    o.renderer=r;o.device=device;o.texture=id;
    method<Bind>(r,0x2c)(r,0xde1,id);
    // BGRA source avoids the legacy driver's asymmetric RGBA conversion path.
    method<Image>(r,0x4cc)(r,0xde1,0,0x8058,pw,ph,0,0x80e1,0x1401,tile.data());
    o.surface=field<IDirectDrawSurface7*>(r,0x100ea0+4*id);
    DDSURFACEDESC2 desc{};desc.dwSize=sizeof desc;
    bool ok=o.surface&&SUCCEEDED(o.surface->GetSurfaceDesc(&desc))&&desc.dwWidth==pw&&desc.dwHeight==ph;
    if(ok){
        method<Parameter>(r,0x4d8)(r,0xde1,0x2801,0x2601);
        method<Parameter>(r,0x4d8)(r,0xde1,0x2800,0x2601);
        method<Parameter>(r,0x4d8)(r,0xde1,0x2802,0x2900);
        method<Parameter>(r,0x4d8)(r,0xde1,0x2803,0x2900);
        o.bytes=bytes;o.owner[0]=id;o.owner[1]=0x8058;
        o.owner[0x14/4]=tw;o.owner[0x18/4]=th;
        o.slot.used=1;o.slot.owner=o.owner.data();
        if(trace&&notices++<8){wchar_t s[160];swprintf_s(s,L"SCALED_FONT_TEXTURE logical=%dx%d physical=%ux%u layout=unchanged",w,h,pw,ph);trace(s);}
    }else eraseTexture(o);
    if(before<4096)method<Bind>(r,0x2c)(r,0xde1,before);
    return ok;
}
void demoteLine(){
    std::lock_guard<std::recursive_mutex> guard(stateMutex);
    for(void* s:capture.privateSlots)for(auto& p:owned)if(&p->slot==s){
        eraseTexture(*p);ownedBytes-=p->bytes;p->bytes=0;p->slot=*static_cast<Slot*>(p->original);
    }
    capture.valid=false;
}
void __fastcall rasterHook(void* object,void*,const char* text,unsigned* pixels,int pitch){
    capture=Capture{};
    BYTE* r=ready?renderer():nullptr;
    static LONG rendererReported=0;
    if(ready&&!r&&trace&&InterlockedCompareExchange(&rendererReported,1,0)==0)trace(L"SCALED_FONT_SKIP stage=renderer_contract");
    capture.collecting=r&&highTarget(r);
    raster(object,text,pixels,pitch);
    capture.collecting=false;
}
void* __fastcall allocateHook(void* object,void*,int w,int h){
    void* original=allocateSlot(object,w,h);
    int x=capture.cursor;capture.cursor+=w;
    if(!original||!capture.valid||!capture.mapped||w<1||w>256||h!=capture.height||x<0||x>capture.width-w)return original;
    try{
        std::lock_guard<std::recursive_mutex> guard(stateMutex);
        auto next=std::make_unique<Owned>();next->original=original;
        // Reserve before allocating a GPU resource so vector growth cannot leak it.
        owned.reserve(128);
        capture.privateSlots.reserve(32);
        if(!makeTexture(*next,w,h,x)){
            static LONG reported=0;if(trace&&InterlockedCompareExchange(&reported,1,0)==0)trace(L"SCALED_FONT_SKIP stage=texture_allocation caps_or_budget=true");
            // No mixed-quality seams within one line if a later tile exceeds
            // the GPU/budget limit. Earlier private pointers become native views.
            demoteLine();return original;
        }
        auto slot=&next->slot;capture.privateSlots.push_back(slot);ownedBytes+=next->bytes;owned.push_back(std::move(next));return slot;
    }catch(...){demoteLine();return original;}
}
void __cdecl uploadHook(void* slot,unsigned* descriptor){
    std::lock_guard<std::recursive_mutex> guard(stateMutex);
    auto it=std::find_if(owned.begin(),owned.end(),[&](const auto& p){return &p->slot==slot;});
    // Always populate the retained original atlas too. Image/font pools stay intact.
    upload(it==owned.end()?slot:(*it)->original,descriptor);
    if(capture.cursor>=capture.width)capture=Capture{};
}
void __fastcall releaseHook(void* object,void*,void* slot){
    std::lock_guard<std::recursive_mutex> guard(stateMutex);
    auto it=std::find_if(owned.begin(),owned.end(),[&](const auto& p){return &p->slot==slot;});
    if(it==owned.end()){releaseSlot(object,slot);return;}
    auto& p=**it;eraseTexture(p);void* original=p.original;ownedBytes-=p.bytes;
    releaseSlot(object,original);owned.erase(it);
}
struct Call {size_t rva,target;void* callback;BYTE original[5]{};bool patched=false;};
Call calls[]={
    {0x31d97,0x1ef9f,reinterpret_cast<void*>(&rasterHook)},
    {0x3200e,0x27d21,reinterpret_cast<void*>(&allocateHook)},
    {0x32056,0x27eb7,reinterpret_cast<void*>(&uploadHook)},
    {0x321b3,0x27d21,reinterpret_cast<void*>(&allocateHook)},
    {0x321fb,0x27eb7,reinterpret_cast<void*>(&uploadHook)},
    {0x3235e,0x27e4d,reinterpret_cast<void*>(&releaseHook)}
};
bool matches(const Call& c,bool patched){
    auto p=engine+c.rva;
    auto target=patched?reinterpret_cast<BYTE*>(c.callback):engine+c.target;
    return p[0]==0xe8&&p+5+*reinterpret_cast<int*>(p+1)==target;
}
bool write(BYTE* p,const BYTE* b){DWORD old;if(!VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old))return false;
    memcpy(p,b,5);bool ok=FlushInstructionCache(GetCurrentProcess(),p,5)!=FALSE;
    DWORD ignored;return VirtualProtect(p,5,old,&ignored)!=FALSE&&ok;
}
void configure(BYTE* b){engine=b;raster=reinterpret_cast<Raster>(b+0x1ef9f);
    allocateSlot=reinterpret_cast<Allocate>(b+0x27d21);upload=reinterpret_cast<Upload>(b+0x27eb7);releaseSlot=reinterpret_cast<Release>(b+0x27e4d);}
}

void beginScaledText(void* object,int pitch){
    if(!capture.collecting)return;
    try{
        int h=field<int>(object,0x1c);
        if(pitch<1||pitch>8192||h<1||h>256||size_t(h)*pitch*scale*scale*4>16*1024*1024){
            static LONG reported=0;if(trace&&InterlockedCompareExchange(&reported,1,0)==0){wchar_t s[120];swprintf_s(s,L"SCALED_FONT_SKIP stage=canvas_contract width=%d height=%d",pitch,h);trace(s);}
            capture.valid=false;return;}
        capture.width=pitch;capture.height=h;capture.cursor=0;
        capture.pixels.assign(size_t(h)*pitch*scale*scale,0);capture.valid=true;
    }catch(...){capture.valid=false;}
}
void observeScaledGlyph(void* object,int x,int y,const unsigned char* text,int advance,int pitch,ScaledOriginalGlyph original){
    if(!capture.collecting||!capture.valid||pitch!=capture.width)return;
    try{
        auto font=field<BYTE*>(object,text[0]<0xb0?4:text[0]<0xca?0:8);
        unsigned h=field<unsigned short>(font,0x58),color=field<unsigned>(object,0x2c);
        if(h<1||h>unsigned(capture.height)){capture.valid=false;return;}
        if(text[0]>=0xca&&text[1]&&!font[0x2a]&&(h==14||h==22)){
            auto& c=caches[h==14?0:1];int a=advance;
            if(c.draw(static_cast<unsigned short>(unsigned(text[0])<<8|text[1]),x,y,a,color,
                      capture.pixels.data(),size_t(h)*scale*pitch*scale,pitch*scale)){capture.mapped=true;return;}
        }
        // Preserve original Latin/Korean/unknown glyph shape and advance. Rendering
        // a white mask on an object copy avoids altering the native color/state.
        std::array<BYTE,0x30> copy{};memcpy(copy.data(),object,copy.size());
        *reinterpret_cast<unsigned*>(copy.data()+0x2c)=0xffffffff;
        std::vector<unsigned> mask(size_t(h)*pitch,0);int a=advance;
        original(copy.data(),x,y,text,&a,mask.data(),pitch);
        for(unsigned row=0;row<h;++row)for(int col=0;col<pitch;++col)if(mask[row*pitch+col])
            for(unsigned yy=0;yy<scale;++yy)for(unsigned xx=0;xx<scale;++xx)
                capture.pixels[(size_t(row)*scale+yy)*pitch*scale+col*scale+xx]=color;
    }catch(...){capture.valid=false;}
}
bool installScaledFontRuntime(HMODULE module,void(*logger)(const wchar_t*)){
    BYTE* b=reinterpret_cast<BYTE*>(module);
    if(ready){if(engine!=b)return false;for(auto& c:calls)if(!matches(c,true))return false;return true;}
    if(!imageHeader(b,0x10b000,0x3ed73966))return false;
    for(auto& c:calls){BYTE* p=b+c.rva;
        if(p[0]!=0xe8||p+5+*reinterpret_cast<int*>(p+1)!=b+c.target)return false;
    }
    if(!loadCaches()){for(auto& c:caches)c=ScaledGlyphCache{};return false;}
    configure(b);trace=logger;
    for(auto& c:calls){BYTE patch[5]={0xe8};memcpy(c.original,b+c.rva,5);
        *reinterpret_cast<int*>(patch+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(c.callback)-reinterpret_cast<ULONG_PTR>(b+c.rva+5));
        c.patched=true;if(!write(b+c.rva,patch)){removeScaledFontRuntime();return false;}
    }
    ready=true;if(trace)trace(L"SCALED_FONT_READY variant=C scale=4 policy=launcher_output_snapshot original_pool=retained");return true;
}
bool removeScaledFontRuntime(){
    std::lock_guard<std::recursive_mutex> guard(stateMutex);
    if(!owned.empty())return false; // Never retire code while native words retain private slots.
    for(auto& c:calls)if(c.patched&&!matches(c,true)&&!matches(c,false))return false;
    bool ok=true;
    for(auto& c:calls)if(c.patched){if(write(engine+c.rva,c.original))c.patched=false;else ok=false;}
    if(ok){ready=false;engine=nullptr;capture=Capture{};for(auto& c:caches)c=ScaledGlyphCache{};}
    return ok;
}
#ifdef SCALED_FONT_RUNTIME_TEST
void configureScaledRuntimeFixture(BYTE* e){configure(e);ready=false;}
void __fastcall scaledRasterFixture(void* o,void*,const char* t,unsigned* p,int w){rasterHook(o,nullptr,t,p,w);}
void* __fastcall scaledSlotFixture(void* o,void*,int w,int h){return allocateHook(o,nullptr,w,h);}
void __cdecl scaledUploadFixture(void* s,unsigned* d){uploadHook(s,d);}
void __fastcall scaledReleaseFixture(void* o,void*,void* s){releaseHook(o,nullptr,s);}
size_t scaledRuntimeOwnedCount(){std::lock_guard<std::recursive_mutex> g(stateMutex);return owned.size();}
#endif
