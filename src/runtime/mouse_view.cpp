#include "mouse_view.h"
#include "mouse_view_transform.h"
#include "camera_input_view.h"
#include "world_gamepad.h"
#include <cstring>
namespace {
struct Point {int x,y;};using Getter=Point*(__cdecl*)(Point*);
BYTE* engine=nullptr;Getter originalMouse=nullptr,originalCenter=nullptr;BYTE baseline[5]{};
void(*trace)(const wchar_t*)=nullptr;
bool readable(const void* a,size_t n){auto p=reinterpret_cast<ULONG_PTR>(a),end=p+n;if(!p||end<p)return false;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;}
Point* __cdecl pointHook(Point* out){
 auto result=originalMouse(out);
 if(!worldExplorationActive()||!readable(out,8))return result;
 auto camera=*reinterpret_cast<BYTE**>(engine+0xf2290);float displayed[16];
 if(!readable(camera,0xc0)||!render_input::inputView.read(reinterpret_cast<uintptr_t>(camera),GetTickCount(),displayed))return result;
 Point center{};originalCenter(&center);int x=out->x,y=out->y;
 if(render_input::mouseViewPoint(reinterpret_cast<float*>(camera+0x80),displayed,center.x,center.y,out->x,out->y,x,y)){
  out->x=x;out->y=y;
  static LONG used=0;if(InterlockedIncrement(&used)==1&&trace)trace(L"MOUSE_VIEW_APPLIED scope=original_mouse_movement local_coordinate_copy=true ui_cursor=unchanged camera=unchanged");
 }
 return result;
}
void callBytes(BYTE* base,void* target,BYTE (&out)[5]){out[0]=0xe8;auto delta=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(target)-reinterpret_cast<ULONG_PTR>(base+0x6e931));memcpy(out+1,&delta,4);}
bool write(BYTE* target,const BYTE* expected,const BYTE* value){if(memcmp(target,expected,5))return false;DWORD old;if(!VirtualProtect(target,5,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(target,value,5);FlushInstructionCache(GetCurrentProcess(),target,5);DWORD ignored;if(!VirtualProtect(target,5,old,&ignored)){memcpy(target,expected,5);FlushInstructionCache(GetCurrentProcess(),target,5);VirtualProtect(target,5,old,&ignored);return false;}return true;}
}
bool installMouseView(HMODULE module,void(*logger)(const wchar_t*)){
 auto p=reinterpret_cast<BYTE*>(module);BYTE hook[5];if(engine){callBytes(engine,reinterpret_cast<void*>(&pointHook),hook);return p==engine&&!memcmp(p+0x6e92c,hook,5);}
 if(!readable(p,0x10b000))return false;auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<1||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 BYTE expected[5];callBytes(p,p+0x2e02,expected);if(memcmp(p+0x6e92c,expected,5))return false;
#ifndef MOUSE_VIEW_TEST
 const BYTE before[]={0x8d,0x4d,0xa4,0x51},after[]={0x83,0xc4,0x04};
 if(memcmp(p+0x6e928,before,4)||memcmp(p+0x6e931,after,3))return false;
#endif
 originalMouse=reinterpret_cast<Getter>(p+0x2e02);originalCenter=reinterpret_cast<Getter>(p+0xd7bc);engine=p;trace=logger;memcpy(baseline,expected,5);callBytes(p,reinterpret_cast<void*>(&pointHook),hook);
 if(!write(p+0x6e92c,expected,hook)){engine=nullptr;return false;}
 if(trace)trace(L"MOUSE_VIEW_READY callsite=6e92c source_locked=true remap=ground_ray original_camera=unchanged");return true;
}
bool removeMouseView(){if(!engine)return true;BYTE hook[5];callBytes(engine,reinterpret_cast<void*>(&pointHook),hook);if(!write(engine+0x6e92c,hook,baseline))return false;engine=nullptr;return true;}
