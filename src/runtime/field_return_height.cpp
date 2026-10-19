#include "field_return_height.h"
#include <cmath>
#include <cstring>
#include <cstdint>
#include <cwchar>
namespace {
using Position = void(__thiscall*)(void*,float,float,float);
constexpr unsigned callRva=0x75c0a, imageSize=0x10b000;
constexpr BYTE callBytes[]={0xe8,0x64,0x4b,0xfe,0xff};
constexpr BYTE commandPrefix[]={0x55,0x8b,0xec,0x6a,0xff,0x68};
constexpr BYTE positionPrefix[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc};
BYTE* engine=nullptr; Position original=nullptr;
void(*trace)(const wchar_t*)=nullptr; unsigned notices=0;
bool readable(const void* value,size_t count){
 auto p=reinterpret_cast<uintptr_t>(value);
 if(!p||!count||count>~uintptr_t(0)-p)return false;
 const auto end=p+count;
 while(p<end){MEMORY_BASIC_INFORMATION m{};
  if(!VirtualQuery(reinterpret_cast<const void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  DWORD a=m.Protect&0xff;
  if(a!=PAGE_READONLY&&a!=PAGE_READWRITE&&a!=PAGE_WRITECOPY&&a!=PAGE_EXECUTE_READ&&a!=PAGE_EXECUTE_READWRITE&&a!=PAGE_EXECUTE_WRITECOPY)return false;
  auto base=reinterpret_cast<uintptr_t>(m.BaseAddress);if(m.RegionSize>~uintptr_t(0)-base)return false;
  auto next=base+m.RegionSize;if(next<=p)return false;p=next<end?next:end;
 }return true;
}
int integer(const BYTE* p,unsigned o){return *reinterpret_cast<const int*>(p+o);}
BYTE* pointer(const BYTE* p,unsigned o){return *reinterpret_cast<BYTE*const*>(p+o);}
bool vtable(const BYTE* p,unsigned rva){return pointer(p,0)==engine+rva;}
unsigned fnv(const BYTE* p,size_t n){unsigned h=2166136261u;for(size_t i=0;i<n;++i)h=(h^p[i])*16777619u;return h;}
bool selectHeight(BYTE* actor,float x,float y,float& z){
 if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(z))return false;
 if(!engine||!readable(actor,0x340)||!vtable(actor,0xc11e4)||integer(actor,0x328)!=0)return false;
 auto scene=pointer(actor,0x20);
 if(!readable(scene,0x1568)||!vtable(scene,0xc12bc)||integer(scene,0x10cc)!=757||pointer(scene,0x1564)!=actor)return false;
 auto dealer=pointer(scene,0x3c);
 if(!readable(dealer,0x74)||!vtable(dealer,0xc1320)||pointer(dealer,0x54)!=scene||integer(dealer,0x30)!=4)return false;
 auto plans=pointer(dealer,0x2c);if(!readable(plans,4*56))return false;
 auto plan=plans+2*56;
 if(integer(plan,0)!=2||integer(plan,0xc)!=0||integer(plan,0x20)!=6||integer(plan,0x24)!=1)return false;
 auto condition=pointer(plan,8);auto actions=pointer(plan,4);
 if(!readable(condition,60)||integer(condition,0)!=304||integer(condition,4)!=10000||integer(condition,8)!=1)return false;
 for(unsigned i=12;i<60;i+=4)if(integer(condition,i)!=0)return false;
 // Exact six-command script identity, independent of the translated display label.
 if(!readable(actions,360)||fnv(actions,360)!=0xb82b40d0u)return false;
 auto slots=pointer(dealer,0x34);int count=integer(dealer,0x38);
 // Native scene initialization at 68BBF pushes 150 command slots (68BC1).
 if(count<2||count>256||!readable(slots,size_t(count)*40))return false;
 BYTE* selected=nullptr;
 for(int i=0;i<count-1;++i){auto slot=slots+i*40;
  if(integer(slot,0)==202&&integer(slot,8)==2&&pointer(slot,0x14)==actions+64){if(selected)return false;selected=slot;}
 }
 if(!selected||integer(selected,4)<1)return false;
 auto mover=pointer(selected,0x18);
 if(!readable(mover,0x154)||!vtable(mover,0xbea64))return false;
 const float* point=reinterpret_cast<const float*>(mover+0x128);
 const float* target=reinterpret_cast<const float*>(mover+0x13c);
 for(unsigned i=0;i<3;++i)if(!std::isfinite(point[i])||!std::isfinite(target[i]))return false;
 if(point[0]!=x||point[1]!=y)return false;
 // The actual native marker must still be the interpolation destination.
 auto objects=pointer(scene,0x1518);int n=integer(scene,0x1514);
 if(n<1||n>4096||!readable(objects,size_t(n)*72))return false;
 const BYTE* marker=nullptr;
 for(int i=0;i<n;++i)if(integer(objects+i*72,0)==5){if(marker)return false;marker=objects+i*72;}
 constexpr DWORD markerBits[]={0x437a3cac,0xc3dd1df4,0xc2c00000};
 if(!marker||memcmp(marker+12,target,12)||memcmp(target,markerBits,12))return false;
 z=point[2];return true;
}
void __fastcall positionHook(void* value,void*,float x,float y,float z){
 float before=z;
 bool changed=selectHeight(static_cast<BYTE*>(value),x,y,z);
 original(value,x,y,z);
 if(changed&&before!=z&&trace&&notices<8){++notices;wchar_t line[200];
  swprintf_s(line,L"FIELD_RETURN_HEIGHT_APPLIED field=757 plan=2 opcode=202 old_z=%.6f new_z=%.6f unlock=original",double(before),double(z));trace(line);
 }
}
void hookBytes(BYTE (&out)[5],BYTE* p){out[0]=0xe8;auto delta=reinterpret_cast<uintptr_t>(&positionHook)-reinterpret_cast<uintptr_t>(p+callRva+5);DWORD relative=DWORD(delta);memcpy(out+1,&relative,4);}
bool replace(BYTE* dst,const BYTE* from,const BYTE* to){
 if(memcmp(dst,from,5))return false;DWORD old;
 if(!VirtualProtect(dst,5,PAGE_EXECUTE_READWRITE,&old))return false;
 memcpy(dst,to,5);FlushInstructionCache(GetCurrentProcess(),dst,5);DWORD ignored;
 if(!VirtualProtect(dst,5,old,&ignored)){memcpy(dst,from,5);FlushInstructionCache(GetCurrentProcess(),dst,5);VirtualProtect(dst,5,old,&ignored);return false;}
 return true;
}
bool set(BYTE* p,bool on,void(*logger)(const wchar_t*)){
 if(!readable(p,sizeof(IMAGE_DOS_HEADER)))return false;auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096||!readable(p+dos->e_lfanew,sizeof(IMAGE_NT_HEADERS32)))return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);
 if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=imageSize)return false;
 if(!readable(p+callRva,5)||!readable(p+0x7591c,sizeof(commandPrefix))||!readable(p+0x5a773,sizeof(positionPrefix)))return false;
 if(memcmp(p+0x7591c,commandPrefix,sizeof(commandPrefix))||memcmp(p+0x5a773,positionPrefix,sizeof(positionPrefix)))return false;
 BYTE hook[5];hookBytes(hook,p);bool native=memcmp(p+callRva,callBytes,5)==0,ours=memcmp(p+callRva,hook,5)==0&&engine==p;
 if(!native&&!ours)return false;if(on&&ours)return true;if(!on&&native)return true;
 if(on){engine=p;trace=logger;notices=0;
#ifndef FIELD_RETURN_HEIGHT_TEST
 original=reinterpret_cast<Position>(p+0x5a773);
#endif
 }
 if(!replace(p+callRva,on?callBytes:hook,on?hook:callBytes))return false;
 if(on&&trace)trace(L"FIELD_RETURN_HEIGHT_READY field=757 plan=2 scope=source_locked_xyz_return only=true");
 if(!on){engine=nullptr;trace=nullptr;}return true;
}
}
bool installFieldReturnHeight(HMODULE p,void(*logger)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(p),true,logger);}
bool removeFieldReturnHeight(HMODULE p){return set(reinterpret_cast<BYTE*>(p),false,nullptr);}
#ifdef FIELD_RETURN_HEIGHT_TEST
void initializeFieldReturnHeightFixture(BYTE* p){memset(p,0,imageSize);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=imageSize;memcpy(p+callRva,callBytes,5);memcpy(p+0x7591c,commandPrefix,sizeof(commandPrefix));memcpy(p+0x5a773,positionPrefix,sizeof(positionPrefix));}
void configureFieldReturnHeightFixture(Position f){original=f;}
void invokeFieldReturnHeightFixture(void* actor,float x,float y,float z){positionHook(actor,nullptr,x,y,z);}
#endif
