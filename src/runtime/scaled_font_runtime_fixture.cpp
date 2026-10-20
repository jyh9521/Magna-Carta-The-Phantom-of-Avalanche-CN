// Owned structures/device only. No game/driver entry point, display-mode change,
// commercial dependency loading, save access, or proprietary file modification.
#include "scaled_font_runtime.h"
#include "scaled_font.h"
#include "native_font.h"
#include <ddraw.h>
#include <d3d.h>
#include <filesystem>
#include <vector>
#include <array>
#include <fstream>
#include <iterator>
#include <iostream>
#include <stdexcept>
#include <cstring>

namespace {
void check(bool v,const char* s){if(!v)throw std::runtime_error(s);}
void hr(HRESULT v,const char* s){if(FAILED(v)){std::cerr<<s<<" hr="<<std::hex<<v<<std::endl;throw std::runtime_error(s);}}
LONG WINAPI crash(EXCEPTION_POINTERS* e){std::cerr<<"SCALED_RUNTIME_EXCEPTION code="<<std::hex<<e->ExceptionRecord->ExceptionCode<<" address="<<e->ExceptionRecord->ExceptionAddress<<std::endl;return EXCEPTION_EXECUTE_HANDLER;}
void __cdecl unexpected(){std::cerr<<"UNEXPECTED_COMMERCIAL_IMPORT"<<std::endl;ExitProcess(99);}
void imports(BYTE* b){
    auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(b);auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(b+d->e_lfanew);
    auto dir=n->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    auto entry=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(b+dir.VirtualAddress);
    HMODULE crt=LoadLibraryW(L"msvcrt.dll");check(crt!=nullptr,"system CRT");
    for(;entry->Name;++entry){const char* dll=reinterpret_cast<const char*>(b+entry->Name);
        HMODULE library=nullptr;
        for(const char* allowed:{"KERNEL32.dll","USER32.dll","GDI32.dll","MSVCRT.dll","MSVCP60.dll"})
            if(!_stricmp(dll,allowed))library=LoadLibraryA(allowed);
        auto src=reinterpret_cast<IMAGE_THUNK_DATA32*>(b+entry->OriginalFirstThunk);
        auto dst=reinterpret_cast<IMAGE_THUNK_DATA32*>(b+entry->FirstThunk);
        for(;src->u1.AddressOfData;++src,++dst){const char* name=IMAGE_SNAP_BY_ORDINAL32(src->u1.Ordinal)?nullptr:
            reinterpret_cast<const char*>(b+src->u1.AddressOfData+2);
            FARPROC fn=library?GetProcAddress(library,name?name:MAKEINTRESOURCEA(IMAGE_ORDINAL32(src->u1.Ordinal))):nullptr;
            if(!_stricmp(dll,"Core.dll")&&name&&!strcmp(name,"?Cmalloc@@YAPAXI@Z"))fn=GetProcAddress(crt,"malloc");
            DWORD old;check(VirtualProtect(&dst->u1.Function,4,PAGE_READWRITE,&old)!=FALSE,"IAT protection");
            dst->u1.Function=reinterpret_cast<DWORD>(fn?fn:reinterpret_cast<FARPROC>(&unexpected));DWORD ignored;VirtualProtect(&dst->u1.Function,4,old,&ignored);
        }
    }
}
void jump(BYTE* at,void* target){at[0]=0xe9;*reinterpret_cast<int*>(at+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(target)-reinterpret_cast<ULONG_PTR>(at+5));}
struct Slot{unsigned id,used;float u,v;int x,y;void* owner;};
std::array<Slot,160> originalSlots{};unsigned allocated=0,uploaded=0,released=0;
std::array<BYTE,0x30> fontObject{};std::array<BYTE,108> font{};
unsigned short glyph=0;int logicalHeight=22;std::vector<unsigned> renderedLow;
bool mixed=false;
int __fastcall fallback(void* o,void*,int x,int y,const unsigned char*,int* a,unsigned* p,int pitch){
    // One owned ASCII pixel, with the original logical advance and clipping.
    const int pos=(y+2)*pitch+x+*a+2;if(pos>=0&&pos<logicalHeight*pitch)p[pos]=*reinterpret_cast<unsigned*>(static_cast<BYTE*>(o)+0x2c);*a+=7;return 1;
}
void __fastcall raster(void*,void*,const char*,unsigned* pixels,int width){
    beginScaledText(fontObject.data(),width);
    const unsigned char text[]={static_cast<unsigned char>(glyph>>8),static_cast<unsigned char>(glyph),0};
    const int xs[]={-1,1,-1,1,0},ys[]={0,0,2,2,1};
    for(unsigned pass=0;pass<5;++pass){
        *reinterpret_cast<unsigned*>(fontObject.data()+0x2c)=pass==4?0xffc0e0ff:0xff000000;
        int a=0;
        while(a<width){observeScaledGlyph(fontObject.data(),xs[pass],ys[pass],text,a,width,reinterpret_cast<ScaledOriginalGlyph>(&fallback));
            check(drawNativeCoverage(fontObject.data(),xs[pass],ys[pass],text,&a,pixels,width),"baseline glyph");
            if(mixed&&a<width){const unsigned char ascii[]={65,0};observeScaledGlyph(fontObject.data(),xs[pass],ys[pass],ascii,a,width,reinterpret_cast<ScaledOriginalGlyph>(&fallback));
                fallback(fontObject.data(),nullptr,xs[pass],ys[pass],ascii,&a,pixels,width);}
        }
    }
    renderedLow.assign(pixels,pixels+logicalHeight*width);
}
void* __fastcall allocate(void*,void*,int,int){check(allocated<originalSlots.size(),"fixture slots");auto& s=originalSlots[allocated++];s.used=1;return &s;}
void __cdecl upload(void* p,unsigned*){check(p>=originalSlots.data()&&p<originalSlots.data()+allocated,"original upload pointer");++uploaded;}
void __fastcall release(void*,void*,void* p){check(p>=originalSlots.data()&&p<originalSlots.data()+allocated,"original release pointer");auto s=static_cast<Slot*>(p);check(s->used==1,"one release");s->used=0;++released;}
void log(const wchar_t* s){std::wcout<<s<<std::endl;}
}
int wmain(int argc,wchar_t** argv){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);SetUnhandledExceptionFilter(crash);
    if(argc!=5&&argc!=6){std::cerr<<"mode absolute-driver absolute-ddraw absolute-cache [--presentation]"<<std::endl;return 2;}
    const bool presentation=argc==6&&!wcscmp(argv[5],L"--presentation");
    if(argc==6&&!presentation)return 2;
    SetEnvironmentVariableW(L"MC_SCALED_FONT_OUTPUT",presentation?L"2880x1800":L"3840x2160");
    const bool modified=!wcscmp(argv[1],L"modified"),rollback=!wcscmp(argv[1],L"rollback");
    if(!modified&&!rollback&&wcscmp(argv[1],L"baseline"))return 2;
    HMODULE image=nullptr;HWND window=nullptr;IDirectDraw7* draw=nullptr;IDirect3D7* d3d=nullptr;
    IDirectDrawSurface7* target=nullptr;IDirect3DDevice7* device=nullptr;BYTE* e=nullptr;
    int result=1;
    try{
        for(int i=2;i<5;++i)check(std::filesystem::path(argv[i]).is_absolute(),"absolute paths");
        SetEnvironmentVariableW(L"MC_SCALED_FONT_ASSETS",argv[4]);
        image=LoadLibraryExW(argv[2],nullptr,DONT_RESOLVE_DLL_REFERENCES);check(image!=nullptr,"map driver without entry");
        BYTE* b=reinterpret_cast<BYTE*>(image);auto dn=reinterpret_cast<IMAGE_NT_HEADERS32*>(b+reinterpret_cast<IMAGE_DOS_HEADER*>(b)->e_lfanew);
        check(dn->FileHeader.TimeDateStamp==0x3c2b7d28&&dn->OptionalHeader.SizeOfImage==0x2c000,"driver identity");imports(b);
        HMODULE dd=LoadLibraryW(argv[3]);check(dd!=nullptr,"ddraw");
        using Create=HRESULT(WINAPI*)(GUID*,void**,REFIID,IUnknown*);
        auto create=reinterpret_cast<Create>(GetProcAddress(dd,"DirectDrawCreateEx"));check(create!=nullptr,"ddraw export");
        window=CreateWindowExW(0,L"STATIC",L"OffscreenScaledFontFixture",WS_POPUP,0,0,64,64,nullptr,nullptr,nullptr,nullptr);check(window!=nullptr,"hidden window");
        hr(create(nullptr,reinterpret_cast<void**>(&draw),IID_IDirectDraw7,nullptr),"draw");
        hr(draw->SetCooperativeLevel(window,DDSCL_NORMAL),"normal cooperative level");
        hr(draw->QueryInterface(IID_IDirect3D7,reinterpret_cast<void**>(&d3d)),"d3d7");
        DDSURFACEDESC2 desc{};desc.dwSize=sizeof desc;desc.dwFlags=DDSD_CAPS|DDSD_WIDTH|DDSD_HEIGHT|DDSD_PIXELFORMAT;
        desc.dwWidth=presentation?800:3840;desc.dwHeight=presentation?600:2160;desc.ddsCaps.dwCaps=DDSCAPS_OFFSCREENPLAIN|DDSCAPS_3DDEVICE|DDSCAPS_VIDEOMEMORY;
        desc.ddpfPixelFormat.dwSize=sizeof(DDPIXELFORMAT);desc.ddpfPixelFormat.dwFlags=DDPF_RGB;desc.ddpfPixelFormat.dwRGBBitCount=32;
        desc.ddpfPixelFormat.dwRBitMask=0xff0000;desc.ddpfPixelFormat.dwGBitMask=0xff00;desc.ddpfPixelFormat.dwBBitMask=0xff;
        hr(draw->CreateSurface(&desc,&target,nullptr),"4k offscreen target");
        hr(d3d->CreateDevice(IID_IDirect3DHALDevice,target,&device),"owned device");
        // Initialize only the driver's embedded D3DX conversion utility. Its DLL
        // entry and commercial Core/Asura dependencies are never executed.
        reinterpret_cast<void(__cdecl*)()>(b+0xa8c6)();
        std::vector<BYTE> renderer(0x123000);*reinterpret_cast<BYTE**>(renderer.data())=b+0x1a5a8;
        *reinterpret_cast<IDirect3DDevice7**>(renderer.data()+0x2c)=device;
        e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(e!=nullptr,"owned PE");
        auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(e);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;
        auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(e+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;
        nt->FileHeader.TimeDateStamp=0x3ed73966;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
        *reinterpret_cast<void**>(e+0xf1b70)=renderer.data();
        for(auto c:std::vector<std::pair<unsigned,unsigned>>{{0x31d97,0x1ef9f},{0x3200e,0x27d21},{0x32056,0x27eb7},{0x321b3,0x27d21},{0x321fb,0x27eb7},{0x3235e,0x27e4d}}){e[c.first]=0xe8;*reinterpret_cast<int*>(e+c.first+1)=c.second-c.first-5;}
        jump(e+0x1ef9f,reinterpret_cast<void*>(&raster));jump(e+0x27d21,reinterpret_cast<void*>(&allocate));
        jump(e+0x27eb7,reinterpret_cast<void*>(&upload));jump(e+0x27e4d,reinterpret_cast<void*>(&release));
        std::vector<BYTE> before(e,e+0x10b000);configureScaledRuntimeFixture(e);
        if(modified||rollback){
            e[0x321fb]=0x90;check(!installScaledFontRuntime(reinterpret_cast<HMODULE>(e),log),"foreign CALL rejected");
            e[0x321fb]=0xe8;check(!memcmp(e,before.data(),before.size()),"rejection changed no bytes");
            check(installScaledFontRuntime(reinterpret_cast<HMODULE>(e),log),"install source-locked call bridge");
            e[0x321fb]=0x90;std::vector<BYTE> foreign(e,e+0x10b000);
            check(!removeScaledFontRuntime()&&!memcmp(e,foreign.data(),foreign.size()),"foreign rollback preserved");
            check(!installScaledFontRuntime(reinterpret_cast<HMODULE>(e),log),"foreign reentry rejected");
            e[0x321fb]=0xe8;check(installScaledFontRuntime(reinterpret_cast<HMODULE>(e),log),"idempotent install");
            if(rollback){check(removeScaledFontRuntime(),"rollback");check(!memcmp(e,before.data(),before.size()),"instruction rollback exact");}
        }
        unsigned textures=0;
        for(int h:{14,22})for(int padded:{0,1})for(int width:{1,255,256,257,512,513}){
            const int canvasHeight=padded?(h==14?16:32):h;
            mixed=width==513;
            logicalHeight=h;*reinterpret_cast<void**>(fontObject.data()+8)=font.data();
            *reinterpret_cast<void**>(fontObject.data()+4)=font.data();
            *reinterpret_cast<unsigned short*>(font.data()+0x58)=static_cast<unsigned short>(h);
            *reinterpret_cast<int*>(fontObject.data()+0x1c)=canvasHeight;
            ScaledGlyphCache high;std::string error;
            auto path=std::filesystem::path(argv[4])/(L"candidate-"+std::to_wstring(h)+L".sgc");
            std::ifstream highFile(path,std::ios::binary);std::vector<unsigned char> highBytes((std::istreambuf_iterator<char>(highFile)),{});
            check(high.loadBytes(highBytes,error),"fixture high cache");glyph=high.ids()[500];
            std::vector<unsigned> low(size_t(width)*canvasHeight,0),expected(size_t(width)*canvasHeight*16,0);
            scaledRasterFixture(nullptr,nullptr,"owned",low.data(),width);
            int xs[]={-1,1,-1,1,0},ys[]={0,0,2,2,1};
            for(unsigned pass=0;pass<5;++pass){int a=0;unsigned color=pass==4?0xffc0e0ff:0xff000000;
                while(a<width){check(high.draw(glyph,xs[pass],ys[pass],a,color,expected.data(),size_t(width)*h*16,width*4),"reference C");
                    if(mixed&&a<width){int pos=(ys[pass]+2)*width+xs[pass]+a+2;
                        if(pos>=0&&pos<h*width)for(int yy=0;yy<4;++yy)for(int xx=0;xx<4;++xx)
                            expected[(size_t(pos/width)*4+yy)*width*4+(pos%width)*4+xx]=color;
                        a+=7;}
                }
            }
            allocated=uploaded=released=0;
            std::vector<void*> words;
            for(int x=0;x<width;x+=256){int w=std::min(256,width-x);void* slot=scaledSlotFixture(nullptr,nullptr,w,canvasHeight);words.push_back(slot);
                unsigned descriptor[]={0x1908,unsigned(w),unsigned(h),0,0};scaledUploadFixture(slot,descriptor);
                if(modified){check(slot!=&originalSlots[allocated-1],"expected private high slot");auto s=static_cast<Slot*>(slot);auto owner=static_cast<unsigned*>(s->owner);
                    auto surface=*reinterpret_cast<IDirectDrawSurface7**>(renderer.data()+0x100ea0+4*owner[0]);check(surface!=nullptr,"native texture surface");
                    DDSURFACEDESC2 td{};td.dwSize=sizeof td;hr(surface->GetSurfaceDesc(&td),"texture description");
                    check(td.dwWidth==owner[5]*4&&td.dwHeight==owner[6]*4&&td.ddpfPixelFormat.dwRGBBitCount==32,"physical allocation");
                    hr(surface->Lock(nullptr,&td,DDLOCK_WAIT|DDLOCK_READONLY,nullptr),"texture readback");
                    bool exact=true;for(unsigned yy=0;yy<td.dwHeight;++yy)for(unsigned xx=0;xx<td.dwWidth;++xx){
                        unsigned wanted=yy<unsigned(canvasHeight*4)&&xx<unsigned(w*4)?expected[size_t(yy)*width*4+x*4+xx]:0;
                        if(*reinterpret_cast<unsigned*>(static_cast<BYTE*>(td.lpSurface)+yy*td.lPitch+xx*4)!=wanted)exact=false;
                    }
                    hr(surface->Unlock(nullptr),"texture unlock");check(exact,"GPU pixels match C including tail/padding");
                    for(int left:{0,w/2}){double u=double(left)/owner[5],v=double(h)/owner[6];
                        check(u==double(left*4)/td.dwWidth&&v==double(h*4)/td.dwHeight,"native crop UV invariance");}
                    using Bind=void(__thiscall*)(void*,unsigned,unsigned);
                    reinterpret_cast<Bind>(*reinterpret_cast<DWORD*>(b+0x1a5a8+0x2c))(renderer.data(),0xde1,owner[0]);++textures;
                }else check(slot==&originalSlots[allocated-1],"baseline uses original slot");
            }
            check(uploaded==allocated,"original upload preserved");
            for(void* s:words)scaledReleaseFixture(nullptr,nullptr,s);
            check(released==allocated&&scaledRuntimeOwnedCount()==0,"all native/private slots released");
            if(modified){IDirectDrawSurface7* remaining=nullptr;hr(device->GetTexture(0,&remaining),"binding after delete");check(remaining==nullptr,"no retained device binding");}
        }
        if(modified){
            mixed=false;
            // Exhaust the private slot budget, then force failure in tile two.
            // The first tile must demote too, rather than mixing C and baseline.
            logicalHeight=14;*reinterpret_cast<unsigned short*>(font.data()+0x58)=14;
            *reinterpret_cast<int*>(fontObject.data()+0x1c)=14;allocated=uploaded=released=0;
            std::vector<void*> retained;
            std::vector<unsigned> line(513*14,0);
            for(unsigned i=0;i<127;++i){std::fill(line.begin(),line.end(),0);scaledRasterFixture(nullptr,nullptr,"owned",line.data(),256);
                auto slot=scaledSlotFixture(nullptr,nullptr,256,14);check(slot!=&originalSlots[allocated-1],"budget setup");
                unsigned d[]={0x1908,256,14,0,0};scaledUploadFixture(slot,d);retained.push_back(slot);}
            scaledRasterFixture(nullptr,nullptr,"owned",line.data(),513);
            for(int w:{256,256,1}){auto slot=scaledSlotFixture(nullptr,nullptr,w,14);retained.push_back(slot);unsigned d[]={0x1908,unsigned(w),14,0,0};scaledUploadFixture(slot,d);}
            check(static_cast<Slot*>(retained[127])->owner==originalSlots[127].owner,"failed line demoted");
            for(auto s:retained)scaledReleaseFixture(nullptr,nullptr,s);
            check(scaledRuntimeOwnedCount()==0&&released==allocated,"budget fallback release");
            // A 1080p render target must use original slots even with C enabled.
            desc.dwWidth=1920;desc.dwHeight=1080;IDirectDrawSurface7* lowTarget=nullptr;
            SetEnvironmentVariableW(L"MC_SCALED_FONT_OUTPUT",L"1920x1080");
            hr(draw->CreateSurface(&desc,&lowTarget,nullptr),"1080p target");hr(device->SetRenderTarget(lowTarget,0),"1080p selection");
            allocated=uploaded=released=0;scaledRasterFixture(nullptr,nullptr,"owned",line.data(),256);
            auto slot=scaledSlotFixture(nullptr,nullptr,256,14);check(slot==&originalSlots[0],"1080p baseline preserved");
            unsigned d[]={0x1908,256,14,0,0};scaledUploadFixture(slot,d);scaledReleaseFixture(nullptr,nullptr,slot);
            hr(device->SetRenderTarget(target,0),"restore owned target");lowTarget->Release();
        }
        check(removeScaledFontRuntime(),"remove final bridge");check(!memcmp(e,before.data(),before.size()),"all call instructions restored");
        std::cout<<"SCALED_RUNTIME "<<(modified?"MODIFIED":rollback?"ROLLBACK":"BASELINE")<<" PASS cases=24 hd_textures="<<textures<<" upload=original UV=exact release=exact instructions=restored"
                 <<(modified?" low_resolution=baseline budget_fallback=whole_line":" low_resolution=not_run budget_fallback=not_run")
                 <<" actual_d3d7=true driver_entry_executed=false game_started=false"<<std::endl;
        reinterpret_cast<void(__cdecl*)()>(b+0xa99f)();result=0;
    }catch(const std::exception& error){std::cerr<<"SCALED_RUNTIME_FAIL "<<error.what()<<std::endl;}
    if(device)device->SetTexture(0,nullptr);
    if(device)device->Release();if(target)target->Release();if(d3d)d3d->Release();if(draw)draw->Release();
    if(window)DestroyWindow(window);if(e)VirtualFree(e,0,MEM_RELEASE);if(image)FreeLibrary(image);return result;
}
