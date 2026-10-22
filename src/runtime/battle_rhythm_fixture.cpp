#include "motion60.h"
#include <cstdio>
#include <cstring>
static BYTE model[0x120]{},action[0x24]{},record[8]{},data[0x24]{};static BYTE* sequence[1];static MotionMatrix pose[1];
static float seenPose=0,seenWorld=0;static int frame=1;static float x=10;
static MotionMatrix identity(float x){MotionMatrix m{};m.v[0]=m.v[5]=m.v[10]=m.v[15]=1;m.v[12]=x;return m;}
static void __cdecl absolute(void*,unsigned,MotionMatrix* m,MotionMatrix*){m->v[12]+=100;}
static void __fastcall render(void*,void*,int f,MotionMatrix* parent,int,int,int,int,int){pose[0]=identity(float(f*10));memcpy(model+0xc,parent,64);motion60TestAbsolute(data,0,pose,nullptr);seenPose=pose[0].v[12];seenWorld=reinterpret_cast<MotionMatrix*>(model+0xc)->v[12];}
static void __fastcall battle(void*,void*){auto world=identity(x);motion60TestRenderParent(model,frame,&world);}
int main(){
 auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));if(!image)return 2;
 motion60TestInitialize(image,&absolute);motion60TestComplete(image,true);motion60TestConfigure(reinterpret_cast<MotionRenderFn>(&render),&absolute);
 *reinterpret_cast<BYTE**>(model)=image+0xbd9f4;*reinterpret_cast<MotionMatrix**>(model+0x8c)=pose;*reinterpret_cast<BYTE**>(model+0xa0)=action;
 *reinterpret_cast<unsigned*>(action+4)=4;*reinterpret_cast<unsigned*>(action+8)=4;*reinterpret_cast<BYTE***>(action+0x18)=sequence;sequence[0]=record;*reinterpret_cast<BYTE**>(record+4)=data;*reinterpret_cast<unsigned*>(data+0x14)=1;
 BYTE scene[0x1e04]{},actor[0x2e0]{},graph[0x144]{},obs[0x60]{};
 *reinterpret_cast<BYTE**>(scene)=image+0xc195c;*reinterpret_cast<int*>(scene+0x1dc4)=*reinterpret_cast<int*>(scene+0x1dcc)=1;*reinterpret_cast<BYTE**>(scene+0x40)=actor;*reinterpret_cast<BYTE**>(actor)=image+0xc1644;
 *reinterpret_cast<BYTE**>(actor+0x2dc)=graph;*reinterpret_cast<BYTE**>(graph)=image+0xbe200;*reinterpret_cast<BYTE**>(graph+0x140)=obs;*reinterpret_cast<BYTE**>(obs)=image+0xbda2c;*reinterpret_cast<BYTE**>(obs+0x5c)=model;
 motion60TestTick(0,0,1000);frame=0;x=0;battle(nullptr,nullptr);motion60TestTick(1,16,1049);frame=1;x=10;
 motion60TestBattleDraw(scene,reinterpret_cast<void(__thiscall*)(void*)>(&battle));
 bool pass=seenPose==110&&seenWorld==10;
 printf("BATTLE_RHYTHM_COMPARE %s pose=%.6f world=%.6f expected_pose=110 expected_world=10 camera=not_modified game_started=false\n",pass?"PASS":"FAIL",seenPose,seenWorld);
 VirtualFree(image,0,MEM_RELEASE);return pass?0:1;
}
