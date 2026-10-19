#include "gui_parent_guard.h"
#include <cstdint>
#include <cstring>
namespace {
constexpr unsigned site=0x38b45, imageSize=0x10b000;
constexpr BYTE original[]={0x83,0x7a,0x08,0x00,0x74,0x72};
constexpr BYTE vectorPrefix[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc,0x8b,0x45,0xfc,0x8b,0x4d,0x08,0xd9,0x00,0xd8,0x01};
BYTE* installed=nullptr; BYTE* bridge=nullptr;
bool readable(const void* value,size_t count){
 auto p=reinterpret_cast<uintptr_t>(value);if(!p||count>~uintptr_t(0)-p)return false;
 const auto end=p+count;
 while(p<end){MEMORY_BASIC_INFORMATION m{};
  if(!VirtualQuery(reinterpret_cast<const void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  DWORD a=m.Protect&0xff;
  if(a!=PAGE_READONLY&&a!=PAGE_READWRITE&&a!=PAGE_WRITECOPY&&a!=PAGE_EXECUTE_READ&&a!=PAGE_EXECUTE_READWRITE&&a!=PAGE_EXECUTE_WRITECOPY)return false;
  auto b=reinterpret_cast<uintptr_t>(m.BaseAddress);if(m.RegionSize>~uintptr_t(0)-b)return false;
  auto next=b+m.RegionSize;if(next<=p)return false;p=next<end?next:end;
 }return true;
}
bool identity(BYTE* p){
 if(!readable(p,sizeof(IMAGE_DOS_HEADER)))return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);
 if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096||!readable(p+d->e_lfanew,sizeof(IMAGE_NT_HEADERS32)))return false;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);
 if(n->Signature!=IMAGE_NT_SIGNATURE||n->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||n->FileHeader.TimeDateStamp!=0x3ed73966||n->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||n->OptionalHeader.SizeOfImage!=imageSize)return false;
 if(!readable(p+site,6)||!readable(p+0x1e940,sizeof(vectorPrefix))||memcmp(p+0x1e940,vectorPrefix,sizeof(vectorPrefix)))return false;
 // The source-locked launcher verifies the complete engine hash before loading.
 // Validate the generic GUI vtable and allocator's exact 0x54 allocation too.
 constexpr BYTE allocation[]={0x6a,0x54};
 return readable(p+0xba4c,2)&&!memcmp(p+0xba4c,allocation,2)&&readable(p+0xbd604,4)&&*reinterpret_cast<DWORD*>(p+0xbd604)==DWORD(uintptr_t(p+0x9440));
}
void branch(BYTE* b,BYTE* p){b[0]=0xe9;DWORD rel=DWORD(uintptr_t(bridge)-uintptr_t(p+site+5));memcpy(b+1,&rel,4);b[5]=0x90;}
bool replace(BYTE* p,const BYTE* from,const BYTE* to){
 if(memcmp(p,from,6))return false;DWORD old;
 if(!VirtualProtect(p,6,PAGE_EXECUTE_READWRITE,&old))return false;
 memcpy(p,to,6);FlushInstructionCache(GetCurrentProcess(),p,6);DWORD ignored;
 if(!VirtualProtect(p,6,old,&ignored)){memcpy(p,from,6);FlushInstructionCache(GetCurrentProcess(),p,6);VirtualProtect(p,6,old,&ignored);return false;}return true;
}
}
size_t encodeGuiParentGuard(BYTE* out,DWORD base,DWORD address){
 // EDX is the native child. Preserve EAX; both exits repeat the original CMP,
 // so flags have exactly the native value at their respective continuations.
 // Only the live generic root's first 12 bytes are inspected, never +f4/+100.
 // Other parent types retain native inheritance and native fault behavior.
 size_t n=0;size_t skipFix=0,inheritFix[4]{};
 auto bytes=[&](const BYTE* b,size_t len){memcpy(out+n,b,len);n+=len;};
 auto word=[&](DWORD v){memcpy(out+n,&v,4);n+=4;};
 auto cond=[&](BYTE op){out[n++]=0x0f;out[n++]=op;size_t pos=n;word(0);return pos;};
 auto fix=[&](size_t pos,DWORD target){DWORD v=target-(address+DWORD(pos)+4);memcpy(out+pos,&v,4);};
 const BYTE first[]={0x50,0x8b,0x42,0x08,0x85,0xc0};bytes(first,sizeof(first));skipFix=cond(0x84);
 out[n++]=0x3b;out[n++]=0x05;word(base+0xf220c);inheritFix[0]=cond(0x85);
 out[n++]=0x81;out[n++]=0x38;word(base+0xbd604);inheritFix[1]=cond(0x85);
 const BYTE type[]={0x83,0x78,0x04,0x02};bytes(type,4);inheritFix[2]=cond(0x85);
 const BYTE parent[]={0x83,0x78,0x08,0x00};bytes(parent,4);inheritFix[3]=cond(0x85);
 const BYTE exit[]={0x58,0x83,0x7a,0x08,0x00};
 const size_t skip=n;bytes(exit,5);out[n++]=0xe9;word((base+0x38bbd)-(address+DWORD(n)+4));
 const size_t inherit=n;bytes(exit,5);out[n++]=0xe9;word((base+0x38b4b)-(address+DWORD(n)+4));
 fix(skipFix,address+DWORD(skip));for(auto pos:inheritFix)fix(pos,address+DWORD(inherit));return n;
}
bool installGuiParentGuard(HMODULE module,void(*log)(const wchar_t*)){
 auto p=reinterpret_cast<BYTE*>(module);if(!identity(p))return false;
 if(installed){BYTE hook[6];branch(hook,p);return installed==p&&!memcmp(p+site,hook,6);}
 if(memcmp(p+site,original,6))return false;
 bridge=static_cast<BYTE*>(VirtualAlloc(nullptr,256,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));if(!bridge)return false;
 auto size=encodeGuiParentGuard(bridge,DWORD(uintptr_t(p)),DWORD(uintptr_t(bridge)));DWORD old;
 if(!VirtualProtect(bridge,256,PAGE_EXECUTE_READ,&old)){VirtualFree(bridge,0,MEM_RELEASE);bridge=nullptr;return false;}
 FlushInstructionCache(GetCurrentProcess(),bridge,size);BYTE hook[6];branch(hook,p);
 if(!replace(p+site,original,hook)){VirtualFree(bridge,0,MEM_RELEASE);bridge=nullptr;return false;}
 installed=p;if(log)log(L"GUI_PARENT_GUARD_READY site=38b45 scope=generic_gui_root spatial_inheritance=original");return true;
}
bool removeGuiParentGuard(HMODULE module){
 auto p=reinterpret_cast<BYTE*>(module);if(!identity(p))return false;
 if(!installed)return !memcmp(p+site,original,6);
 if(installed!=p)return false;BYTE hook[6];branch(hook,p);
 if(!replace(p+site,hook,original))return false;
 // Caller must quiesce native transform calls before uninstall. Normal launcher
 // rollback is file-based while the game is stopped; never hot-unhook in DllMain.
 VirtualFree(bridge,0,MEM_RELEASE);bridge=nullptr;installed=nullptr;return true;
}
#ifdef GUI_PARENT_GUARD_TEST
void initializeGuiParentGuardFixture(BYTE* p){
 memset(p,0,imageSize);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;
 auto n=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->FileHeader.TimeDateStamp=0x3ed73966;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=imageSize;
 memcpy(p+site,original,6);memcpy(p+0x1e940,vectorPrefix,sizeof(vectorPrefix));p[0xba4c]=0x6a;p[0xba4d]=0x54;*reinterpret_cast<DWORD*>(p+0xbd604)=DWORD(uintptr_t(p+0x9440));
}
#endif
