#include "motion60.h"
#include "camera_input_view.h"
#include <cstring>
#include <cstdio>
#include <cmath>
#include "render_timeline.h"
#include "motion_diagnostics.h"
#include <string>
static std::wstring diagnosticLine;
static unsigned diagnosticLines=0;
void diagnosticLogger(const wchar_t* text){if(wcsstr(text,L"MOTION60_DIAG ")==text){diagnosticLine=text;++diagnosticLines;}}
static BYTE object[0x120],action[0x24],record[8],data[0x24];static BYTE* sequence[1];static MotionMatrix pose[2];static float observed;static int checks=0;static int absoluteCalls=0;static bool throwSeh=false;
static void* absoluteBones=nullptr;static float localPoseOffset=0;
static bool transitionHistory=false;static MotionMatrix history[1];
static bool stretchDraw=false,mirrorDraw=false,affineDraw=false;static float observedScale=1;
static bool fullDraw=false,localDraw=false;static BYTE driver[0xe0],camera[0xc0];static float actorX=0,worldObserved=0;
void require(bool b,const char* text){++checks;if(!b){fprintf(stderr,"FAIL %s\n",text);fflush(stderr);ExitProcess(1);}}
MotionMatrix identity(float x){MotionMatrix m{};m.v[0]=m.v[5]=m.v[10]=m.v[15]=1;m.v[12]=x;return m;}
void __cdecl absolute(void*,unsigned,MotionMatrix* p,MotionMatrix*){++absoluteCalls;p[0].v[12]+=100;}
void __fastcall loadCamera(void* d,void*,MotionMatrix* m){memcpy(static_cast<BYTE*>(d)+0x5c,m,64);}
void __fastcall draw(void*,void*,int frame,MotionMatrix*,int,int,int,int,int){
 pose[0]=identity(static_cast<float>(frame*10)+localPoseOffset);pose[1]=identity(3);
 if(stretchDraw)pose[0].v[0]=pose[0].v[5]=pose[0].v[10]=1.008f;
 if(mirrorDraw)pose[0].v[0]=-1;
 if(affineDraw){pose[0].v[0]=2;pose[0].v[5]=.5f;pose[0].v[4]=.25f;}
 if(transitionHistory){pose[0].v[12]=(history[0].v[12]+pose[0].v[12])*.5f;history[0]=pose[0];}
 if(fullDraw){auto actor=identity(actorX);auto view=reinterpret_cast<motion::Matrix*>(driver+0x5c);auto w=localDraw?reinterpret_cast<const motion::Matrix&>(actor):motion::multiply(*view,reinterpret_cast<const motion::Matrix&>(actor));memcpy(object+0xc,&w,64);}
 motion60TestAbsolute(absoluteBones?absoluteBones:data,0,pose,nullptr);observed=pose[0].v[12];observedScale=pose[0].v[0];worldObserved=reinterpret_cast<MotionMatrix*>(object+0xc)->v[12];if(throwSeh)RaiseException(0xe0000001,0,0,nullptr);
}
void renderSample(int frame){if(fullDraw&&!localDraw)motion60TestRenderParent(object,frame,reinterpret_cast<MotionMatrix*>(driver+0x5c));else motion60TestRender(object,frame);}
bool sehProbe(){__try {renderSample(2);}__except(EXCEPTION_EXECUTE_HANDLER){return true;}return false;}
int main(int argc,char** argv){
 const bool renderHistoryOnly=argc==2&&!strcmp(argv[1],"--render-history-only");
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
 localPoseOffset=2;renderSample(0);require(observed==102,"legacy clock same-frame pose mutation still resets");localPoseOffset=0;
 renderSample(0);require(observed==100,"legacy reset returns exact native pose");
 renderSample(1);require(observed<101,"next tick begins previous pose");require(pose[0].v[12]==110,"next baseline restored");
 motion60TestSetTime(17);renderSample(1);require(observed>102&&observed<109,"deterministic half step pose drawn");require(pose[0].v[12]==110,"halfstep cannot contaminate next logic");
 motion60TestSetTime(57);renderSample(1);require(observed==110,"latest pose reached");
 throwSeh=true;require(sehProbe(),"SEH propagated");throwSeh=false;require(pose[0].v[12]==120,"SEH exact absolute restore");
 renderSample(9);require(observed==190,"discontinuous frame resets");
 motion60TestSetTime(327);renderSample(10);require(observed==200,"pause resets");
 *reinterpret_cast<unsigned*>(data+0x14)=513;int before=absoluteCalls;renderSample(11);require(absoluteCalls==before+1,"invalid count original only");require(observed==210,"invalid count untouched");
 auto a=identity(0),b=identity(10);MotionMatrix out{};motion60TestBlend(a,b,.5f,out);require(std::abs(out.v[12]-5)<.001f,"translation interpolates");b.v[0]=-1;b.v[5]=-1;motion60TestBlend(a,b,.5f,out);require(std::abs(out.v[0])<.001f&&std::abs(out.v[1])>.99f,"rotation nlerp intermediate");
 b=identity(10);b.v[0]=2;motion60TestBlend(a,b,.5f,out);require(std::abs(out.v[0]-1.5f)<1e-5f&&out.v[12]==5,"nonuniform bone scale interpolates");
 *reinterpret_cast<unsigned*>(data+0x14)=1;
 stretchDraw=true;motion60TestSetTime(1000);renderSample(0);motion60TestSetTime(1033);renderSample(1);motion60TestSetTime(1049);renderSample(1);
 require(std::abs(observedScale-1.008f)<1e-5f,"real bone absolute hook retains native stretch at display midpoint");
 require(pose[0].v[0]==1.008f,"native stretched pose restored exactly after render");stretchDraw=false;
 mirrorDraw=true;motion60TestSetTime(2000);renderSample(0);motion60TestSetTime(2033);renderSample(1);motion60TestSetTime(2049);renderSample(1);
 require(observed>102&&observed<109,"real reflected bone hook must interpolate rather than present latest30Hz pose");
 require(pose[0].v[0]==-1&&pose[0].v[12]==110,"mirrored bone native absolute pose restored exactly");mirrorDraw=false;
 affineDraw=true;motion60TestSetTime(3000);renderSample(0);motion60TestSetTime(3033);renderSample(1);motion60TestSetTime(3049);renderSample(1);
 require(observed>102&&observed<109&&std::abs(observedScale-2)<1e-5f,"real scaled sheared bone hook draws continuous midpoint without losing native scale");
 require(pose[0].v[0]==2&&pose[0].v[5]==.5f&&pose[0].v[4]==.25f&&pose[0].v[12]==110,"scaled sheared absolute pose restored exactly");affineDraw=false;
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image!=nullptr,"complete image");motion60TestInitialize(image,&absolute);
 BYTE timerBytes[]={0x8b,0x55,0xf8,0x8b,0x45,0xec};memcpy(image+0xcf61,timerBytes,6);
 // Owned executable wrapper establishes the same locals as the guarded timer site.
 BYTE enter[]={0x55,0x8b,0xec,0x83,0xec,0x14};memcpy(image+0xcf20,enter,6);BYTE* code=image+0xcf26;
 for(int i=0;i<4;++i){BYTE op[]={0x8b,0x45,static_cast<BYTE>(8+i*4),0x89,0x45,0};op[5]=static_cast<BYTE>(i==0?-0x14:i==1?-8:i==2?-4:-0x10);memcpy(code,op,6);code+=6;}
 memset(code,0x90,(image+0xcf61)-code);BYTE leave[]={0x8b,0xe5,0x5d,0xc3};memcpy(image+0xcf67,leave,4);
 motion60TestComplete(image,true);require(motion60TestTimerPatch(image,true),"install source-guarded timer site");require(motion60TestTimerPatch(image,true),"timer idempotent");
 auto tick=reinterpret_cast<void(__cdecl*)(BYTE*,BYTE*,unsigned,unsigned)>(image+0xcf20);
 BYTE info[0x24]{};*reinterpret_cast<unsigned*>(info+8)=33;*reinterpret_cast<unsigned*>(info+4)=1;auto manager=image+0xf2250;
 motion60TestDiagnosticLogger(&diagnosticLogger);
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
 float inputView[16]{};auto cameraIdentity=reinterpret_cast<uintptr_t>(*reinterpret_cast<void**>(image+0xf2290));
 require(render_input::inputView.read(cameraIdentity,GetTickCount(),inputView),"real camera hook publishes movement view while orbit active");
 require(std::abs(inputView[0]-reinterpret_cast<MotionMatrix*>(driver+0x5c)->v[0])<.00001f,"published input view equals actually submitted driver view");
 renderSample(1);require(reinterpret_cast<MotionMatrix*>(object+0xc)->v[0]==1&&std::abs(reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]+10)<.002f,"free orbit draw restores original modelview not modified camera view");
 motion60TestFreeView(true,false,true,0,0);appliedCamera();require(reinterpret_cast<MotionMatrix*>(driver+0x5c)->v[0]==1,"free orbit reset restores original view orientation");
 require(!render_input::inputView.read(cameraIdentity,GetTickCount(),inputView),"orbit reset removes input override immediately");
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
 motion60TestComplete(image,true);actorX=12;*cameraMatrix=identity(-20);
 cameraMatrix->v[0]=cameraMatrix->v[5]=cameraMatrix->v[10]=1.008f;
 auto nativeScaledView=*cameraMatrix;float nativeScaledX=-20+12*1.008f;
 motion60TestTick(0,0,1900);appliedCamera();renderSample(0);
 require(std::abs(worldObserved-nativeScaledX)<.0001f,"real camera hook near-rigid first frame preserves native modelview");
 motion60TestTick(0,16,1916);appliedCamera();renderSample(0);
 require(std::abs(worldObserved-nativeScaledX)<.0001f,"stationary actor cannot drift under repeated near-rigid camera draws");
 require(!memcmp(cameraMatrix,&nativeScaledView,sizeof(nativeScaledView)),"native near-rigid camera restored byte exact");
 require(std::abs(reinterpret_cast<MotionMatrix*>(object+0xc)->v[12]-nativeScaledX)<.0001f,"near-rigid modelview restored without transpose scaling error");
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
 fullDraw=false;motion60TestComplete(image,true);
 *reinterpret_cast<unsigned*>(action+4)=4;*reinterpret_cast<unsigned*>(action+8)=4;
 motion60TestTick(0,0,3000);renderSample(3);require(observed==130,"loop baseline last pose");
 motion60TestTick(1,0,3033);renderSample(0);
 require(observed==130,"native loop wrap begins at previous last pose, not first-frame snap");
 require(pose[0].v[12]==100,"loop first native pose restored exactly");
 motion60TestTick(0,16,3049);renderSample(0);
 require(std::abs(observed-(130-30*16.f/33))<.002f,"loop wrap has a genuine intermediate pose");
 require(pose[0].v[12]==100,"loop intermediate rendering never changes native first pose");
 motion60TestTick(1,0,3066);renderSample(1);require(observed==100,"next loop tick follows the same one-tick latency");
 motion60TestTick(1,0,3099);renderSample(3);
 require(observed==130,"skipped loop frames reset rather than interpolate stale pose");
 motion60TestTick(1,0,3132);renderSample(2);
 require(observed==120,"reverse loop frame resets render history");
 *reinterpret_cast<unsigned*>(action+4)=3;
 motion60TestTick(1,0,3165);renderSample(0);
 require(observed==100,"same action with changed length resets even at apparent wrap");
 stretchDraw=true;renderSample(0);stretchDraw=false;
 *reinterpret_cast<unsigned*>(manager+0x24)=1049;tick(manager,info,0,16);
 require(diagnosticLines==1,"real timer hook emits one bounded diagnostic window");
 require(diagnosticLine.find(L"midpoints=0 ")==std::wstring::npos&&diagnosticLine.find(L"near_stretch=0 ")==std::wstring::npos,"real bone hook contributes midpoint and native stretch evidence");
 BYTE fieldJob[16]{};*reinterpret_cast<ULONG_PTR*>(fieldJob)=reinterpret_cast<ULONG_PTR>(image+0xc0f20);
 *reinterpret_cast<ULONG_PTR*>(info+4)=reinterpret_cast<ULONG_PTR>(fieldJob);*reinterpret_cast<unsigned*>(manager+0x24)=2049;tick(manager,info,0,16);
 require(diagnosticLines==2&&diagnosticLine.find(L"owner_switches=1 ")!=std::wstring::npos,"real timer hook records owner switch without hiding generation reset");
 require(diagnosticLine.find(L"job_vtable_rva=c0f20")!=std::wstring::npos,"source-bound field job classification logs relative vtable only");
 motion::Diagnostics aggregate;motion::DiagnosticWindow window;
 aggregate.clock(1,1,false,true,0xfffffff0,0xc0f20);aggregate.draw(.5f,false,false,false,false,false);aggregate.bone(true,true);
 require(!aggregate.take(983,window),"diagnostic cadence survives unsigned clock wrap");
 require(aggregate.take(984,window)&&window.draws==1&&window.midpoints==1&&window.nearStretch==1,"diagnostic window retains preceding draw counts across clock wrap");
 for(unsigned n=1;n<120;++n){aggregate.clock(1,0,false,true,985+1000*n,0xc0f20);require(aggregate.take(985+1000*n,window),"diagnostics bounded report before cap");}
 aggregate.clock(2,1,true,false,121985,0);require(!aggregate.take(121985,window),"diagnostics stop after 120 reports");
 aggregate.reset();aggregate.clock(1,0,false,true,0,0);require(aggregate.take(1000,window)&&window.draws==0&&window.owners==0,"diagnostic reset clears evidence and budget");
 motion60TestDiagnosticLogger(nullptr);
 require(motion60TestTimerPatch(image,false)&&motion60TestTimerPatch(image,true),"history capacity fixture starts clean guarded timer generation");
 static BYTE historyObjects[129][0x100];static MotionMatrix historyInputs[129];
 motion60TestTick(0,0,4000);
 for(unsigned n=0;n<128;++n){
  *reinterpret_cast<BYTE**>(historyObjects[n]+0xa0)=action;*reinterpret_cast<MotionMatrix**>(historyObjects[n]+0xf0)=&historyInputs[n];
  historyInputs[n]=identity(float(n));motion60TestPrepareHistory(historyObjects[n],0);
 }
 historyInputs[127]=identity(900);motion60TestPrepareHistory(historyObjects[127],0);
 require(historyInputs[127].v[12]==127,"history capacity retains live same-tick transition input");
 *reinterpret_cast<BYTE**>(historyObjects[128]+0xa0)=action;*reinterpret_cast<MotionMatrix**>(historyObjects[128]+0xf0)=&historyInputs[128];
 historyInputs[128]=identity(800);motion60TestPrepareHistory(historyObjects[128],0);
 historyInputs[128]=identity(900);motion60TestPrepareHistory(historyObjects[128],0);
 require(historyInputs[128].v[12]==900,"all-live same-tick capacity falls back without stealing another actor input");
 historyInputs[127]=identity(999);motion60TestPrepareHistory(historyObjects[127],0);
 require(historyInputs[127].v[12]==127,"capacity pressure cannot evict current-tick replay history");
 motion60TestTick(1,0,4033);*reinterpret_cast<BYTE**>(historyObjects[128]+0xa0)=action;
 *reinterpret_cast<MotionMatrix**>(historyObjects[128]+0xf0)=&historyInputs[128];historyInputs[128]=identity(800);
 motion60TestPrepareHistory(historyObjects[128],0);historyInputs[128]=identity(900);motion60TestPrepareHistory(historyObjects[128],0);
 require(historyInputs[128].v[12]==800,"expired history capacity must admit new actor and replay same-tick transition input");
 for(unsigned n=0;n<127;++n)motion60TestPrepareHistory(historyObjects[n],0);
 motion60TestTick(0,0,5000);historyInputs[127]=identity(700);motion60TestPrepareHistory(historyObjects[127],0);
 historyInputs[127]=identity(999);motion60TestPrepareHistory(historyObjects[127],0);
 require(historyInputs[127].v[12]==700,"new clock generation reclaims old scene histories without replaying old poses");
 if(!renderHistoryOnly){
 BYTE keyedObject[0x100]{},keyedAction[0x24]{},otherRecord[8]{},otherData[0x18]{};BYTE* keyedSequence[]={record};auto keyedInput=identity(200);
 *reinterpret_cast<BYTE**>(keyedObject+0xa0)=keyedAction;*reinterpret_cast<MotionMatrix**>(keyedObject+0xf0)=&keyedInput;
 *reinterpret_cast<unsigned*>(keyedAction+4)=4;*reinterpret_cast<unsigned*>(keyedAction+8)=4;
 *reinterpret_cast<BYTE***>(keyedAction+0x18)=keyedSequence;motion60TestTick(0,0,6000);
 motion60TestPrepareHistory(keyedObject,0);keyedInput=identity(400);motion60TestPrepareHistory(keyedObject,1);
 require(keyedInput.v[12]==400,"same-tick changed native frame cannot replay another sample history input");
 keyedInput=identity(900);motion60TestPrepareHistory(keyedObject,1);require(keyedInput.v[12]==400,"new frame repeated draw retains its own history input");
 *reinterpret_cast<BYTE**>(otherRecord+4)=otherData;*reinterpret_cast<unsigned*>(otherData+0x14)=1;keyedSequence[0]=otherRecord;
 keyedInput=identity(600);motion60TestPrepareHistory(keyedObject,1);require(keyedInput.v[12]==600,"same-count changed source resource recaptures history input");
 *reinterpret_cast<unsigned*>(keyedAction+4)=8;keyedInput=identity(700);motion60TestPrepareHistory(keyedObject,1);
 require(keyedInput.v[12]==700,"same action address changed clip length recaptures history input");
 *reinterpret_cast<unsigned*>(keyedAction+8)=2;keyedInput=identity(800);motion60TestPrepareHistory(keyedObject,1);
 require(keyedInput.v[12]==800,"same sample with changed source stride recaptures history input");
 *reinterpret_cast<unsigned*>(keyedObject+0xf4)=1;keyedInput=identity(850);motion60TestPrepareHistory(keyedObject,1);
 require(keyedInput.v[12]==850,"changed native transition counter recaptures history input");
 keyedInput=identity(999);motion60TestPrepareHistory(keyedObject,9);
 require(keyedInput.v[12]==850,"equivalent modulo-length native request replays same history input");
 }
 *reinterpret_cast<unsigned*>(action+4)=4;*reinterpret_cast<unsigned*>(action+8)=4;
 *reinterpret_cast<MotionMatrix**>(object+0xf0)=history;*reinterpret_cast<unsigned*>(object+0xf4)=1;
 history[0]=identity(0);transitionHistory=true;motion60TestComplete(image,true);motion60TestTick(0,0,7000);
 renderSample(2);require(history[0].v[12]==10,"source-shaped transition draw records first native result");
 renderSample(3);require(history[0].v[12]==20,"real render hook frame change uses current native transition history not prior sample input");
 renderSample(3);require(history[0].v[12]==20,"real render hook repeated changed-frame draw cannot accumulate transition again");
 transitionHistory=false;*reinterpret_cast<MotionMatrix**>(object+0xf0)=nullptr;*reinterpret_cast<unsigned*>(object+0xf4)=0;
 *reinterpret_cast<MotionMatrix**>(object+0xf0)=history;*reinterpret_cast<unsigned*>(object+0xf4)=2;
 history[0]=identity(0);transitionHistory=true;motion60TestComplete(image,true);motion60TestTick(0,0,7500);
 renderSample(2);require(observed==110&&pose[0].v[12]==110,"held-frame transition first native pose");
 *reinterpret_cast<unsigned*>(object+0xf4)=1;motion60TestTick(1,0,7533);renderSample(2);
 require(observed==110,"new logic tick held animation frame must retain previous transition pose instead of snap");
 require(pose[0].v[12]==115,"held-frame transition native output restored exactly");
 motion60TestTick(0,16,7549);renderSample(2);
 require(std::abs(observed-(110+5*16.f/33))<.002f,"held frame transition has intermediate pose on shared engine phase");
 require(pose[0].v[12]==115&&history[0].v[12]==15,"repeated held-frame render preserves original native transition result");
 renderSample(2);require(std::abs(observed-(110+5*16.f/33))<.002f&&history[0].v[12]==15,"held-frame midpoint is repeatable without accumulating native blend");
 motion60TestTick(1,0,7566);renderSample(2);require(observed==115&&pose[0].v[12]==117.5f,"second held-frame logic update retains prior native transition output");
 motion60TestTick(0,16,7582);renderSample(2);require(std::abs(observed-(115+2.5f*16.f/33))<.002f,"successive held-frame updates remain interpolated");
 localPoseOffset=6;renderSample(2);require(observed==120.5f,"unexpected same-tick held-frame pose mutation still resets");localPoseOffset=0;
 transitionHistory=false;*reinterpret_cast<MotionMatrix**>(object+0xf0)=nullptr;*reinterpret_cast<unsigned*>(object+0xf4)=0;
 BYTE switchAction[0x24]{},switchRecord[8]{},switchData[0x24]{},switchBones[12]{};BYTE* switchSequence[]={switchRecord};
 *reinterpret_cast<unsigned*>(switchAction+4)=4;*reinterpret_cast<unsigned*>(switchAction+8)=4;
 *reinterpret_cast<BYTE***>(switchAction+0x18)=switchSequence;*reinterpret_cast<BYTE**>(switchRecord+4)=switchData;*reinterpret_cast<unsigned*>(switchData+0x14)=1;
 motion60TestComplete(image,true);motion60TestTick(0,0,8000);renderSample(3);require(observed==130,"compatible action switch baseline last pose");
 *reinterpret_cast<BYTE**>(object+0xa0)=switchAction;absoluteBones=switchBones;
 motion60TestTick(1,0,8033);renderSample(0);
 require(observed==130,"compatible native action switch begins at previous local pose instead of resource snap");
 require(pose[0].v[12]==100,"new action native absolute output restores exactly");
 motion60TestTick(0,16,8049);renderSample(0);require(std::abs(observed-(130-30*16.f/33))<.002f,"compatible action switch has real intermediate pose");
 require(pose[0].v[12]==100,"compatible switch repeated render does not contaminate native pose");
 *reinterpret_cast<BYTE**>(object+0xa0)=action;absoluteBones=nullptr;
 motion60TestTick(1,0,8066);renderSample(1);require(observed==100,"same topology switch back retains one-tick display continuity");
 *reinterpret_cast<BYTE**>(object+8)=switchData;*reinterpret_cast<BYTE**>(object+0xa0)=switchAction;absoluteBones=switchBones;
 motion60TestTick(1,0,8099);renderSample(2);require(observed==120,"changed model identity rejects cross-action interpolation");
 *reinterpret_cast<BYTE**>(object+8)=nullptr;*reinterpret_cast<BYTE**>(object+0xa0)=action;absoluteBones=nullptr;
 BYTE bonesA[24]{},bonesB[24]{};unsigned childA=1,childB=1;
 *reinterpret_cast<unsigned*>(bonesA+4)=*reinterpret_cast<unsigned*>(bonesB+4)=1;
 *reinterpret_cast<unsigned**>(bonesA+8)=&childA;*reinterpret_cast<unsigned**>(bonesB+8)=&childB;
 *reinterpret_cast<unsigned*>(data+0x14)=*reinterpret_cast<unsigned*>(switchData+0x14)=2;
 motion60TestComplete(image,true);absoluteBones=bonesA;motion60TestTick(0,0,9000);renderSample(3);
 *reinterpret_cast<BYTE**>(object+0xa0)=switchAction;absoluteBones=bonesB;motion60TestTick(1,0,9033);renderSample(0);
 require(observed==130,"equivalent two-bone child arrays bridge despite different source addresses");
 require(pose[1].v[12]==3&&pose[1].v[15]==1,"all native local bones restored after compatible switch");
 *reinterpret_cast<unsigned*>(bonesB+4)=0;motion60TestTick(1,0,9066);renderSample(1);
 require(observed==110,"in-place hierarchy mutation resets even without changed pointer");
 *reinterpret_cast<unsigned*>(bonesB+4)=1;childB=2;motion60TestTick(1,0,9099);renderSample(2);
 require(observed==120,"out-of-range child rejects compatibility without reading another bone");
 childB=0;motion60TestTick(1,0,9132);renderSample(3);require(observed==130,"cyclic root hierarchy cannot bridge");
 childB=1;*reinterpret_cast<BYTE**>(object+0xa0)=action;absoluteBones=bonesA;motion60TestTick(0,0,9200);renderSample(3);
 *reinterpret_cast<BYTE**>(object+0xa0)=switchAction;absoluteBones=bonesB;motion60TestTick(0,16,9216);renderSample(0);
 require(observed==100,"same-tick action mutation does not bridge unrelated render history");
 *reinterpret_cast<BYTE**>(object+0xa0)=action;absoluteBones=bonesA;motion60TestComplete(image,true);motion60TestTick(0,0,9300);renderSample(3);
 *reinterpret_cast<BYTE**>(object+0xa0)=switchAction;absoluteBones=bonesB;motion60TestTick(2,0,9366);renderSample(0);
 require(observed==100,"catchup action switch resets rather than inventing missing updates");
 *reinterpret_cast<BYTE**>(object+0xa0)=action;absoluteBones=nullptr;*reinterpret_cast<unsigned*>(data+0x14)=1;
 motion::Diagnostics compatibleEvidence;compatibleEvidence.clock(1,1,false,true,0,0);
 compatibleEvidence.draw(.5f,false,false,false,false,false,true);motion::DiagnosticWindow compatibleWindow;
 require(compatibleEvidence.take(1000,compatibleWindow)&&compatibleWindow.compatibleSwitches==1&&compatibleWindow.resets==0,"bounded diagnostics separate compatible bridges from resource resets");
 require(motion60TestTimerPatch(image,false),"complete timer rollback");require(!memcmp(image+0xcf61,timerBytes,6),"complete timer exact rollback");
 image[0xcf61]^=1;require(!motion60TestTimerPatch(image,true),"unknown timer rejects");image[0xcf61]^=1;
 require(motion60TestDriverSet(driverImage,false),"camera rollback");require(*loadSlot==oldLoad&&*mulSlot==oldMul,"camera exact slots restored");require(motion60TestDriverSet(driverImage,false),"camera rollback idempotent");
 *mulSlot=1;require(!motion60TestDriverSet(driverImage,true)&&*loadSlot==oldLoad,"unknown driver slot rejects before writes");*mulSlot=oldMul;
 VirtualFree(driverImage,0,MEM_RELEASE);
 motion60TestComplete(image,false);fullDraw=false;VirtualFree(image,0,MEM_RELEASE);
 printf("MOTION60_FIXTURE PASS checks=%d real_hook_calls=true intermediate_pose=true restore=exact logic_ticks=unchanged commercial_code_executed=false game_started=false\n",checks);return 0;
}
