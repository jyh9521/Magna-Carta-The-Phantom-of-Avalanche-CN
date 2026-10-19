// Source-locked diagnostic probe. A retained device reference is NOT proof of a game crash.
#include "current_texture_lifetime.h"
#include <windows.h>
#include <ddraw.h>
#include <d3d.h>
#include <vector>
#include <iostream>
#include <filesystem>
#include <stdexcept>
#include <cstring>
using DeleteFn=void(__thiscall*)(void*,int,const DWORD*);
void check(bool v,const char* s){if(!v)throw std::runtime_error(s);}
void hr(HRESULT v,const char* s){if(FAILED(v)){std::cerr<<s<<" hr="<<std::hex<<v<<std::endl;throw std::runtime_error(s);}}
LONG WINAPI crash(EXCEPTION_POINTERS* e){std::cerr<<"NATIVE_TEXTURE_EXCEPTION code=0x"<<std::hex<<e->ExceptionRecord->ExceptionCode<<" address="<<e->ExceptionRecord->ExceptionAddress<<std::endl;return EXCEPTION_EXECUTE_HANDLER;}
void log(const wchar_t* s){std::wcout<<s<<std::endl;}
int wmain(int argc,wchar_t** argv){
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);SetUnhandledExceptionFilter(crash);
 HMODULE image=nullptr,dd=nullptr;HWND window=nullptr;IDirectDraw7* draw=nullptr;IDirect3D7* d3d=nullptr;IDirectDrawSurface7* target=nullptr;IDirect3DDevice7* device=nullptr;bool hooked=false;int result=1;
 try{
  check(argc==3||argc==4,"usage: probe absolute-driver absolute-ddraw [--baseline|--rollback]");bool baseline=argc==4&&!wcscmp(argv[3],L"--baseline");bool rollback=argc==4&&!wcscmp(argv[3],L"--rollback");check(argc==3||baseline||rollback,"unknown option");check(std::filesystem::path(argv[1]).is_absolute()&&std::filesystem::path(argv[2]).is_absolute(),"absolute paths required");
  image=LoadLibraryExW(argv[1],nullptr,DONT_RESOLVE_DLL_REFERENCES);check(image!=nullptr,"map driver");auto b=reinterpret_cast<BYTE*>(image);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(b);check(dos->e_magic==IMAGE_DOS_SIGNATURE,"DOS");auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(b+dos->e_lfanew);check(nt->FileHeader.TimeDateStamp==0x3c2b7d28&&nt->OptionalHeader.SizeOfImage==0x2c000,"unsupported driver");
  const BYTE code[]={0x55,0x8b,0xec,0x83,0xec,8,0x89,0x4d,0xf8,0x33,0xc0,0x85,0xc0,0x74,5};check(!memcmp(b+0x52c8,code,sizeof code),"delete code drift");DWORD original=*reinterpret_cast<DWORD*>(b+0x1a6ac);
  dd=LoadLibraryW(argv[2]);check(dd!=nullptr,"load ddraw");using Create=HRESULT(WINAPI*)(GUID*,void**,REFIID,IUnknown*);auto create=reinterpret_cast<Create>(GetProcAddress(dd,"DirectDrawCreateEx"));check(create!=nullptr,"ddraw export");
  window=CreateWindowExW(0,L"STATIC",L"OffscreenNativeTextureProbe",WS_POPUP,0,0,64,64,nullptr,nullptr,nullptr,nullptr);check(window!=nullptr,"hidden window");
  hr(create(nullptr,reinterpret_cast<void**>(&draw),IID_IDirectDraw7,nullptr),"draw");hr(draw->SetCooperativeLevel(window,DDSCL_NORMAL),"cooperative");hr(draw->QueryInterface(IID_IDirect3D7,reinterpret_cast<void**>(&d3d)),"d3d7");
  DDSURFACEDESC2 desc{};desc.dwSize=sizeof desc;desc.dwFlags=DDSD_CAPS|DDSD_WIDTH|DDSD_HEIGHT|DDSD_PIXELFORMAT;desc.dwWidth=desc.dwHeight=64;desc.ddsCaps.dwCaps=DDSCAPS_OFFSCREENPLAIN|DDSCAPS_3DDEVICE|DDSCAPS_VIDEOMEMORY;desc.ddpfPixelFormat.dwSize=sizeof(DDPIXELFORMAT);desc.ddpfPixelFormat.dwFlags=DDPF_RGB;desc.ddpfPixelFormat.dwRGBBitCount=32;desc.ddpfPixelFormat.dwRBitMask=0xff0000;desc.ddpfPixelFormat.dwGBitMask=0xff00;desc.ddpfPixelFormat.dwBBitMask=0xff;
  hr(draw->CreateSurface(&desc,&target,nullptr),"target");hr(d3d->CreateDevice(IID_IDirect3DHALDevice,target,&device),"device");
  if(!baseline){check(installCurrentTextureLifetime(image,nullptr),"install hook");hooked=true;}
  if(rollback){check(removeCurrentTextureLifetime(image),"rollback");hooked=false;check(*reinterpret_cast<DWORD*>(b+0x1a6ac)==original,"rollback slot mismatch");}
  std::vector<BYTE> object(0x123000);*reinterpret_cast<IDirect3DDevice7**>(object.data()+0x2c)=device;DWORD id=301;unsigned residual=0;
  for(unsigned cycle=0;cycle<200u;++cycle){
   DDSURFACEDESC2 td{};td.dwSize=sizeof td;td.dwFlags=DDSD_CAPS|DDSD_WIDTH|DDSD_HEIGHT|DDSD_PIXELFORMAT;td.dwWidth=td.dwHeight=8;td.ddsCaps.dwCaps=DDSCAPS_TEXTURE;td.ddsCaps.dwCaps2=DDSCAPS2_TEXTUREMANAGE;td.ddpfPixelFormat.dwSize=sizeof(DDPIXELFORMAT);td.ddpfPixelFormat.dwFlags=DDPF_RGB|DDPF_ALPHAPIXELS;td.ddpfPixelFormat.dwRGBBitCount=16;td.ddpfPixelFormat.dwRBitMask=0x7c00;td.ddpfPixelFormat.dwGBitMask=0x3e0;td.ddpfPixelFormat.dwBBitMask=0x1f;td.ddpfPixelFormat.dwRGBAlphaBitMask=0x8000;
   IDirectDrawSurface7* texture=nullptr;hr(draw->CreateSurface(&td,&texture,nullptr),"texture");
   // Populate native resource table, then execute the original native BindTexture.
   *reinterpret_cast<IDirectDrawSurface7**>(object.data()+0x100ea0+4*id)=texture;
   using BindFn=void(__thiscall*)(void*,DWORD,DWORD);
   reinterpret_cast<BindFn>(b+0x7a67)(object.data(),0xde1,id);
   ULONG refs=texture->AddRef();texture->Release();check(refs>=3,"device did not retain surface");if(!cycle)std::cout<<"NATIVE_TEXTURE_REFS after_bind="<<(refs-1)<<std::endl;
   *reinterpret_cast<IDirectDrawSurface7**>(object.data()+0x100ea0+4*id)=texture;*reinterpret_cast<DWORD*>(object.data()+0x104ea0+4*id)=1;
   auto erase=reinterpret_cast<DeleteFn>(*reinterpret_cast<DWORD*>(b+0x1a6ac));erase(object.data(),1,&id);
   check(*reinterpret_cast<DWORD*>(object.data()+0x104ea0+4*id)==0&&*reinterpret_cast<DWORD*>(object.data()+0x100ea0+4*id)==0,"native delete not completed");
   IDirectDrawSurface7* remaining=nullptr;hr(device->GetTexture(0,&remaining),"query after native delete");if(remaining){++residual;remaining->Release();}
   // Deliberately leave the old scene bound across creation of the next texture.
   // The next native BindTexture performs replacement; no manual unbind hides a failure.
  }
  if(hooked){check(removeCurrentTextureLifetime(image),"remove hook");hooked=false;check(*reinterpret_cast<DWORD*>(b+0x1a6ac)==original,"rollback slot mismatch");}
  hr(device->SetTexture(0,nullptr),"final unbind");
  std::cout<<"NATIVE_TEXTURE_RESULT mode="<<(baseline?"baseline":rollback?"rollback":"candidate")<<" cycles=200 residual_bound_after_delete="<<residual<<" actual_driver_delete=true actual_d3d7=true driver_entry_executed=false game_started=false"<<std::endl;
  check(residual==((baseline||rollback)?200u:0u),"unexpected binding observation");
  std::cout<<"NATIVE_TEXTURE_OBSERVATION_PASS access_violation=false retained_reference_is_not_uaf=true game_crash_reproduced=false rollback=exact"<<std::endl;result=0;
 }catch(const std::exception& e){std::cerr<<"NATIVE_TEXTURE_PROBE_FAIL "<<e.what()<<std::endl;}
 if(hooked)removeCurrentTextureLifetime(image);if(device)device->Release();if(target)target->Release();if(d3d)d3d->Release();if(draw)draw->Release();if(window)DestroyWindow(window);if(image)FreeLibrary(image);return result;
}
