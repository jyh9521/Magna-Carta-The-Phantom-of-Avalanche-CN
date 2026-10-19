#include "title_layout.h"
#include "wide_ui.h"
#include <cstring>
#include <array>
#ifndef TITLE_LAYOUT_TEST
#include "title_texture.h"
#endif
namespace {
struct OpeningLayoutEntry{int layout;float inkCenterX,inkCenterY;};
#ifdef OPENING_LAYOUT_DATA_HEADER
#include OPENING_LAYOUT_DATA_HEADER
#else
constexpr std::array<OpeningLayoutEntry,0> openingLayouts{};
#endif
bool hdBackground=false;BYTE* titleEngine=nullptr;
ULONG_PTR bgCompareResume=0,menuCompareResume=0,buttonResume=0,tileResume=0,tileSetter=0;
#ifdef TITLE_LAYOUT_TEST
int fixturePhysical=640,fixtureCanvas=853,fixtureHeight=600;
#endif
int __cdecl physical(){
#ifdef TITLE_LAYOUT_TEST
 return fixturePhysical;
#else
 int width=wideUiPhysicalWidth();return width>0?width:(titleEngine?*reinterpret_cast<int*>(titleEngine+0xf1b48):0);
#endif
}
int __cdecl centerOffset(){
#ifdef TITLE_LAYOUT_TEST
 int canvas=fixtureCanvas;
#else
 int canvas=wideUiCanvasWidth();if(canvas<=0&&titleEngine)canvas=*reinterpret_cast<int*>(titleEngine+0xf1b48);
#endif
 int width=physical();return width>0&&canvas>width?(canvas-width+1)/2:0;
}
__declspec(naked) void bgCompare(){__asm {
 pushad
 call physical
 cmp eax,700
 popad
 jmp dword ptr[bgCompareResume]
}}
__declspec(naked) void menuCompare(){__asm {
 pushad
 call physical
 cmp eax,700
 popad
 jmp dword ptr[menuCompareResume]
}}
__declspec(naked) void buttonPoint(){__asm {
 pushfd
 pushad
 call centerOffset
 add dword ptr[ebp-18h],eax
 popad
 popfd
 push 1a8h
 jmp dword ptr[buttonResume]
}}
// GUI decorations are independent render nodes. Their local +0x24 vector,
// not the container's constructor point, feeds the BGR render transform.
void __cdecl centerTile(int id,float* position,void* node){
 // Locale-specific ink bounds come only from verified generated metadata.
 // Translate every child equally; retain seams, depth, fade and glyph scale.
 for(const auto& opening:openingLayouts)if(id==opening.layout){
#ifdef TITLE_LAYOUT_TEST
  int canvas=fixtureCanvas,height=fixtureHeight;
#else
  int canvas=wideUiCanvasWidth();
  if(canvas<=0&&titleEngine)canvas=*reinterpret_cast<int*>(titleEngine+0xf1b48);
  int height=titleEngine?*reinterpret_cast<int*>(titleEngine+0xf1b4c):0;
#endif
  if(canvas>0&&height>0){
   position[0]+=canvas*0.5f-opening.inkCenterX;
   position[1]+=height*0.5f-opening.inkCenterY;
  }
  return;
 }
 if(id!=209&&id!=210)return;
 if(!hdBackground){position[0]+=static_cast<float>(centerOffset());return;}
 // Six overlapping power-of-two tiles cover the 3840x2160 master.
 // Uniform scaling preserves the title; the viewport clips padded tile edges.
 float scale=static_cast<float>(physical())/2880.f;
 position[0]=position[0]*5.f*scale+(centerOffset()?0.f:(static_cast<float>(physical())-3840.f*scale)/2.f);position[1]*=(1080.f/256.f)*scale;
 float* size=reinterpret_cast<float*>(static_cast<BYTE*>(node)+0x40);
 size[0]=scale;size[1]=scale;
}
__declspec(naked) void tilePoint(){__asm {
 pushfd
 pushad
 lea eax,[esp+36]
 push dword ptr[esp+24]
 push eax
 push dword ptr[ebp+10h]
 call centerTile
 add esp,12
 popad
 popfd
 call dword ptr[tileSetter]
 jmp dword ptr[tileResume]
}}
struct Site{DWORD rva;BYTE original[10];unsigned count;void* hook;};
Site sites[]={
 {0xb6c96,{0x81,0x3d,0,0,0,0,0xbc,0x02,0,0},10,bgCompare},
 {0xb79a1,{0x81,0x3d,0,0,0,0,0xbc,0x02,0,0},10,menuCompare},
 {0xb79d9,{0x68,0xa8,0x01,0,0},5,buttonPoint},
 {0x4e370,{0xe8,0x7b,0xf0,0xff,0xff},5,tilePoint}};
void expected(BYTE* p){for(int i=0;i<2;++i)*reinterpret_cast<DWORD*>(sites[i].original+2)=reinterpret_cast<DWORD>(p+0xf1b48);}
void patch(const Site& s,BYTE* p,BYTE* out){memset(out,0x90,s.count);out[0]=0xe9;*reinterpret_cast<int*>(out+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(s.hook)-reinterpret_cast<ULONG_PTR>(p+s.rva+5));}
bool write(BYTE* p,const BYTE* bytes,unsigned n){DWORD old;if(!VirtualProtect(p,n,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(p,bytes,n);bool ok=FlushInstructionCache(GetCurrentProcess(),p,n)!=FALSE;DWORD ignored;return VirtualProtect(p,n,old,&ignored)!=FALSE&&ok;}
bool header(BYTE* p,size_t n){if(!p||n<0x10b000)return false;auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<=0||d->e_lfanew>4096)return false;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&nt->OptionalHeader.SizeOfImage==0x10b000;}
}
bool setTitleLayout(BYTE* p,size_t n,bool enabled){
 if(!header(p,n))return false;expected(p);BYTE desired[10],before[4][10];
 for(unsigned i=0;i<4;++i){auto& s=sites[i];patch(s,p,desired);if(memcmp(p+s.rva,s.original,s.count)&&memcmp(p+s.rva,desired,s.count))return false;memcpy(before[i],p+s.rva,s.count);}
 bgCompareResume=reinterpret_cast<ULONG_PTR>(p+0xb6ca0);menuCompareResume=reinterpret_cast<ULONG_PTR>(p+0xb79ab);buttonResume=reinterpret_cast<ULONG_PTR>(p+0xb79de);tileResume=reinterpret_cast<ULONG_PTR>(p+0x4e375);tileSetter=reinterpret_cast<ULONG_PTR>(p+0x4d3f0);
 for(unsigned i=0;i<4;++i){auto& s=sites[i];patch(s,p,desired);if(!write(p+s.rva,enabled?desired:s.original,s.count)){for(unsigned j=0;j<=i;++j)write(p+sites[j].rva,before[j],sites[j].count);return false;}}
 return true;
}
bool installTitleLayout(HMODULE module,void(*log)(const wchar_t*)){titleEngine=reinterpret_cast<BYTE*>(module);wchar_t mode[8]{};hdBackground=GetEnvironmentVariableW(L"MC_TITLE_BACKGROUND4K",mode,8)&&!wcscmp(mode,L"1");
#ifndef TITLE_LAYOUT_TEST
if(hdBackground&&!installTitleTexture(module,GetModuleHandleW(L"Asura.dll"),log))return false;
#endif
bool ok=setTitleLayout(reinterpret_cast<BYTE*>(module),0x10b000,true);if(ok&&log)log(L"TITLE_LAYOUT_READY art_size=physical_layout title_tile_vectors=centered game_canvas=unchanged");return ok;}
#ifdef TITLE_LAYOUT_TEST
void initializeTitleLayoutFixture(BYTE* p){memset(p,0,0x10b000);auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x80;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;expected(p);for(auto& s:sites)memcpy(p+s.rva,s.original,s.count);}
void configureTitleLayoutFixture(int p,int c){fixturePhysical=p;fixtureCanvas=c;}
void configureOpeningHeightFixture(int height){fixtureHeight=height;}
void configureTitleBackgroundFixture(bool enabled){hdBackground=enabled;}
#endif
