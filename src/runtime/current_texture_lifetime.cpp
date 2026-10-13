#include "current_texture_lifetime.h"
#include <d3d.h>
#include <cstring>
namespace {
using DeleteFn=DWORD(__thiscall*)(void*,int,const DWORD*);
DeleteFn original=nullptr; HMODULE installed=nullptr;void(*logger)(const wchar_t*)=nullptr;
void log(const wchar_t* s){if(logger)logger(s);}
DWORD __fastcall hook(void* object,void*,int count,const DWORD* ids){
 if(count==0)return original(object,count,ids);
 if(count<0||count>4096||!ids){log(L"TEXTURE_CURRENT_INVALID_DELETE");return 0;}
 auto bytes=static_cast<BYTE*>(object);
 // Validate the whole batch before changing bindings. No fixed-size object cache.
 for(int i=0;i<count;++i)if(ids[i]>=4096){log(L"TEXTURE_CURRENT_INVALID_ID");return 0;}
 auto device=*reinterpret_cast<IDirect3DDevice7**>(bytes+0x2c);
 if(!device){log(L"TEXTURE_CURRENT_DELETE_DEFERRED_NO_DEVICE");return 0;}
 for(DWORD stage=0;stage<8;++stage){
  IDirectDrawSurface7* bound=nullptr;HRESULT query=device->GetTexture(stage,&bound);
  if(FAILED(query)){if(bound)bound->Release();log(L"TEXTURE_CURRENT_DELETE_DEFERRED_QUERY");return 0;}
  if(!bound)continue;
  bool deleting=false;
  for(int i=0;i<count;++i){DWORD id=ids[i];if(*reinterpret_cast<DWORD*>(bytes+0x104ea0+4*id)==1&&
    *reinterpret_cast<IDirectDrawSurface7**>(bytes+0x100ea0+4*id)==bound){deleting=true;break;}}
  HRESULT result=deleting?device->SetTexture(stage,nullptr):S_OK;
  bound->Release(); // GetTexture's temporary COM reference, not the driver's table reference.
  if(FAILED(result)){log(L"TEXTURE_CURRENT_DELETE_DEFERRED_UNBIND");return 0;}
  if(deleting)log(L"TEXTURE_CURRENT_UNBOUND_BEFORE_DELETE");
 }
 return original(object,count,ids);
}
bool exchange(DWORD* slot,DWORD expected,DWORD value){DWORD prior;if(!VirtualProtect(slot,4,PAGE_READWRITE,&prior))return false;
 bool changed=InterlockedCompareExchange(reinterpret_cast<LONG*>(slot),value,expected)==static_cast<LONG>(expected);
 DWORD ignored;if(!VirtualProtect(slot,4,prior,&ignored)){if(changed)InterlockedCompareExchange(reinterpret_cast<LONG*>(slot),expected,value);VirtualProtect(slot,4,prior,&ignored);return false;}return changed;}
}
bool installCurrentTextureLifetime(HMODULE module,void(*callback)(const wchar_t*)){
 if(installed)return installed==module && *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(module)+0x1a6ac)==reinterpret_cast<DWORD>(&hook);
 auto b=reinterpret_cast<BYTE*>(module);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(b);
 if(!b||d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096)return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(b+d->e_lfanew);
 if(n->Signature!=IMAGE_NT_SIGNATURE||n->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||n->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||n->OptionalHeader.SizeOfImage!=0x2c000)return false;
 auto t=reinterpret_cast<DWORD*>(b+0x1a5a8);const BYTE code[]={0x55,0x8b,0xec,0x83,0xec,8,0x89,0x4d,0xf8,0x33,0xc0,0x85,0xc0,0x74,5};
 if(t[0x104/4]!=reinterpret_cast<DWORD>(b+0x52c8)||t[0x2c/4]!=reinterpret_cast<DWORD>(b+0x7a67)||memcmp(b+0x52c8,code,sizeof code))return false;
 original=reinterpret_cast<DeleteFn>(b+0x52c8);logger=callback;
 if(!exchange(t+0x104/4,reinterpret_cast<DWORD>(original),reinterpret_cast<DWORD>(&hook))){original=nullptr;logger=nullptr;return false;}
 installed=module;return true;
}
bool removeCurrentTextureLifetime(HMODULE module){if(!installed)return true;if(installed!=module)return false;
 auto slot=reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(module)+0x1a6ac);
 if(!exchange(slot,reinterpret_cast<DWORD>(&hook),reinterpret_cast<DWORD>(original)))return false;
 installed=nullptr;original=nullptr;logger=nullptr;return true;}
#ifdef CURRENT_TEXTURE_TEST
void configureCurrentTextureFixture(CurrentDeleteFn fn){original=fn;}
DWORD __fastcall currentTextureFixtureDelete(void* obj,void*,int n,const DWORD* ids){return hook(obj,nullptr,n,ids);}
#endif
