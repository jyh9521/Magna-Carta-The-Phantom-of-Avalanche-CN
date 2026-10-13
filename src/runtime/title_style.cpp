#include "title_style.h"
#include <cstring>
#include <intrin.h>
#include <cmath>
namespace {
using Draw=void(__thiscall*)(void*);
using Render=void(__cdecl*)(unsigned,unsigned,void*,unsigned,unsigned,int,int,unsigned,unsigned,unsigned,unsigned,unsigned,void*,unsigned);
Draw originalDraw=nullptr;Render originalRender=nullptr;BYTE* engine=nullptr;
float* currentColor=nullptr;
void(*trace)(const wchar_t*)=nullptr;
struct Context {void* vertices[64]{};unsigned count=0,tint=0xffffffff;};
thread_local Context* current=nullptr;
#ifdef TITLE_STYLE_TEST
void* fixtureRenderer=nullptr;
float* fixtureColor=nullptr;
#endif
bool readable(const void* a,size_t n){auto p=reinterpret_cast<ULONG_PTR>(a),end=p+n;if(!p||end<p)return false;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;}
bool replace(DWORD* p,DWORD expected,DWORD value){if(*p!=expected)return false;DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;bool good=InterlockedCompareExchange(reinterpret_cast<LONG*>(p),value,expected)==static_cast<LONG>(expected);DWORD ignored;if(!VirtualProtect(p,4,old,&ignored)){if(good)InterlockedCompareExchange(reinterpret_cast<LONG*>(p),expected,value);VirtualProtect(p,4,old,&ignored);return false;}return good;}
void gather(BYTE* p,Context& c,BYTE* (&seen)[64],unsigned& count){
 if(!readable(p,0x20)||count>=64)return;for(unsigned i=0;i<count;++i)if(seen[i]==p)return;seen[count++]=p;
 auto vt=*reinterpret_cast<BYTE**>(p);
 if(vt==engine+0xbdb9c&&readable(p,0x174)&&c.count<64)c.vertices[c.count++]=p+0x124;
 // These are the render child links, not the input child links (+18/+10).
 auto child=*reinterpret_cast<BYTE**>(p+0x1c);
 while(child&&readable(child,0x10)&&count<64){unsigned before=count;gather(child,c,seen,count);if(count==before)break;child=*reinterpret_cast<BYTE**>(child+0xc);}
 // Only known GUI button/base GUI objects own the +ec visual root.
 if((vt==engine+0xbee80||vt==engine+0xbec88)&&readable(p,0xf0))gather(*reinterpret_cast<BYTE**>(p+0xec),c,seen,count);
}
bool style(BYTE* button,Context& c){
 if(!readable(button,0x1a8)||*reinterpret_cast<BYTE**>(button)!=engine+0xbee80)return false;
 int id=*reinterpret_cast<int*>(button+4);if(id<0x16c||id>0x16f)return false;
 auto menu=*reinterpret_cast<BYTE**>(button+0x17c);if(!readable(menu,0x1ac)||*reinterpret_cast<BYTE**>(menu)!=engine+0xc2340)return false;
 auto owner=*reinterpret_cast<BYTE**>(menu+0x1a8);if(!readable(owner,0x74)||*reinterpret_cast<BYTE**>(owner)!=engine+0xc22f0||*reinterpret_cast<int*>(owner+0x70)!=4)return false;
 bool enabled=*reinterpret_cast<int*>(button+0x160)!=0,focused=*reinterpret_cast<int*>(button+0x198)!=0,pushed=*reinterpret_cast<int*>(button+0x19c)!=0;
 c.tint=!enabled?0xff706e68:pushed?0xffff8f35:focused?0xffffbd66:0xffaaa69e;
 BYTE* seen[64]{};unsigned count=0;gather(button,c,seen,count);return c.count!=0;
}
void __cdecl renderHook(unsigned format,unsigned primitive,void* vertices,unsigned index,unsigned count,int first,int texture,unsigned color,unsigned blend,unsigned a,unsigned b,unsigned d,void* matrix,unsigned flags){
 bool apply=false;if(current&&format==0x102&&primitive==5&&count==4)for(unsigned i=0;i<current->count;++i)if(current->vertices[i]==vertices){apply=true;break;}
 float saved[4];if(apply){memcpy(saved,currentColor,sizeof(saved));for(float f:saved)if(!std::isfinite(f)||f<0||f>1)apply=false;}
 if(apply)for(unsigned i=0;i<3;++i)currentColor[i]=saved[i]*float((current->tint>>(16-i*8))&255)/255.f;
 // ASRRegRender copies these RGBA floats into its owned queue record.
 // Restore immediately, so unrelated draw submissions keep the original state.
 __try {originalRender(format,primitive,vertices,index,count,first,texture,color,blend,a,b,d,matrix,flags);}
 __finally {if(apply)memcpy(currentColor,saved,sizeof(saved));}
}
void __fastcall drawHook(void* value,void*){
 Context context;Context* previous=current;bool apply=style(static_cast<BYTE*>(value),context);current=apply?&context:nullptr;
 __try {originalDraw(value);}
 __finally {current=previous;}
 static LONG used=0;if(apply&&InterlockedIncrement(&used)==1&&trace)trace(L"TITLE_STYLE_APPLIED normal=muted hover=amber pressed=orange scope=four_title_buttons resources=unchanged");
}
}
bool installTitleStyle(HMODULE module,void(*logger)(const wchar_t*)){
 if(engine)return engine==reinterpret_cast<BYTE*>(module)&&*reinterpret_cast<DWORD*>(engine+0xbee90)==reinterpret_cast<DWORD>(&drawHook)&&*reinterpret_cast<DWORD*>(engine+0xbd01c)==reinterpret_cast<DWORD>(&renderHook);
 auto p=reinterpret_cast<BYTE*>(module);if(!readable(p,0x10b000))return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 BYTE call[]={0xff,0x15};if(memcmp(p+0x4258b,call,2)||*reinterpret_cast<DWORD*>(p+0x4258d)!=reinterpret_cast<DWORD>(p+0xbd01c))return false;
 BYTE prefix[]={0x55,0x8b,0xec,0x83,0xec,0x08};if(memcmp(p+0x4c6ff,prefix,sizeof(prefix)))return false;
 auto draw=reinterpret_cast<DWORD*>(p+0xbee90),render=reinterpret_cast<DWORD*>(p+0xbd01c);
 auto expected=GetProcAddress(GetModuleHandleW(L"Asura.dll"),"?ASRRegRender@@YAXIIPAXIIHHIIIIIAAVASRMatrix@@I@Z");
 auto asura=reinterpret_cast<BYTE*>(GetModuleHandleW(L"Asura.dll"));
 currentColor=asura?reinterpret_cast<float*>(asura+0x3e2800):nullptr;
#ifdef TITLE_STYLE_TEST
 expected=reinterpret_cast<FARPROC>(fixtureRenderer);
 currentColor=fixtureColor;
#else
 if(!asura||reinterpret_cast<BYTE*>(expected)!=asura+0x51a01)return false;
#endif
 if(!expected||!readable(currentColor,16)||*draw!=reinterpret_cast<DWORD>(p+0x4c6ff)||*render!=reinterpret_cast<DWORD>(expected))return false;
 originalDraw=reinterpret_cast<Draw>(*draw);originalRender=reinterpret_cast<Render>(*render);engine=p;trace=logger;
 if(!replace(render,reinterpret_cast<DWORD>(originalRender),reinterpret_cast<DWORD>(&renderHook))){engine=nullptr;return false;}
 if(!replace(draw,reinterpret_cast<DWORD>(originalDraw),reinterpret_cast<DWORD>(&drawHook))){replace(render,reinterpret_cast<DWORD>(&renderHook),reinterpret_cast<DWORD>(originalRender));engine=nullptr;return false;}
 if(trace)trace(L"TITLE_STYLE_READY source_locked=true normal=muted selection=amber background=preserved");return true;
}
bool removeTitleStyle(){
 if(!engine)return true;auto draw=reinterpret_cast<DWORD*>(engine+0xbee90),render=reinterpret_cast<DWORD*>(engine+0xbd01c);
 if(*draw!=reinterpret_cast<DWORD>(&drawHook)||*render!=reinterpret_cast<DWORD>(&renderHook))return false;
 if(!replace(draw,reinterpret_cast<DWORD>(&drawHook),reinterpret_cast<DWORD>(originalDraw)))return false;
 if(!replace(render,reinterpret_cast<DWORD>(&renderHook),reinterpret_cast<DWORD>(originalRender))){replace(draw,reinterpret_cast<DWORD>(originalDraw),reinterpret_cast<DWORD>(&drawHook));return false;}
 engine=nullptr;current=nullptr;return true;
}
#ifdef TITLE_STYLE_TEST
void titleStyleFixtureRenderer(void* p,float* c){fixtureRenderer=p;fixtureColor=c;}
#endif
