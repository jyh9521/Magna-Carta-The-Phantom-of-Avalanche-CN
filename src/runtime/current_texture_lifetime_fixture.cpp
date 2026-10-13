#include "current_texture_lifetime.h"
#include <d3d.h>
#include <vector>
#include <iostream>
#include <cstring>
struct Surface {void** table; unsigned refs=1;};
Surface a{},b{}; Surface* bound[8]{}; unsigned checks=0,deleted=0,unbound=0;bool hazard=false,queryFail=false,unbindFail=false;
void require(bool v){++checks;if(!v){std::cout<<"CURRENT_TEXTURE_FAIL check="<<checks<<std::endl;ExitProcess(1);}}
ULONG WINAPI release(void* p){return --static_cast<Surface*>(p)->refs;}
HRESULT WINAPI get(void*,DWORD n,void** p){if(queryFail)return E_FAIL;*p=bound[n];if(bound[n])++bound[n]->refs;return S_OK;}
HRESULT WINAPI set(void*,DWORD n,void*){if(unbindFail)return E_FAIL;bound[n]=nullptr;++unbound;return S_OK;}
DWORD __fastcall erase(void* obj,void*,int n,const DWORD* ids){++deleted;for(int i=0;i<n;i++){auto s=*reinterpret_cast<Surface**>(static_cast<BYTE*>(obj)+0x100ea0+ids[i]*4);for(auto v:bound)if(v&&v==s)hazard=true;}return 0x1234;}
int main(){void* st[3]{};st[2]=reinterpret_cast<void*>(&release);a.table=b.table=st;void* dt[36]{};dt[34]=reinterpret_cast<void*>(&get);dt[35]=reinterpret_cast<void*>(&set);void** d=dt;
std::vector<BYTE> obj(0x123000);*reinterpret_cast<void**>(obj.data()+0x2c)=&d;
*reinterpret_cast<Surface**>(obj.data()+0x100ea0+6*4)=&a;*reinterpret_cast<DWORD*>(obj.data()+0x104ea0+6*4)=1;
*reinterpret_cast<Surface**>(obj.data()+0x100ea0+7*4)=&b;*reinterpret_cast<DWORD*>(obj.data()+0x104ea0+7*4)=1;
DWORD id=6;bound[0]=&a;erase(obj.data(),nullptr,1,&id);require(hazard);std::cout<<"CURRENT_TEXTURE_BASELINE hazard=true"<<std::endl;hazard=false;deleted=0;
configureCurrentTextureFixture(reinterpret_cast<CurrentDeleteFn>(&erase));bound[0]=&a;bound[7]=&a;bound[1]=&b;
require(currentTextureFixtureDelete(obj.data(),nullptr,1,&id)==0x1234);require(!hazard&&deleted==1&&unbound==2);require(bound[1]==&b&&a.refs==1&&b.refs==1);
queryFail=true;require(currentTextureFixtureDelete(obj.data(),nullptr,1,&id)==0);require(deleted==1);queryFail=false;
bound[0]=&a;unbindFail=true;require(currentTextureFixtureDelete(obj.data(),nullptr,1,&id)==0);require(deleted==1&&a.refs==1&&bound[0]==&a);unbindFail=false;
require(currentTextureFixtureDelete(obj.data(),nullptr,1,&id)==0x1234);require(deleted==2&&!hazard);DWORD bad=4096;require(currentTextureFixtureDelete(obj.data(),nullptr,1,&bad)==0);require(deleted==2);
require(currentTextureFixtureDelete(obj.data(),nullptr,0,nullptr)==0x1234);
auto m=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2c000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(m!=nullptr);require(!installCurrentTextureLifetime(reinterpret_cast<HMODULE>(m),nullptr));
auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(m);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(m+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x2c000;
auto t=reinterpret_cast<DWORD*>(m+0x1a5a8);DWORD orig=reinterpret_cast<DWORD>(m+0x52c8);t[0x104/4]=orig;t[0x2c/4]=reinterpret_cast<DWORD>(m+0x7a67);
const BYTE code[]={0x55,0x8b,0xec,0x83,0xec,8,0x89,0x4d,0xf8,0x33,0xc0,0x85,0xc0,0x74,5};memcpy(m+0x52c8,code,sizeof code);
m[0x52c8]^=1;require(!installCurrentTextureLifetime(reinterpret_cast<HMODULE>(m),nullptr));m[0x52c8]^=1;
DWORD old;VirtualProtect(t,0x108,PAGE_READONLY,&old);require(installCurrentTextureLifetime(reinterpret_cast<HMODULE>(m),nullptr));require(t[0x104/4]!=orig);require(installCurrentTextureLifetime(reinterpret_cast<HMODULE>(m),nullptr));
MEMORY_BASIC_INFORMATION info{};VirtualQuery(t,&info,sizeof info);require(info.Protect==PAGE_READONLY);DWORD protectedOld;VirtualProtect(t,0x108,PAGE_READWRITE,&protectedOld);DWORD hooked=t[0x104/4];t[0x104/4]=orig;VirtualProtect(t,0x108,protectedOld,&old);require(!installCurrentTextureLifetime(reinterpret_cast<HMODULE>(m),nullptr));require(!removeCurrentTextureLifetime(reinterpret_cast<HMODULE>(m)));VirtualProtect(t,0x108,PAGE_READWRITE,&protectedOld);t[0x104/4]=hooked;VirtualProtect(t,0x108,protectedOld,&old);
require(removeCurrentTextureLifetime(reinterpret_cast<HMODULE>(m)));require(t[0x104/4]==orig);require(removeCurrentTextureLifetime(reinterpret_cast<HMODULE>(m)));VirtualFree(m,0,MEM_RELEASE);
std::cout<<"CURRENT_TEXTURE_PASS checks="<<checks<<" actual_binding=true failed_delete_deferred=true refs_balanced=true rollback=exact game_started=false"<<std::endl;
}
