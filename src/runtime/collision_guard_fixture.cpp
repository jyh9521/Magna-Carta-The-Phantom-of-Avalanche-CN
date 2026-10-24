#include "collision_guard.h"
#include "collision_kernel.h"
#include <cstdio>
#include <cstring>
#include <vector>
#include <cmath>
static BYTE* image;static BYTE actor[0x340],scene[0x1740],gui[0x198],visual[0x150],model[0x80],bounds[0x80],level[0x100],guide[0x130],tree[0x40],node[0x50];
static unsigned checks=0,calls=0,syncs=0,queries=0;static CollisionVec requested{},observed{};
unsigned& word(void* p,unsigned o){return *reinterpret_cast<unsigned*>(static_cast<BYTE*>(p)+o);}
void require(bool b,const char* why){++checks;if(!b){std::fprintf(stderr,"COLLISION_GUARD FAIL %s\n",why);ExitProcess(1);}}
void __fastcall physics(void* p,void*){++calls;require(GetLastError()==0x2468,"original incoming error");memcpy(static_cast<BYTE*>(p)+0x154,&requested,12);SetLastError(0x1234);}
int __fastcall point(void*,void*,float x,float,float){++queries;memset(tree+0x14,0x87,28);SetLastError(0xdead);return x<0;}
void __fastcall synchronize(void* p,void*,float x,float y,float z){++syncs;observed={x,y,z};memcpy(static_cast<BYTE*>(p)+0x48,&observed,12);SetLastError(0xdead);}
void logger(const wchar_t*){SetLastError(0xbad);}
void reset(float x){CollisionVec p{x,0,0};memcpy(actor+0x154,&p,12);word(scene,0x156c)=2;word(scene,0x1574)=0;}
CollisionVec run(float before,float after){reset(before);requested={after,0,0};BYTE cache[28];memcpy(cache,tree+0x14,28);unsigned n=calls;
 DWORD stackBefore;__asm mov stackBefore,esp
 SetLastError(0x2468);invokeCollisionGuardFixture(actor);
 DWORD end;__asm mov end,esp
 require(stackBefore==end,"stack unchanged");require(calls==n+1,"original once");require(GetLastError()==0x1234,"output error unchanged");require(!memcmp(cache,tree+0x14,28),"oracle scratch restored");CollisionVec p{};memcpy(&p,actor+0x154,12);return p;}
int __cdecl wall(CollisionVec p,void*){return p.x>=-1&&p.x<=1;}
int __cdecl unknown(CollisionVec,void*){return -1;}
int main(int argc,char** argv){
 bool baseline=argc==2&&!strcmp(argv[1],"--baseline");
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(image!=nullptr,"owned image");initializeCollisionGuardFixture(image);
 word(actor,0)=DWORD(image+0xc11e4);word(actor,0x20)=DWORD(scene);word(actor,0x2dc)=DWORD(visual);
 word(scene,0)=DWORD(image+0xc12bc);word(scene,0x1564)=DWORD(actor);word(scene,0x1558)=DWORD(level);
 word(scene,0x10c8)=DWORD(gui);word(gui,0x190)=1;
 word(level,0)=DWORD(image+0xc15ac);word(level,0xf4)=DWORD(guide);word(guide,0x120)=DWORD(tree);word(tree,0x30)=DWORD(node);
 word(visual,0x140)=DWORD(model);word(model,0x58)=DWORD(bounds);
 CollisionVec box[8];unsigned i=0;for(float x:{-2.f,2.f})for(float y:{-2.f,2.f})for(float z:{0.f,6.f})box[i++]={x,y,z};memcpy(bounds+0x20,box,96);
 configureCollisionGuardFixture(reinterpret_cast<void(__thiscall*)(void*)>(&physics),reinterpret_cast<int(__thiscall*)(void*,float,float,float)>(&point),reinterpret_cast<void(__thiscall*)(void*,float,float,float)>(&synchronize));
 if(baseline){reset(10);requested={-1,0,0};SetLastError(0x2468);physics(actor,nullptr);std::puts("COLLISION_GUARD BASELINE invalid_endpoint=accepted policy=absent game_started=false");return 1;}
 std::vector<BYTE> pristine(image,image+0x10b000);DWORD old;require(VirtualProtect(image,0x10b000,PAGE_EXECUTE_READ,&old)!=0,"owned RX image");require(installCollisionGuard(HMODULE(image),logger),"install");require(installCollisionGuard(HMODULE(image),logger),"idempotent");
 auto p=run(10,9);require(p.x==9&&syncs==0,"free movement exact");
 p=run(10,-1);require(p.x>=2&&p.x<2.01f&&syncs==1&&observed.x==p.x,"new overlap clipped and visual synced");
 p=run(1,1);require(p.x>=2&&p.x<=2.5f&&syncs==2,"inside start recovered rather than all directions locked");
 p=run(-100,-100);require(p.x==-100&&syncs==2,"deep solids never teleport");
 reset(10);word(scene,0x156c)=6;requested={-1,0,0};SetLastError(0x2468);invokeCollisionGuardFixture(actor);memcpy(&p,actor+0x154,12);require(p.x==-1&&syncs==2,"scripted mode excluded");
 reset(10);word(scene,0x1574)=1;SetLastError(0x2468);invokeCollisionGuardFixture(actor);require(syncs==2,"event lock excluded");
 CollisionVec out{};require(resolveCollisionStep({10,0,0},{-10,0,0},nullptr,0,wall,nullptr,&out)==1&&out.x>1,"thin wall sweep prevents tunnelling");
 require(resolveCollisionStep({10,0,0},{20,0,0},nullptr,0,unknown,nullptr,&out)==4&&out.x==20,"unknown query not accepted as geometry");
 require(resolveCollisionStep({10,0,0},{20,0,0},box,9,wall,nullptr,&out)==4,"offset count guarded");
 require(removeCollisionGuard(HMODULE(image)),"remove");require(!memcmp(image,pristine.data(),pristine.size()),"whole image byte exact rollback");
 require(VirtualProtect(image,0x10b000,PAGE_EXECUTE_READWRITE,&old)!=0,"mutate owned negative");image[0x65699]^=1;require(!installCollisionGuard(HMODULE(image),logger),"unknown source refused");
 std::printf("COLLISION_GUARD PASS checks=%u physics_calls=%u queries=%u map_specific=false bounds=native8 rollback=byte_exact game_started=false\n",checks,calls,queries);
 return 0;
}
