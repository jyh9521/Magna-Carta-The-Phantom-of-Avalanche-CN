#include "free_view.h"
#include "camera_input_view.h"
#include "motion60.h"
#include "render_timeline.h"
#include "motion_diagnostics.h"
#include <cwchar>
#include <intrin.h>
#include <array>
#include <vector>
#include <map>
#include <cmath>
#include <algorithm>
#include <cstring>
namespace {
using Matrix=motion::Matrix;
using motion::blend;
using Render=void(__thiscall*)(void*,int,Matrix*,int,int,int,int,int);
using Absolute=void(__cdecl*)(void*,unsigned,Matrix*,Matrix*);
Render originalRender=nullptr;Absolute originalAbsolute=nullptr;BYTE* engineBase=nullptr;
void(*trace)(const wchar_t*)=nullptr;
bool complete=false;
bool readable(const void*,size_t);
DWORD timelineThread=0;
motion::Timeline timeline;
motion::Diagnostics diagnostics;
using LoadMatrix=void(__thiscall*)(void*,Matrix*);
LoadMatrix originalLoad=nullptr,originalMultiply=nullptr;
BYTE* driverBase=nullptr;
motion::TransformTrack cameraTrack;
camera::Orbit freeOrbit;bool freeView=false;DWORD freeTimestamp=0;uint64_t freeGeneration=0;
#ifdef MOTION60_TEST
bool freeFixture=false;camera::Input freeFixtureInput{};
#endif
struct CameraState {void* identity=nullptr;Matrix original{},applied{};bool valid=false;};
thread_local CameraState cameraState;
ULONG_PTR timerResume=0;
constexpr BYTE timerOriginal[]={0x8b,0x55,0xf8,0x8b,0x45,0xec};
void __cdecl captureTimer(BYTE* manager,BYTE* info,unsigned consumed,unsigned elapsed){
 if(manager!=engineBase+0xf2250||!readable(info,0x24)||*reinterpret_cast<unsigned*>(info+8)!=33)return;
 timelineThread=GetCurrentThreadId();
 auto before=timeline.phase();auto owner=*reinterpret_cast<ULONG_PTR*>(info+4);
 timeline.observe(*reinterpret_cast<ULONG_PTR*>(info+4),33,*reinterpret_cast<unsigned*>(info+0x10),consumed,
                  *reinterpret_cast<unsigned*>(manager+0x24),*reinterpret_cast<int*>(info+0x1c)==0&&elapsed<=250);
 if(trace&&diagnostics.enabled()){
  unsigned jobRva=0;if(readable(reinterpret_cast<void*>(owner),4)){
   auto vtable=*reinterpret_cast<ULONG_PTR*>(owner);auto base=reinterpret_cast<ULONG_PTR>(engineBase);
   if(vtable>=base&&vtable-base<0x10b000)jobRva=static_cast<unsigned>(vtable-base);
  }
  auto now=*reinterpret_cast<unsigned*>(manager+0x24);auto after=timeline.phase();
  diagnostics.clock(owner,consumed,before.generation!=after.generation,after.valid,now,jobRva);
  motion::DiagnosticWindow s;if(diagnostics.take(now,s)){
   wchar_t line[768];swprintf_s(line,L"MOTION60_DIAG clocks=%llu updates=%llu owner_switches=%llu generation_changes=%llu invalid=%llu draws=%llu midpoints=%llu resets=%llu resource=%llu phase=%llu same_frame=%llu jumps=%llu bones=%llu unsupported=%llu near_stretch=%llu job_vtable_rva=%x",
    s.clocks,s.updates,s.owners,s.generations,s.invalid,s.draws,s.midpoints,s.resets,s.resource,s.phase,s.sameFrame,s.jumps,s.bones,s.unsupported,s.nearStretch,s.jobVtableRva);trace(line);
  }
 }
 cameraState.valid=false;
 if(!timeline.phase().valid||timeline.phase().generation!=freeGeneration)render_input::inputView.reset();
 static LONG captured=0;if(timeline.phase().valid&&InterlockedIncrement(&captured)==1&&trace)trace(L"MOTION60_CLOCK_APPLIED interval_ms=33 phase=callback_remainder controller=source_locked");
}
__declspec(naked) void timerThunk(){__asm {
 pushfd
 pushad
 push dword ptr[ebp-10h]
 push dword ptr[ebp-4]
 push dword ptr[ebp-8]
 push dword ptr[ebp-14h]
 call captureTimer
 add esp,16
 popad
 popfd
 mov edx,dword ptr[ebp-8]
 mov eax,dword ptr[ebp-14h]
 jmp dword ptr[timerResume]
}}
struct Cache{void* action=nullptr;void* bones=nullptr;Matrix* pose=nullptr;unsigned clipLength=0;int frame=0;LONGLONG changed=0,last=0;motion::Phase phase{};motion::TransformTrack world,localWorld;std::vector<Matrix> previous,current;};
std::map<void*,Cache> caches;SRWLOCK cacheLock=SRWLOCK_INIT;LONGLONG frequency=0;
// The original renderer copies local pose into object+f0 on every draw.
// Replaying the same fixed tick must start with the same transition history.
struct History {void* action=nullptr;Matrix* buffer=nullptr;motion::Phase phase{};std::vector<Matrix> input;};
std::map<void*,History> histories;
motion::Phase renderPhase();
void prepareHistory(void* value,int frame){
 auto phase=renderPhase();
 if(!complete||!phase.valid||!readable(value,0x100))return;
 auto object=static_cast<BYTE*>(value);auto action=*reinterpret_cast<BYTE**>(object+0xa0);
 auto buffer=*reinterpret_cast<Matrix**>(object+0xf0);
 if(!buffer||!readable(action,0x20))return;
 unsigned length=*reinterpret_cast<unsigned*>(action+4),stride=*reinterpret_cast<unsigned*>(action+8);
 if(!length||!stride||frame<0)return;unsigned sample=(unsigned(frame)%length)/stride;
 auto sequence=*reinterpret_cast<BYTE**>(action+0x18);
 if(sample>65535||!readable(sequence,(sample+1)*sizeof(void*)))return;
 auto record=*reinterpret_cast<BYTE**>(sequence+sample*sizeof(void*));
 if(!readable(record,8))return;auto data=*reinterpret_cast<BYTE**>(record+4);
 if(!readable(data,0x18))return;unsigned count=*reinterpret_cast<unsigned*>(data+0x14);
 if(!count||count>512||!readable(buffer,count*sizeof(Matrix)))return;
 if(histories.find(value)==histories.end()&&histories.size()>=128){
  // Only same-tick input is replayable. Prior-tick/scene records are obsolete,
  // not permanently reserved capacity for actors that are no longer visible.
  for(auto i=histories.begin();i!=histories.end();){
   if(i->second.phase.generation!=phase.generation||i->second.phase.tick!=phase.tick)i=histories.erase(i);
   else ++i;
  }
  if(histories.size()>=128)return; // Retain every still-live same-tick input.
 }
 auto& h=histories[value];
 bool repeat=h.action==action&&h.buffer==buffer&&h.input.size()==count
  &&h.phase.generation==phase.generation&&h.phase.tick==phase.tick;
 if(repeat)memcpy(buffer,h.input.data(),count*sizeof(Matrix));
 else {h.action=action;h.buffer=buffer;h.input.assign(buffer,buffer+count);h.phase=phase;}
}
#ifdef MOTION60_TEST
bool fixtureClock=false;LONGLONG fixtureTicks=0;
#endif
struct Context{void* object;int frame;Matrix* pose=nullptr;std::vector<Matrix> baseline;Context* parent;Matrix* world=nullptr;Matrix baselineWorld{};bool hasParent=false;};
thread_local Context* active=nullptr;volatile LONG changes=0;
motion::Phase renderPhase(){return timelineThread==GetCurrentThreadId()?timeline.phase():motion::Phase{};}
void cameraMatrix(void* driver,Matrix* matrix,LoadMatrix original){
 if(!complete||!engineBase||!readable(matrix,sizeof(Matrix))||!readable(driver,0x60)
    ||*reinterpret_cast<unsigned*>(static_cast<BYTE*>(driver)+0x58)!=0x1700){original(driver,matrix);return;}
 auto camera=*reinterpret_cast<BYTE**>(engineBase+0xf2290);
 if(!camera||matrix!=reinterpret_cast<Matrix*>(camera+0x80)){original(driver,matrix);return;}
 auto phase=renderPhase();if(!phase.valid){cameraTrack.reset();cameraState.valid=false;render_input::inputView.reset();original(driver,matrix);return;}
 if(cameraState.identity!=camera){cameraTrack.reset();cameraState.identity=camera;}
 cameraState.original=*matrix;cameraState.applied=cameraTrack.sample(*matrix,phase,true);
 if(freeView){
  if(freeGeneration!=phase.generation){freeOrbit.reset();freeGeneration=phase.generation;}
#ifdef MOTION60_TEST
  if(freeFixture){cameraState.applied=freeOrbit.sample(cameraState.applied,reinterpret_cast<uintptr_t>(camera),freeFixtureInput);}
  else
#endif
  {
  DWORD now=GetTickCount();float dt=freeTimestamp?float(now-freeTimestamp)/1000:0;freeTimestamp=now;
  DWORD foregroundPid=0;GetWindowThreadProcessId(GetForegroundWindow(),&foregroundPid);
  if(foregroundPid!=GetCurrentProcessId()){freeOrbit.reset();}
  else {
   auto key=[](int k){return (GetAsyncKeyState(k)&0x8000)!=0;};bool chord=key(VK_CONTROL)&&key(VK_MENU);
   camera::Input input{key(VK_F6),key(VK_F7),chord?float(key(VK_NUMPAD6))-float(key(VK_NUMPAD4)):0,
    chord?float(key(VK_NUMPAD8))-float(key(VK_NUMPAD2)):0,chord?float(key(VK_ADD))-float(key(VK_SUBTRACT)):0,dt};
   cameraState.applied=freeOrbit.sample(cameraState.applied,reinterpret_cast<uintptr_t>(camera),input);
  }
 }
 }
 cameraState.valid=motion::rigid(cameraState.original)&&motion::rigid(cameraState.applied);
 Matrix copy=cameraState.applied;original(driver,&copy);
 render_input::inputView.publish(cameraState.applied.v,reinterpret_cast<uintptr_t>(camera),GetTickCount(),cameraState.valid&&freeView&&freeOrbit.active());
 static LONG applied=0;if(cameraState.valid&&InterlockedIncrement(&applied)==1&&trace)trace(L"MOTION60_CAMERA_APPLIED phase=engine_remainder original_camera=unchanged");
}
void __fastcall loadHook(void* d,void*,Matrix* m){cameraMatrix(d,m,originalLoad);}
void __fastcall multiplyHook(void* d,void*,Matrix* m){cameraMatrix(d,m,originalMultiply);}
bool readable(const void* address,size_t length){
 if(!address||!length)return false;auto p=reinterpret_cast<ULONG_PTR>(address);if(p+length<p)return false;auto end=p+length;
 while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;
}
bool sourceCall(void* caller){
#ifdef MOTION60_TEST
(void)caller;return true;
#else
return reinterpret_cast<BYTE*>(caller)==engineBase+0x3b801;
#endif
}
void __cdecl absoluteHook(void* bones,unsigned root,Matrix* poses,Matrix* parent){
 auto phase=renderPhase();
 if(complete&&!phase.valid){originalAbsolute(bones,root,poses,parent);return;}
 if(!active||!sourceCall(_ReturnAddress())||root||parent||!readable(active->object,0x100)){originalAbsolute(bones,root,poses,parent);return;}
 BYTE* object=static_cast<BYTE*>(active->object);void* action=*reinterpret_cast<void**>(object+0xa0);
 if(!readable(action,0x20)||*reinterpret_cast<Matrix**>(object+0x8c)!=poses){originalAbsolute(bones,root,poses,parent);return;}
 // Current frame's resource record is the renderer's validated local [ebp-4].
 auto sequence=*reinterpret_cast<BYTE**>(static_cast<BYTE*>(action)+0x18);unsigned sample=*reinterpret_cast<unsigned*>(object+0xf8);
 if(sample>65535||!readable(sequence,(sample+1)*sizeof(void*))){originalAbsolute(bones,root,poses,parent);return;}
 auto record=*reinterpret_cast<BYTE**>(sequence+sample*sizeof(void*));
 if(!readable(record,8)){originalAbsolute(bones,root,poses,parent);return;}auto data=*reinterpret_cast<BYTE**>(record+4);
 if(!readable(data,0x20)){originalAbsolute(bones,root,poses,parent);return;}unsigned count=*reinterpret_cast<unsigned*>(data+0x14);
 if(!count||count>512||!readable(poses,count*sizeof(Matrix))){originalAbsolute(bones,root,poses,parent);return;}
 std::vector<Matrix> current(poses,poses+count),interpolated=current;LARGE_INTEGER now{};QueryPerformanceCounter(&now);
#ifdef MOTION60_TEST
 if(fixtureClock)now.QuadPart=fixtureTicks;
#endif
 struct Lock {bool held=true;Lock(){AcquireSRWLockExclusive(&cacheLock);}void release(){if(held){ReleaseSRWLockExclusive(&cacheLock);held=false;}}~Lock(){release();}} lock;
 if(caches.find(active->object)==caches.end()&&caches.size()>=128){
for(auto i=caches.begin();i!=caches.end();)if(now.QuadPart-i->second.last>frequency/4)i=caches.erase(i);else ++i;
if(caches.size()>=128){lock.release();originalAbsolute(bones,root,poses,parent);return;}
}
unsigned clipLength=*reinterpret_cast<unsigned*>(static_cast<BYTE*>(action)+4);
auto& c=caches[active->object];bool resourceReset=c.current.size()!=count||c.action!=action||c.bones!=bones||c.pose!=poses||c.clipLength!=clipLength||now.QuadPart-c.last>frequency/4;
 bool phaseReset=complete&&(c.phase.generation!=phase.generation||phase.tick<c.phase.tick||phase.tick>c.phase.tick+1);
 bool reset=resourceReset||phaseReset;
 bool sameFrameChange=!reset&&active->frame==c.frame&&memcmp(current.data(),c.current.data(),count*sizeof(Matrix));
 if(sameFrameChange)reset=true;
 // The native actor update wraps looping clips from length-1 to zero.
 // Preserve render history for that adjacent step, but not seeks or reversals.
 bool adjacent=static_cast<LONGLONG>(active->frame)==static_cast<LONGLONG>(c.frame)+1;
 bool wrapped=clipLength>1&&c.frame>=0&&static_cast<unsigned>(c.frame)==clipLength-1&&active->frame==0;
 bool frameJump=!reset&&active->frame!=c.frame&&!adjacent&&!wrapped;
 if(frameJump)reset=true;
 if(reset){c.previous=current;c.current=current;c.frame=active->frame;c.changed=now.QuadPart;c.action=action;c.bones=bones;c.pose=poses;c.clipLength=clipLength;c.world.reset();c.localWorld.reset();}
 else if(active->frame!=c.frame||(complete&&phase.tick!=c.phase.tick)){c.previous=c.current;c.current=current;c.frame=active->frame;c.changed=now.QuadPart;}
 c.last=now.QuadPart;float alpha=frequency?static_cast<float>((now.QuadPart-c.changed)*1000.0/(frequency*33.0)):1;alpha=(std::max)(0.f,(std::min)(1.f,alpha));
 if(complete){alpha=phase.alpha;c.phase=phase;}
 if(complete&&trace&&diagnostics.enabled()){
  diagnostics.draw(alpha,reset,resourceReset,phaseReset,sameFrameChange,frameJump);
  for(unsigned bone=0;bone<count;++bone){const auto& m=current[bone];bool stretch=false;
   for(int row=0;row<3;++row){float norm=0;for(int col=0;col<3;++col)norm+=m.v[row*4+col]*m.v[row*4+col];stretch=stretch||std::abs(norm-1)>.0005f;}
   diagnostics.bone(motion::rigid(m),stretch);
  }
 }
 for(unsigned i=0;i<count;++i)blend(c.previous[i],c.current[i],alpha,interpolated[i]);
 Matrix interpolatedWorld{};bool worldValid=false;
 auto world=reinterpret_cast<Matrix*>(object+0xc);
 if(complete&&!active->hasParent&&motion::rigid(*world)){
  // Original Render(NULL parent) copies local +4c into +c. No view matrix
  // exists in this value: camera removal would corrupt both draw and restore.
  interpolatedWorld=c.localWorld.sample(*world,phase);
  active->world=world;active->baselineWorld=*world;worldValid=true;
 }else if(complete&&cameraState.valid&&motion::rigid(*world)){
  // Asura matrices are column-major: modelview = view * actorWorld.
  auto actorWorld=motion::multiply(motion::inverseRigid(cameraState.applied),*world);
  if(motion::rigid(actorWorld)){
   interpolatedWorld=motion::multiply(cameraState.applied,c.world.sample(actorWorld,phase));
   active->world=world;active->baselineWorld=motion::multiply(cameraState.original,actorWorld);worldValid=true;
  }
 }
 if(caches.size()>128)for(auto i=caches.begin();i!=caches.end();)if(i->first!=active->object&&now.QuadPart-i->second.last>frequency/4)i=caches.erase(i);else ++i;
 lock.release();
 // Obtain the exact unmodified absolute output first; restore it after drawing.
 active->baseline.resize(count);originalAbsolute(bones,root,poses,parent);memcpy(active->baseline.data(),poses,count*sizeof(Matrix));active->pose=poses;
 memcpy(poses,interpolated.data(),count*sizeof(Matrix));originalAbsolute(bones,root,poses,parent);
 if(worldValid)*world=interpolatedWorld;
 static LONG localChanges=0,composedChanges=0;
 if(worldValid&&InterlockedIncrement(active->hasParent?&composedChanges:&localChanges)==1&&trace)
  trace(active->hasParent?L"MOTION60_WORLD_APPLIED source_space=view_composed parent=non_null restore=original_modelview":L"MOTION60_WORLD_APPLIED source_space=local parent=null camera_conversion=false restore=exact_local");
 if(InterlockedIncrement(&changes)==1&&trace)trace(complete?L"MOTION60_POSE_APPLIED phase=engine_remainder world_camera=interpolated latency_ticks=1":L"MOTION60_POSE_APPLIED scope=skeletal_local_pose logic_interval_ms=33 world_camera=unchanged latency_ticks=1");
}
void renderScoped(Context* ctx,void* object,int frame,Matrix* world,int a,int b,int c,int d,int e){
 __try {active=ctx;originalRender(object,frame,world,a,b,c,d,e);}
 __finally {if(ctx->pose&&!ctx->baseline.empty())memcpy(ctx->pose,ctx->baseline.data(),ctx->baseline.size()*sizeof(Matrix));if(ctx->world)*ctx->world=ctx->baselineWorld;active=ctx->parent;}
}
void __fastcall renderHook(void* object,void*,int frame,Matrix* world,int a,int b,int c,int d,int e){
 prepareHistory(object,frame);
 Context ctx{object,frame,nullptr,{},active};ctx.hasParent=world!=nullptr;renderScoped(&ctx,object,frame,world,a,b,c,d,e);
}
bool write(void* p,DWORD value){DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;DWORD before=*static_cast<DWORD*>(p);*static_cast<DWORD*>(p)=value;DWORD unused;if(VirtualProtect(p,4,old,&unused))return true;*static_cast<DWORD*>(p)=before;VirtualProtect(p,4,old,&unused);return false;}
bool timerMatches(BYTE* p){
 if(!readable(p+0xcf61,6))return false;
 BYTE patched[]={0xe9,0,0,0,0,0x90};*reinterpret_cast<int32_t*>(patched+1)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(&timerThunk)-reinterpret_cast<ULONG_PTR>(p+0xcf66));
 return !memcmp(p+0xcf61,timerOriginal,6)||!memcmp(p+0xcf61,patched,6);
}
bool timerPatch(BYTE* p,bool enabled){
 BYTE patched[]={0xe9,0,0,0,0,0x90};*reinterpret_cast<int32_t*>(patched+1)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(&timerThunk)-reinterpret_cast<ULONG_PTR>(p+0xcf66));
 if(memcmp(p+0xcf61,timerOriginal,6)&&memcmp(p+0xcf61,patched,6))return false;
 BYTE before[6];memcpy(before,p+0xcf61,6);DWORD old;if(!VirtualProtect(p+0xcf61,6,PAGE_EXECUTE_READWRITE,&old))return false;
 timerResume=reinterpret_cast<ULONG_PTR>(p+0xcf67);memcpy(p+0xcf61,enabled?patched:timerOriginal,6);
 bool ok=FlushInstructionCache(GetCurrentProcess(),p+0xcf61,6)!=FALSE;DWORD ignored;
 if(!ok||!VirtualProtect(p+0xcf61,6,old,&ignored)){memcpy(p+0xcf61,before,6);FlushInstructionCache(GetCurrentProcess(),p+0xcf61,6);VirtualProtect(p+0xcf61,6,old,&ignored);return false;}
 timeline.reset();diagnostics.reset();histories.clear();cameraTrack.reset();cameraState={};render_input::inputView.reset();return true;
}
}
namespace {
bool headerMatches(BYTE* p,size_t n){if(!readable(p,n)||n<0x10b000)return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096)return false;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&nt->OptionalHeader.SizeOfImage==0x10b000;}
bool mappedMatches(BYTE* p,size_t n,Absolute absolute){
 if(!headerMatches(p,n)||!absolute)return false;
 BYTE prefix[]={0x55,0x8b,0xec,0x81,0xec,0x04,0x03,0x00,0x00,0x56,0x57},call[]={0xff,0x15,0,0,0,0,0x83,0xc4,0x10};*reinterpret_cast<DWORD*>(call+2)=reinterpret_cast<DWORD>(p+0xbd0a4);
 if(memcmp(p+0x3b0c0,prefix,sizeof(prefix))||memcmp(p+0x3b7fb,call,sizeof(call)))return false;
 DWORD slot=*reinterpret_cast<DWORD*>(p+0xbd9f8),iat=*reinterpret_cast<DWORD*>(p+0xbd0a4);
 return (slot==reinterpret_cast<DWORD>(p+0x3b0c0)&&iat==reinterpret_cast<DWORD>(absolute))||
 (slot==reinterpret_cast<DWORD>(&renderHook)&&iat==reinterpret_cast<DWORD>(&absoluteHook)&&engineBase==p&&originalAbsolute==absolute);
}
bool setMapped(BYTE* p,size_t n,Absolute absolute,bool enabled,void(*logger)(const wchar_t*)){
 if(!headerMatches(p,n)||!absolute)return false;
 BYTE prefix[]={0x55,0x8b,0xec,0x81,0xec,0x04,0x03,0x00,0x00,0x56,0x57};BYTE call[]={0xff,0x15,0,0,0,0,0x83,0xc4,0x10};*reinterpret_cast<DWORD*>(call+2)=reinterpret_cast<DWORD>(p+0xbd0a4);
 if(memcmp(p+0x3b0c0,prefix,sizeof(prefix))||memcmp(p+0x3b7fb,call,sizeof(call)))return false;
 auto slot=reinterpret_cast<DWORD*>(p+0xbd9f8);auto iat=reinterpret_cast<DWORD*>(p+0xbd0a4);
 DWORD expectedRender=reinterpret_cast<DWORD>(p+0x3b0c0),expectedAbsolute=reinterpret_cast<DWORD>(absolute);
 DWORD renderPatched=reinterpret_cast<DWORD>(&renderHook),absolutePatched=reinterpret_cast<DWORD>(&absoluteHook);
 bool clean=*slot==expectedRender&&*iat==expectedAbsolute;
 bool patched=*slot==renderPatched&&*iat==absolutePatched&&engineBase==p&&originalAbsolute==absolute;
 if(!clean&&!patched)return false;
 if(enabled&&patched)return true;if(!enabled&&clean)return true;
 if(enabled){LARGE_INTEGER f{};if(!QueryPerformanceFrequency(&f))return false;frequency=f.QuadPart;engineBase=p;trace=logger;originalRender=reinterpret_cast<Render>(expectedRender);originalAbsolute=absolute;
 if(!write(iat,absolutePatched))return false;if(!write(slot,renderPatched)){write(iat,expectedAbsolute);return false;}
 if(trace)trace(L"MOTION60_READY skeletal_pose=source_locked logic_events=unchanged world_camera=unchanged");return true;}
 if(!write(slot,expectedRender))return false;if(!write(iat,expectedAbsolute)){write(slot,renderPatched);return false;}
 AcquireSRWLockExclusive(&cacheLock);caches.clear();ReleaseSRWLockExclusive(&cacheLock);return true;
}
}
bool installMotion60(HMODULE engine,void(*logger)(const wchar_t*)){
 HMODULE asura=GetModuleHandleW(L"Asura.dll");if(!asura)return false;auto p=reinterpret_cast<BYTE*>(asura);
 auto absolute=GetProcAddress(asura,"?MakeAbsoluteMatrix@@YAXPAUASRBone@@IPAVASRMatrix@@1@Z");BYTE prefix[]={0x55,0x8b,0xec,0x83,0xec,0x44,0x56,0x57};
 if(absolute!=reinterpret_cast<FARPROC>(p+0x44f0d)||!readable(p+0x44f0d,sizeof(prefix))||memcmp(p+0x44f0d,prefix,sizeof(prefix)))return false;
 auto base=reinterpret_cast<BYTE*>(engine);wchar_t flag[8]{};complete=GetEnvironmentVariableW(L"MC_MOTION60_COMPLETE",flag,8)==1&&flag[0]==L'1';
 if(!headerMatches(base,0x10b000)||(complete&&!timerMatches(base)))return false;
 if(!setMapped(base,0x10b000,reinterpret_cast<Absolute>(absolute),true,logger))return false;
 if(complete&&!timerPatch(base,true)){setMapped(base,0x10b000,reinterpret_cast<Absolute>(absolute),false,nullptr);return false;}
 if(complete&&logger)logger(L"MOTION60_COMPLETE_READY clock=engine_fixed_step world=source_locked camera=source_locked logic_events=unchanged");return true;
}
bool removeMotion60(HMODULE engine){
 if(engineBase!=reinterpret_cast<BYTE*>(engine))return false;
 if(!mappedMatches(engineBase,0x10b000,originalAbsolute)||(complete&&!timerMatches(engineBase)))return false;
 if(complete&&!timerPatch(engineBase,false))return false;
 return setMapped(engineBase,0x10b000,originalAbsolute,false,nullptr);
}
namespace {
bool setDriver(BYTE* p,bool enabled,void(*logger)(const wchar_t*)){
 if(!readable(p,0x2c000))return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x2c000)return false;
 BYTE loadPrefix[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xfc};
 BYTE multiplyPrefix[]={0x55,0x8b,0xec,0x81,0xec,0x48,0x02,0x00,0x00,0x56,0x57};
 if(memcmp(p+0x356a,loadPrefix,sizeof(loadPrefix))||memcmp(p+0x7036,multiplyPrefix,sizeof(multiplyPrefix)))return false;
 auto load=reinterpret_cast<DWORD*>(p+0x1a838),mul=reinterpret_cast<DWORD*>(p+0x1a878);
 DWORD originalA=reinterpret_cast<DWORD>(p+0x356a),originalB=reinterpret_cast<DWORD>(p+0x7036);
 DWORD hookA=reinterpret_cast<DWORD>(&loadHook),hookB=reinterpret_cast<DWORD>(&multiplyHook);
 bool patched=*load==hookA&&*mul==hookB&&driverBase==p,clean=*load==originalA&&*mul==originalB;
 if(!patched&&!clean)return false;
 if(enabled&&patched)return true;if(!enabled&&clean)return true;
 if(!enabled){if(!write(load,originalA))return false;if(!write(mul,originalB)){write(load,hookA);return false;}cameraTrack.reset();cameraState={};render_input::inputView.reset();return true;}
 originalLoad=reinterpret_cast<LoadMatrix>(originalA);originalMultiply=reinterpret_cast<LoadMatrix>(originalB);
 if(!write(load,hookA))return false;if(!write(mul,hookB)){write(load,originalA);return false;}
 driverBase=p;if(logger)logger(L"MOTION60_CAMERA_READY scope=active_camera_modelview load_multiply=guarded ui_projection=unchanged");return true;
}
}
bool installMotion60Driver(HMODULE module,void(*logger)(const wchar_t*)){
 wchar_t freeFlag[8]{};freeView=GetEnvironmentVariableW(L"MC_FREE_VIEW",freeFlag,8)==1&&freeFlag[0]==L'1';freeOrbit.reset();render_input::inputView.reset();freeTimestamp=0;freeGeneration=0;
 wchar_t flag[8]{};if(GetEnvironmentVariableW(L"MC_MOTION60_COMPLETE",flag,8)!=1||flag[0]!=L'1')return true;
 bool ready=setDriver(reinterpret_cast<BYTE*>(module),true,logger);if(ready&&freeView&&logger)logger(L"FREE_VIEW_READY mode=orbit render_only=true initial=off F6_toggle=enabled F7_reset=enabled");return ready;
}
bool removeMotion60Driver(HMODULE module){return setDriver(reinterpret_cast<BYTE*>(module),false,nullptr);}
#ifdef MOTION60_TEST
bool motion60TestSetMapped(BYTE* p,size_t n,MotionAbsoluteFn a,bool enabled){return setMapped(p,n,reinterpret_cast<Absolute>(a),enabled,nullptr);}
void motion60TestInitialize(BYTE* p,MotionAbsoluteFn a){memset(p,0,0x10b000);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;BYTE prefix[]={0x55,0x8b,0xec,0x81,0xec,0x04,0x03,0x00,0x00,0x56,0x57};memcpy(p+0x3b0c0,prefix,sizeof(prefix));BYTE call[]={0xff,0x15,0,0,0,0,0x83,0xc4,0x10};*reinterpret_cast<DWORD*>(call+2)=reinterpret_cast<DWORD>(p+0xbd0a4);memcpy(p+0x3b7fb,call,sizeof(call));*reinterpret_cast<DWORD*>(p+0xbd9f8)=reinterpret_cast<DWORD>(p+0x3b0c0);*reinterpret_cast<DWORD*>(p+0xbd0a4)=reinterpret_cast<DWORD>(a);}
void motion60TestConfigure(MotionRenderFn r,MotionAbsoluteFn a){originalRender=reinterpret_cast<Render>(r);originalAbsolute=reinterpret_cast<Absolute>(a);LARGE_INTEGER f{};QueryPerformanceFrequency(&f);frequency=f.QuadPart;caches.clear();}
void motion60TestSetTime(double milliseconds){fixtureClock=true;fixtureTicks=static_cast<LONGLONG>(milliseconds*frequency/1000.0);}
void motion60TestRender(void* o,int f){renderHook(o,nullptr,f,nullptr,0,0,0,0,0);}
void motion60TestRenderParent(void* o,int f,MotionMatrix* p){renderHook(o,nullptr,f,reinterpret_cast<Matrix*>(p),0,0,0,0,0);}
void motion60TestAbsolute(void* b,unsigned r,MotionMatrix* p,MotionMatrix* parent){absoluteHook(b,r,reinterpret_cast<Matrix*>(p),reinterpret_cast<Matrix*>(parent));}
void motion60TestBlend(const MotionMatrix& a,const MotionMatrix& b,float t,MotionMatrix& out){blend(reinterpret_cast<const Matrix&>(a),reinterpret_cast<const Matrix&>(b),t,reinterpret_cast<Matrix&>(out));}
void motion60TestComplete(BYTE* p,bool enabled){engineBase=p;complete=enabled;timeline.reset();timelineThread=GetCurrentThreadId();cameraState={};cameraTrack.reset();caches.clear();}
void motion60TestFreeView(bool enabled,bool toggle,bool reset,float yaw,float dt){freeView=enabled;freeFixture=true;freeFixtureInput={toggle,reset,yaw,0,0,dt};}
void motion60TestTick(unsigned consumed,unsigned remainder,unsigned timestamp){timeline.observe(1,33,remainder,consumed,timestamp,true);cameraState.valid=false;}
void motion60TestDiagnosticLogger(void(*logger)(const wchar_t*)){trace=logger;diagnostics.reset();}
void motion60TestPrepareHistory(void* object,int frame){prepareHistory(object,frame);}
void motion60TestCamera(void* d,MotionMatrix* m,void(__thiscall* f)(void*,MotionMatrix*)){cameraMatrix(d,reinterpret_cast<Matrix*>(m),reinterpret_cast<LoadMatrix>(f));}
bool motion60TestTimerPatch(BYTE* p,bool enabled){return timerPatch(p,enabled);}
bool motion60TestDriverSet(BYTE* p,bool enabled){return setDriver(p,enabled,nullptr);}
#endif
