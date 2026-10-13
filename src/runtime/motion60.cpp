#include "motion60.h"
#include <intrin.h>
#include <array>
#include <vector>
#include <map>
#include <cmath>
#include <algorithm>
#include <cstring>
namespace {
struct Matrix {float v[16];};
struct Q {float x,y,z,w;};
Q quaternion(const Matrix& m){
 Q q{};float t=m.v[0]+m.v[5]+m.v[10];
 if(t>0){float s=std::sqrt(t+1)*2;q.w=s/4;q.x=(m.v[9]-m.v[6])/s;q.y=(m.v[2]-m.v[8])/s;q.z=(m.v[4]-m.v[1])/s;}
 else if(m.v[0]>m.v[5]&&m.v[0]>m.v[10]){float s=std::sqrt(1+m.v[0]-m.v[5]-m.v[10])*2;q.w=(m.v[9]-m.v[6])/s;q.x=s/4;q.y=(m.v[1]+m.v[4])/s;q.z=(m.v[2]+m.v[8])/s;}
 else if(m.v[5]>m.v[10]){float s=std::sqrt(1+m.v[5]-m.v[0]-m.v[10])*2;q.w=(m.v[2]-m.v[8])/s;q.x=(m.v[1]+m.v[4])/s;q.y=s/4;q.z=(m.v[6]+m.v[9])/s;}
 else {float s=std::sqrt(1+m.v[10]-m.v[0]-m.v[5])*2;q.w=(m.v[4]-m.v[1])/s;q.x=(m.v[2]+m.v[8])/s;q.y=(m.v[6]+m.v[9])/s;q.z=s/4;}return q;
}
bool rigid(const Matrix& m){
 for(float x:m.v)if(!std::isfinite(x))return false;
 for(int r=0;r<3;++r){float n=0;for(int c=0;c<3;++c)n+=m.v[r*4+c]*m.v[r*4+c];if(std::abs(n-1)>0.03f)return false;
 for(int s=0;s<r;++s){float d=0;for(int c=0;c<3;++c)d+=m.v[r*4+c]*m.v[s*4+c];if(std::abs(d)>0.03f)return false;}}
 float det=m.v[0]*(m.v[5]*m.v[10]-m.v[6]*m.v[9])-m.v[1]*(m.v[4]*m.v[10]-m.v[6]*m.v[8])+m.v[2]*(m.v[4]*m.v[9]-m.v[5]*m.v[8]);
 return det>0.97f&&det<1.03f&&std::abs(m.v[3])+std::abs(m.v[7])+std::abs(m.v[11])<0.001f&&std::abs(m.v[15]-1)<0.001f;
}
void blend(const Matrix& a,const Matrix& b,float t,Matrix& out){
 out=b;if(t>=1)return;if(t<=0){out=a;return;}if(!rigid(a)||!rigid(b))return;
 Q x=quaternion(a),y=quaternion(b);float dot=x.x*y.x+x.y*y.y+x.z*y.z+x.w*y.w;
 if(dot<0){y.x=-y.x;y.y=-y.y;y.z=-y.z;y.w=-y.w;}
 Q q{x.x+(y.x-x.x)*t,x.y+(y.y-x.y)*t,x.z+(y.z-x.z)*t,x.w+(y.w-x.w)*t};
 float n=std::sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w);if(n<0.001f)return;q.x/=n;q.y/=n;q.z/=n;q.w/=n;
 out.v[0]=1-2*(q.y*q.y+q.z*q.z);out.v[1]=2*(q.x*q.y-q.z*q.w);out.v[2]=2*(q.x*q.z+q.y*q.w);
 out.v[4]=2*(q.x*q.y+q.z*q.w);out.v[5]=1-2*(q.x*q.x+q.z*q.z);out.v[6]=2*(q.y*q.z-q.x*q.w);
 out.v[8]=2*(q.x*q.z-q.y*q.w);out.v[9]=2*(q.y*q.z+q.x*q.w);out.v[10]=1-2*(q.x*q.x+q.y*q.y);
 for(int i=12;i<15;++i)out.v[i]=a.v[i]+(b.v[i]-a.v[i])*t;
}
using Render=void(__thiscall*)(void*,int,Matrix*,int,int,int,int,int);
using Absolute=void(__cdecl*)(void*,unsigned,Matrix*,Matrix*);
Render originalRender=nullptr;Absolute originalAbsolute=nullptr;BYTE* engineBase=nullptr;
void(*trace)(const wchar_t*)=nullptr;
struct Cache{void* action=nullptr;void* bones=nullptr;Matrix* pose=nullptr;int frame=0;LONGLONG changed=0,last=0;std::vector<Matrix> previous,current;};
std::map<void*,Cache> caches;SRWLOCK cacheLock=SRWLOCK_INIT;LONGLONG frequency=0;
#ifdef MOTION60_TEST
bool fixtureClock=false;LONGLONG fixtureTicks=0;
#endif
struct Context{void* object;int frame;Matrix* pose=nullptr;std::vector<Matrix> baseline;Context* parent;};
thread_local Context* active=nullptr;volatile LONG changes=0;
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
auto& c=caches[active->object];bool reset=c.current.size()!=count||c.action!=action||c.bones!=bones||c.pose!=poses||now.QuadPart-c.last>frequency/4;
 if(!reset&&active->frame==c.frame&&memcmp(current.data(),c.current.data(),count*sizeof(Matrix)))reset=true;
 if(!reset&&active->frame!=c.frame&&active->frame!=c.frame+1)reset=true;
 if(reset){c.previous=current;c.current=current;c.frame=active->frame;c.changed=now.QuadPart;c.action=action;c.bones=bones;c.pose=poses;}
 else if(active->frame!=c.frame){c.previous=c.current;c.current=current;c.frame=active->frame;c.changed=now.QuadPart;}
 c.last=now.QuadPart;float alpha=frequency?static_cast<float>((now.QuadPart-c.changed)*1000.0/(frequency*33.0)):1;alpha=(std::max)(0.f,(std::min)(1.f,alpha));
 for(unsigned i=0;i<count;++i)blend(c.previous[i],c.current[i],alpha,interpolated[i]);
 if(caches.size()>128)for(auto i=caches.begin();i!=caches.end();)if(i->first!=active->object&&now.QuadPart-i->second.last>frequency/4)i=caches.erase(i);else ++i;
 lock.release();
 // Obtain the exact unmodified absolute output first; restore it after drawing.
 active->baseline.resize(count);originalAbsolute(bones,root,poses,parent);memcpy(active->baseline.data(),poses,count*sizeof(Matrix));active->pose=poses;
 memcpy(poses,interpolated.data(),count*sizeof(Matrix));originalAbsolute(bones,root,poses,parent);
 if(InterlockedIncrement(&changes)==1&&trace)trace(L"MOTION60_POSE_APPLIED scope=skeletal_local_pose logic_interval_ms=33 world_camera=unchanged latency_ticks=1");
}
void renderScoped(Context* ctx,void* object,int frame,Matrix* world,int a,int b,int c,int d,int e){
 __try {active=ctx;originalRender(object,frame,world,a,b,c,d,e);}
 __finally {if(ctx->pose&&!ctx->baseline.empty())memcpy(ctx->pose,ctx->baseline.data(),ctx->baseline.size()*sizeof(Matrix));active=ctx->parent;}
}
void __fastcall renderHook(void* object,void*,int frame,Matrix* world,int a,int b,int c,int d,int e){
 Context ctx{object,frame,nullptr,{},active};renderScoped(&ctx,object,frame,world,a,b,c,d,e);
}
bool write(void* p,DWORD value){DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;DWORD before=*static_cast<DWORD*>(p);*static_cast<DWORD*>(p)=value;DWORD unused;if(VirtualProtect(p,4,old,&unused))return true;*static_cast<DWORD*>(p)=before;VirtualProtect(p,4,old,&unused);return false;}
}
namespace {
bool headerMatches(BYTE* p,size_t n){if(!readable(p,n)||n<0x10b000)return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096)return false;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&nt->OptionalHeader.SizeOfImage==0x10b000;}
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
 return setMapped(reinterpret_cast<BYTE*>(engine),0x10b000,reinterpret_cast<Absolute>(absolute),true,logger);
}
bool removeMotion60(HMODULE engine){return engineBase==reinterpret_cast<BYTE*>(engine)&&setMapped(engineBase,0x10b000,originalAbsolute,false,nullptr);}
#ifdef MOTION60_TEST
bool motion60TestSetMapped(BYTE* p,size_t n,MotionAbsoluteFn a,bool enabled){return setMapped(p,n,reinterpret_cast<Absolute>(a),enabled,nullptr);}
void motion60TestInitialize(BYTE* p,MotionAbsoluteFn a){memset(p,0,0x10b000);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;BYTE prefix[]={0x55,0x8b,0xec,0x81,0xec,0x04,0x03,0x00,0x00,0x56,0x57};memcpy(p+0x3b0c0,prefix,sizeof(prefix));BYTE call[]={0xff,0x15,0,0,0,0,0x83,0xc4,0x10};*reinterpret_cast<DWORD*>(call+2)=reinterpret_cast<DWORD>(p+0xbd0a4);memcpy(p+0x3b7fb,call,sizeof(call));*reinterpret_cast<DWORD*>(p+0xbd9f8)=reinterpret_cast<DWORD>(p+0x3b0c0);*reinterpret_cast<DWORD*>(p+0xbd0a4)=reinterpret_cast<DWORD>(a);}
void motion60TestConfigure(MotionRenderFn r,MotionAbsoluteFn a){originalRender=reinterpret_cast<Render>(r);originalAbsolute=reinterpret_cast<Absolute>(a);LARGE_INTEGER f{};QueryPerformanceFrequency(&f);frequency=f.QuadPart;caches.clear();}
void motion60TestSetTime(double milliseconds){fixtureClock=true;fixtureTicks=static_cast<LONGLONG>(milliseconds*frequency/1000.0);}
void motion60TestRender(void* o,int f){renderHook(o,nullptr,f,nullptr,0,0,0,0,0);}
void motion60TestAbsolute(void* b,unsigned r,MotionMatrix* p,MotionMatrix* parent){absoluteHook(b,r,reinterpret_cast<Matrix*>(p),reinterpret_cast<Matrix*>(parent));}
void motion60TestBlend(const MotionMatrix& a,const MotionMatrix& b,float t,MotionMatrix& out){blend(reinterpret_cast<const Matrix&>(a),reinterpret_cast<const Matrix&>(b),t,reinterpret_cast<Matrix&>(out));}
#endif
