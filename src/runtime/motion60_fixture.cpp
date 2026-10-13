#include "motion60.h"
#include <cstring>
#include <cstdio>
#include <cmath>
static BYTE object[0x120],action[0x24],record[8],data[0x24];static BYTE* sequence[1];static MotionMatrix pose[1];static float observed;static int checks=0;static int absoluteCalls=0;static bool throwSeh=false;
void require(bool b,const char* text){++checks;if(!b){fprintf(stderr,"FAIL %s\n",text);fflush(stderr);ExitProcess(1);}}
MotionMatrix identity(float x){MotionMatrix m{};m.v[0]=m.v[5]=m.v[10]=m.v[15]=1;m.v[12]=x;return m;}
void __cdecl absolute(void*,unsigned,MotionMatrix* p,MotionMatrix*){++absoluteCalls;p[0].v[12]+=100;}
void __fastcall draw(void*,void*,int frame,MotionMatrix*,int,int,int,int,int){pose[0]=identity(static_cast<float>(frame*10));motion60TestAbsolute(data,0,pose,nullptr);observed=pose[0].v[12];if(throwSeh)RaiseException(0xe0000001,0,0,nullptr);}
bool sehProbe(){__try {motion60TestRender(object,2);}__except(EXCEPTION_EXECUTE_HANDLER){return true;}return false;}
int main(){
 BYTE* image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(image!=nullptr,"fixture allocation");motion60TestInitialize(image,&absolute);
 DWORD oldRender=*reinterpret_cast<DWORD*>(image+0xbd9f8),oldIat=*reinterpret_cast<DWORD*>(image+0xbd0a4);
 require(motion60TestSetMapped(image,0x10b000,&absolute,true),"source installer");require(motion60TestSetMapped(image,0x10b000,&absolute,true),"idempotent install");
 image[0x3b0c0]^=1;require(!motion60TestSetMapped(image,0x10b000,&absolute,true),"prefix drift rejection");require(!motion60TestSetMapped(image,0x10b000,&absolute,false),"rollback rejects prefix drift");image[0x3b0c0]^=1;
 require(motion60TestSetMapped(image,0x10b000,&absolute,false),"rollback applies");require(*reinterpret_cast<DWORD*>(image+0xbd9f8)==oldRender&&*reinterpret_cast<DWORD*>(image+0xbd0a4)==oldIat,"rollback exact slots");
 require(motion60TestSetMapped(image,0x10b000,&absolute,false),"rollback idempotent");image[0x3b7fb]^=1;require(!motion60TestSetMapped(image,0x10b000,&absolute,true),"call drift rejection");image[0x3b7fb]^=1;
 *reinterpret_cast<DWORD*>(image+0xbd0a4)=1;require(!motion60TestSetMapped(image,0x10b000,&absolute,true),"iat drift rejection");*reinterpret_cast<DWORD*>(image+0xbd0a4)=oldIat;
 require(!motion60TestSetMapped(image,0x100000,&absolute,true),"image size rejection");VirtualFree(image,0,MEM_RELEASE);
 *reinterpret_cast<MotionMatrix**>(object+0x8c)=pose;*reinterpret_cast<void**>(object+0xa0)=action;*reinterpret_cast<BYTE***>(action+0x18)=sequence;sequence[0]=record;*reinterpret_cast<BYTE**>(record+4)=data;*reinterpret_cast<unsigned*>(data+0x14)=1;
 motion60TestConfigure(reinterpret_cast<MotionRenderFn>(&draw),&absolute);
 motion60TestSetTime(0);
 motion60TestRender(object,0);require(observed==100,"first frame unchanged");require(pose[0].v[12]==100,"baseline absolute restored");
 motion60TestRender(object,1);require(observed<101,"next tick begins previous pose");require(pose[0].v[12]==110,"next baseline restored");
 motion60TestSetTime(17);motion60TestRender(object,1);require(observed>102&&observed<109,"deterministic half step pose drawn");require(pose[0].v[12]==110,"halfstep cannot contaminate next logic");
 motion60TestSetTime(57);motion60TestRender(object,1);require(observed==110,"latest pose reached");
 throwSeh=true;require(sehProbe(),"SEH propagated");throwSeh=false;require(pose[0].v[12]==120,"SEH exact absolute restore");
 motion60TestRender(object,9);require(observed==190,"discontinuous frame resets");
 motion60TestSetTime(327);motion60TestRender(object,10);require(observed==200,"pause resets");
 *reinterpret_cast<unsigned*>(data+0x14)=513;int before=absoluteCalls;motion60TestRender(object,11);require(absoluteCalls==before+1,"invalid count original only");require(observed==210,"invalid count untouched");
 auto a=identity(0),b=identity(10);MotionMatrix out{};motion60TestBlend(a,b,.5f,out);require(std::abs(out.v[12]-5)<.001f,"translation interpolates");b.v[0]=-1;b.v[5]=-1;motion60TestBlend(a,b,.5f,out);require(std::abs(out.v[0])<.001f&&std::abs(out.v[1])>.99f,"rotation nlerp intermediate");
 b=identity(10);b.v[0]=2;motion60TestBlend(a,b,.5f,out);require(out.v[0]==2&&out.v[12]==10,"nonrigid bypass");
 printf("MOTION60_FIXTURE PASS checks=%d real_hook_calls=true intermediate_pose=true restore=exact logic_ticks=unchanged commercial_code_executed=false game_started=false\n",checks);return 0;
}
