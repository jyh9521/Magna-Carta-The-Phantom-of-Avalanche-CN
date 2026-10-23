#include "motion60.h"
#include <cstdio>
#include <cstring>
#include <cmath>
#include <stdexcept>
#ifdef BASELINE_NATIVE_PATH
bool motion60TestNativeMapped(BYTE*,size_t,bool){return true;}
#endif
static BYTE* native;static unsigned absoluteSite=0x4be50;static float offset=0,observed=0;static BYTE bones[12]{};
MotionMatrix identity(float x){MotionMatrix m{};m.v[0]=m.v[5]=m.v[10]=m.v[15]=1;m.v[12]=x;return m;}
void check(bool ok,const char* what){if(!ok)throw std::runtime_error(what);}
void __cdecl absolute(void*,unsigned,MotionMatrix* pose,MotionMatrix*){pose->v[12]+=100;}
void __fastcall draw(void* object,void*,int,MotionMatrix* parent,int,int,int,int,int){
 auto o=static_cast<BYTE*>(object);auto pose=*reinterpret_cast<MotionMatrix**>(o+0x8c);pose[0]=identity(offset);
 *reinterpret_cast<MotionMatrix*>(o+0xc)=parent?*parent:identity(0);
 reinterpret_cast<MotionAbsoluteFn>(native+absoluteSite-15)(bones,0,pose,nullptr);observed=pose[0].v[12];
}
void jump(BYTE* p,void* fn){p[0]=0xe9;*reinterpret_cast<int*>(p+1)=int(reinterpret_cast<BYTE*>(fn)-p-5);}
int main(){try{
 native=static_cast<BYTE*>(VirtualAlloc(nullptr,0x74d000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(native,"native allocation");
 auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(native);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(native+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x74d000;
 BYTE skin[]={0x55,0x8b,0xec,0x81,0xec,0xf8,3,0,0},rigid[]={0x55,0x8b,0xec,0x81,0xec,0xf0,1,0,0};memcpy(native+0x4b6c2,skin,9);memcpy(native+0x4d6c3,rigid,9);
 for(unsigned rva:{0x4b6c2u,0x4d6c3u}){auto p=native+rva+9;*p++=0x8b;*p++=0xe5;*p++=0x5d;jump(p,reinterpret_cast<void*>(&draw));}
 for(unsigned rva:{0x4be50u,0x4dbd7u}){auto p=native+rva;p[0]=0xe8;*reinterpret_cast<int*>(p+1)=int(0x44f0d-rva-5);BYTE args[]={0x55,0x8b,0xec,0xff,0x75,0x14,0xff,0x75,0x10,0xff,0x75,0x0c,0xff,0x75,0x08};memcpy(p-15,args,15);BYTE tail[]={0x83,0xc4,0x10,0x5d,0xc3};memcpy(p+5,tail,5);}jump(native+0x44f0d,reinterpret_cast<void*>(&absolute));
 auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));motion60TestInitialize(image,absolute);motion60TestConfigure(reinterpret_cast<MotionRenderFn>(&draw),absolute);motion60TestComplete(image,true);
 check(motion60TestNativeMapped(native,0x74d000,true),"native install");check(motion60TestNativeMapped(native,0x74d000,true),"idempotent");

#ifndef BASELINE_NATIVE_PATH
 check(motion60TestNativeSource(native+0x4be55,false)&&motion60TestNativeSource(native+0x4dbdc,true),"native return PCs admitted");
 check(!motion60TestNativeSource(native+0x4be55,true)&&!motion60TestNativeSource(native+0x4dbdc,false)&&!motion60TestNativeSource(native+0x4be56,false),"wrong renderer and interior PCs rejected");
#endif
 BYTE object[0x100]{},action[0x28]{},data[0x28]{};MotionMatrix pose{};BYTE* table[]={data};unsigned sequence[]={0,0};
 *reinterpret_cast<BYTE***>(native+0x7e0dc)=table;*reinterpret_cast<BYTE***>(native+0x7e0e0)=table+1;
 *reinterpret_cast<unsigned*>(data+0x14)=1;*reinterpret_cast<BYTE**>(object+8)=data;*reinterpret_cast<BYTE**>(object+0xa0)=action;*reinterpret_cast<MotionMatrix**>(object+0x8c)=&pose;
 *reinterpret_cast<unsigned*>(action+4)=2;*reinterpret_cast<unsigned*>(action+8)=1;*reinterpret_cast<unsigned**>(action+0x18)=sequence;
 for(unsigned renderer:{0x4b6c2u,0x4d6c3u}){
  absoluteSite=renderer==0x4b6c2?0x4be50:0x4dbd7;auto render=reinterpret_cast<MotionRenderFn>(native+renderer);
  motion60TestComplete(image,true);auto world=identity(0);offset=0;motion60TestTick(0,0,1000);render(object,0,&world,0,0,0,0,0);
  offset=10;*reinterpret_cast<unsigned*>(object+0xf8)=1;motion60TestTick(1,16,1049);render(object,1,&world,0,0,0,0,0);
  check(std::abs(observed-(100+10*16.f/33))<.001f,"base actor midpoint must not pass latest30Hz pose");check(pose.v[12]==110,"native absolute pose restored");
 }
 native[0x4dbd7]^=1;check(!motion60TestNativeMapped(native,0x74d000,false),"unknown call rejected before writes");native[0x4dbd7]^=1;
 check(motion60TestNativeMapped(native,0x74d000,false),"remove");check(!memcmp(native+0x4b6c2,skin,9)&&!memcmp(native+0x4d6c3,rigid,9),"exact native entries restored");
 for(unsigned rva:{0x4b6c2u,0x4d6c3u,0x4be50u,0x4dbd7u}){native[rva]^=1;check(!motion60TestNativeMapped(native,0x74d000,true),"drift rejects whole transaction");native[rva]^=1;}
 VirtualFree(native,0,MEM_RELEASE);VirtualFree(image,0,MEM_RELEASE);
 puts("NATIVE_ACTOR_MOTION PASS base_skin=interpolated base_rigid=interpolated phase=shared restore=exact drift=rejected rollback=exact game_started=false");return 0;
}catch(const std::exception& e){printf("NATIVE_ACTOR_MOTION FAIL %s observed=%.6f\n",e.what(),observed);return 1;}}
