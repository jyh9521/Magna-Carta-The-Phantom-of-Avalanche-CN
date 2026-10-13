#include "motion60.h"
#include <cstring>
#include <cstdio>
#include <cmath>
#include "render_timeline.h"
static BYTE object[0x120],action[0x24],record[8],data[0x24];static BYTE* sequence[1];static MotionMatrix pose[1];static float observed;static int checks=0;static int absoluteCalls=0;static bool throwSeh=false;
static bool transitionHistory=false;static MotionMatrix history[1];
static bool fullDraw=false,localDraw=false;static BYTE driver[0xe0],camera[0xc0];static float actorX=0,worldObserved=0;
void require(bool b,const char* text){++checks;if(!b){fprintf(stderr,"FAIL %s\n",text);fflush(stderr);ExitProcess(1);}}
MotionMatrix identity(float x){MotionMatrix m{};m.v[0]=m.v[5]=m.v[10]=m.v[15]=1;m.v[12]=x;return m;}
void __cdecl absolute(void*,unsigned,MotionMatrix* p,MotionMatrix*){++absoluteCalls;p[0].v[12]+=100;}
void __fastcall loadCamera(void* d,void*,MotionMatrix* m){memcpy(static_cast<BYTE*>(d)+0x5c,m,64);}
void __fastcall draw(void*,void*,int frame,MotionMatrix*,int,int,int,int,int){
 pose[0]=identity(static_cast<float>(frame*10));
 if(transitionHistory){pose[0].v[12]=(history[0].v[12]+pose[0].v[12])*.5f;history[0]=pose[0];}
 if(fullDraw){auto actor=identity(actorX);auto view=reinterpret_cast<motion::Matrix*>(driver+0x5c);auto w=localDraw?reinterpret_cast<const motion::Matrix&>(actor):motion::multiply(*view,reinterpret_cast<const motion::Matrix&>(actor));memcpy(object+0xc,&w,64);}
 motion60TestAbsolute(data,0,pose,nullptr);observed=pose[0].v[12];worldObserved=reinterpret_cast<MotionMatrix*>(object+0xc)->v[12];if(throwSeh)RaiseException(0xe0000001,0,0,nullptr);
}
void renderSample(int frame){if(fullDraw&&!localDraw)motion60TestRenderParent(object,frame,reinterpret_cast<MotionMatrix*>(driver+0x5c));else motion60TestRender(object,frame);}
bool sehProbe(){__try {renderSample(2);}__except(EXCEPTION_EXECUTE_HANDLER){return true;}return false;}
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
 renderSample(0);require(observed==100,"first frame unchanged");require(pose[0].v[12]==100,"baseline absolute restored");
 renderSample(1);require(observed<101,"next tick begins previous pose");require(pose[0].v[12]==110,"next baseline restored");
 motion60TestSetTime(17);renderSample(1);require(observed>102&&observed<109,"deterministic half step pose drawn");require(pose[0].v[12]==110,"halfstep cannot contaminate next logic");
 motion60TestSetTime(57);renderSample(1);require(observed==110,"latest pose reached");
 throwSeh=true;require(sehProbe(),"SEH propagated");throwSeh=false;require(pose[0].v[12]==120,"SEH exact absolute restore");
 renderSample(9);require(observed==190,"discontinuous frame resets");
 motion60TestSetTime(327);renderSample(10);require(observed==200,"pause resets");
 *reinterpret_cast<unsigned*>(data+0x14)=513;int before=absoluteCalls;renderSample(11);require(absoluteCalls==before+1,"invalid count original only");require(observed==210,"invalid count untouched");
 auto a=identity(0),b=identity(10);MotionMatrix out{};motion60TestBlend(a,b,.5f,out);require(std::abs(out.v[12]-5)<.001f,"translation interpolates");b.v[0]=-1;b.v[5]=-1;motion60TestBlend(a,b,.5f,out);require(std::abs(out.v[0])<.001f&&std::abs(out.v[1])>.99f,"rotation nlerp intermediate");
 b=identity(10);b.v[0]=2;motion60TestBlend(a,b,.5f,out);require(out.v[0]==2&&out.v[12]==10,"nonrigid bypass");
 *reinterpret_cast<unsigned*>(data+0x14)=1;
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image!=nullptr,"complete image");motion60TestInitialize(image,&absolute);
 BYTE timerBytes[]={0x8b,0x55,0xf8,0x8b,0x45,0xec};memcpy(image+0xcf61,timerBytes,6);
 // Owned executable wrapper establishes the same locals as the guarded timer site.
 BYTE enter[]={0x55,0x8b,0xec,0x83,0xec,0x14};memcpy(image+0xcf20,enter,6);BYTE* code=image+0xcf26;
 for(int i=0;i<4;++i){BYTE op[]={0x8b,0x45,static_cast<BYTE>(8+i*4),0x89,0x45,0};op[5]=static_cast<BYTE>(i==0?-0x14:i==1?-8:i==2?-4:-0x10);memcpy(code,op,6);code+=6;}
 memset(code,0x90,(image+0xcf61)-code);BYTE leave[]={0x8b,0xe5,0x5d,0xc3};memcpy(image+0xcf67,leave,4);
 motion60TestComplete(image,true);require(motion60TestTimerPatch(image,true),"install source-guarded timer site");require(motion60TestTimerPatch(image,true),"timer idempotent");
 auto tick=reinterpret_cast<void(__cdecl*)(BYTE*,BYTE*,unsigned,unsigned)>(image+0xcf20);
 BYTE info[0x24]{};*reinterpret_cast<unsigned*>(info+8)=33;*reinterpret_cast<unsigned*>(info+4)=1;auto manager=image+0xf2250;
 *reinterpret_cast<void**>(image+0xf2290)=camera;*reinterpret_cast<unsigned*>(driver+0x58)=0x1700;
 auto cameraMatrix=reinterpret_cast<MotionMatrix*>(camera+0x80);*cameraMatrix=identity(0);
 BYTE* driverImage=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2c000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(driverImage!=nullptr,"owned driver image");
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(driverImage);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(driverImage+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x2c000;
 BYTE loadPrefix[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xfc},mulPrefix[]={0x55,0x8b,0xec,0x81,0xec,0x48,0x02,0x00,0x00,0x56,0x57};
 memcpy(driverImage+0x356a,loadPrefix,sizeof(loadPrefix));memcpy(driverImage+0x7036,mulPrefix,sizeof(mulPrefix));
 auto emit=[&](BYTE* at,bool saved){if(saved){*at++=0x5f;*at++=0x5e;}*at++=0x8b;*at++=0xe5;*at++=0x5d;*at++=0xe9;*reinterpret_cast<int32_t*>(at)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(&loadCamera)-reinterpret_cast<ULONG_PTR>(at+4));};
 emit(driverImage+0x356a+sizeof(loadPrefix),false);emit(driverImage+0x7036+sizeof(mulPrefix),true);
 auto loadSlot=reinterpret_cast<DWORD*>(driverImage+0x1a838),mulSlot=reinterpret_cast<DWORD*>(driverImage+0x1a878);*loadSlot=reinterpret_cast<DWORD>(driverImage+0x356a);*mulSlot=reinterpret_cast<DWORD>(driverImage+0x7036);
 DWORD oldLoad=*loadSlot,oldMul=*mulSlot;
 require(motion60TestDriverSet(driverImage,true),"guarded camera installation");require(motion60TestDriverSet(driverImage,true),"camera idempotent install");
 driverImage[0x7036]^=1;require(!motion60TestDriverSet(driverImage,false),"driver rollback rejects prefix drift");driverImage[0x7036]^=1;
 auto appliedCamera=[&](){reinterpret_cast<void(__thiscall*)(void*,MotionMatrix*)>(*loadSlot)(driver,cameraMatrix);};
 fullDraw=true;actorX=0;tick(manager,info,0,0);motion60TestCamera(driver,cameraMatrix,reinterpret_cast<void(__thiscall*)(void*,MotionMatrix*)>(&loadCamera));renderSample(0);
 require(observed==100&&worldObserved==0,"complete first frame original");
 *reinterpret_cast<unsigned*>(manager+0x24)=33;actorX=10;*cameraMatrix=identity(-20);tick(manager,info,1,33);
 appliedCamera();renderSample(1);
 require(std::abs(worldObserved)<.001f&&observed==100,"world and pose start same phase");require(reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]==-10,"original modelview restored");
 *reinterpret_cast<unsigned*>(manager+0x24)=49;*reinterpret_cast<unsigned*>(info+0x10)=16;tick(manager,info,0,16);
 appliedCamera();renderSample(1);
 float alpha=16.f/33;require(std::abs(worldObserved+10*alpha)<.002f,"shared world camera midpoint without double lag");require(std::abs(observed-(100+10*alpha))<.002f,"bone midpoint engine remainder");
 require(cameraMatrix->v[12]==-20&&reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]==-10&&pose[0].v[12]==110,"camera world pose exact restoration");
 reinterpret_cast<void(__thiscall*)(void*,MotionMatrix*)>(*mulSlot)(driver,cameraMatrix);require(std::abs(reinterpret_cast<MotionMatrix*>(driver+0x5c)->v[12]+20*alpha)<.002f,"multiply camera path same phase");
 throwSeh=true;require(sehProbe(),"complete SEH propagates");throwSeh=false;require(reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]==-10&&pose[0].v[12]==120,"complete SEH restores world and pose");
 auto foreign=identity(99);motion60TestCamera(driver,&foreign,reinterpret_cast<void(__thiscall*)(void*,MotionMatrix*)>(&loadCamera));require(reinterpret_cast<MotionMatrix*>(driver+0x5c)->v[12]==99,"foreign transform bypass");
 *reinterpret_cast<unsigned*>(driver+0x58)=0x1701;motion60TestCamera(driver,cameraMatrix,reinterpret_cast<void(__thiscall*)(void*,MotionMatrix*)>(&loadCamera));require(reinterpret_cast<MotionMatrix*>(driver+0x5c)->v[12]==-20,"projection bypass");
 *reinterpret_cast<unsigned*>(driver+0x58)=0x1700;
 motion60TestFreeView(true,false,false,0,0);appliedCamera();
 motion60TestFreeView(true,true,false,0,0);appliedCamera();
 motion60TestFreeView(true,false,false,1,.05f);appliedCamera();
 require(std::abs(reinterpret_cast<MotionMatrix*>(driver+0x5c)->v[0]-1)>.0001f,"free orbit applied through real driver slot");
 require(cameraMatrix->v[12]==-20&&cameraMatrix->v[0]==1,"free orbit source camera immutable");
 renderSample(1);require(reinterpret_cast<MotionMatrix*>(object+0xc)->v[0]==1&&std::abs(reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]+10)<.002f,"free orbit draw restores original modelview not modified camera view");
 motion60TestFreeView(true,false,true,0,0);appliedCamera();require(reinterpret_cast<MotionMatrix*>(driver+0x5c)->v[0]==1,"free orbit reset restores original view orientation");
 motion60TestFreeView(false,false,false,0,0);appliedCamera();require(reinterpret_cast<MotionMatrix*>(driver+0x5c)->v[0]==1,"free orbit disabled leaves complete-motion camera unchanged");
 transitionHistory=true;history[0]=identity(0);*reinterpret_cast<MotionMatrix**>(object+0xf0)=history;
 *reinterpret_cast<unsigned*>(action+4)=100;*reinterpret_cast<unsigned*>(action+8)=100;
 motion60TestComplete(image,true);motion60TestTick(0,0,1000);renderSample(2);float stable=history[0].v[12];
 motion60TestTick(0,16,1016);renderSample(2);
 require(std::abs(history[0].v[12]-stable)<.001f,"same logic tick cannot advance original transition history");
 motion60TestTick(0,24,1024);renderSample(2);
 require(std::abs(history[0].v[12]-stable)<.001f,"third presentation still uses tick input history");
 motion60TestTick(1,0,1033);renderSample(2);
 require(history[0].v[12]>stable,"next native logic tick advances transition exactly once");
 transitionHistory=false;*reinterpret_cast<MotionMatrix**>(object+0xf0)=nullptr;
 localDraw=true;motion60TestComplete(image,true);actorX=0;*cameraMatrix=identity(-20);
 motion60TestTick(0,0,2000);appliedCamera();renderSample(0);
 require(worldObserved==0,"local source branch initial matrix");
 localDraw=false;renderSample(0);localDraw=true;
 actorX=10;*cameraMatrix=identity(-40);motion60TestTick(1,0,2033);appliedCamera();renderSample(1);
 require(reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]==10,"local source branch restores local matrix not camera-converted matrix");
 localDraw=false;renderSample(1);require(std::abs(worldObserved+20)<.002f,"composed track does not consume local track");localDraw=true;
 motion60TestTick(0,16,2049);appliedCamera();renderSample(1);
 require(std::abs(worldObserved-10*16.f/33)<.002f,"local world midpoint independent of camera movement");
 require(reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]==10,"local matrix exact midpoint restore");
 localDraw=false;renderSample(1);require(std::abs(worldObserved+20+10*16.f/33)<.002f,"alternating spaces retain separate midpoints");localDraw=true;
 throwSeh=true;require(sehProbe(),"local branch SEH propagated");throwSeh=false;
 require(reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]==10,"local branch SEH exact restore");
 localDraw=false;
 require(motion60TestTimerPatch(image,false),"complete timer rollback");require(!memcmp(image+0xcf61,timerBytes,6),"complete timer exact rollback");
 image[0xcf61]^=1;require(!motion60TestTimerPatch(image,true),"unknown timer rejects");image[0xcf61]^=1;
 require(motion60TestDriverSet(driverImage,false),"camera rollback");require(*loadSlot==oldLoad&&*mulSlot==oldMul,"camera exact slots restored");require(motion60TestDriverSet(driverImage,false),"camera rollback idempotent");
 *mulSlot=1;require(!motion60TestDriverSet(driverImage,true)&&*loadSlot==oldLoad,"unknown driver slot rejects before writes");*mulSlot=oldMul;
 VirtualFree(driverImage,0,MEM_RELEASE);
 motion60TestComplete(image,false);fullDraw=false;VirtualFree(image,0,MEM_RELEASE);
 printf("MOTION60_FIXTURE PASS checks=%d real_hook_calls=true intermediate_pose=true restore=exact logic_ticks=unchanged commercial_code_executed=false game_started=false\n",checks);return 0;
}
