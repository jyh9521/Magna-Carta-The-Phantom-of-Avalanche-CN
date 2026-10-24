#include "damage_projection.h"
#include <cmath>
#include <cstring>
namespace {
BYTE* engine=nullptr;
struct Raster {void* driver=nullptr;float position[4]{};BYTE valid=0;};
thread_local Raster raster;
#ifdef DAMAGE_PROJECTION_TEST
int failWrite=-1;BYTE* fixtureDriver=nullptr;
#endif
// D3D7 keeps row-vector modelview/projection matrices at +5c/+9c.
// Their contiguous storage matches column-vector multiplication in this loop.
void transform(const float* m,const double* in,double* out){for(int r=0;r<4;++r){out[r]=0;for(int k=0;k<4;++k)out[r]+=m[k*4+r]*in[k];}}
void __fastcall rasterHook(void* object,void*,const float* point){
 raster={};
 if(!engine||!object||!point)return;
#ifdef DAMAGE_PROJECTION_TEST
 auto driver=fixtureDriver;
#else
 auto driver=reinterpret_cast<BYTE*>(GetModuleHandleW(L"AsrD3DDrv.dll"));
#endif
 auto table=*reinterpret_cast<BYTE***>(object);
 if(!driver||table[0x1b4/4]!=driver+0x80a4||table[0x1a4/4]!=driver+0x9b8c||table[0x394/4]!=driver+0x1897c){
  using NativeRaster=void(__thiscall*)(void*,const float*);reinterpret_cast<NativeRaster>(table[0x394/4])(object,point);return;
 }
 raster.driver=object;
 auto bytes=static_cast<BYTE*>(object);double p[]={point[0],point[1],point[2],1},eye[4],clip[4];
 transform(reinterpret_cast<float*>(bytes+0x5c),p,eye);transform(reinterpret_cast<float*>(bytes+0x9c),eye,clip);
 int width=*reinterpret_cast<int*>(engine+0xf1b48),height=*reinterpret_cast<int*>(engine+0xf1b4c);
 for(double v:clip)if(!std::isfinite(v))return;
 double w=clip[3];if(width<=0||height<=0||w<=0||clip[0]<-w||clip[0]>w||clip[1]<-w||clip[1]>w||clip[2]<0||clip[2]>w)return;
 raster.position[0]=float((clip[0]/w+1)*width*.5);raster.position[1]=float((clip[1]/w+1)*height*.5);
 raster.position[2]=float(clip[2]/w);raster.position[3]=float(w);raster.valid=1;
}
void __fastcall floatHook(void* object,void*,unsigned name,float* output){
 if(name==0xb07&&raster.driver==object){memcpy(output,raster.position,sizeof(raster.position));return;}
 using Query=void(__thiscall*)(void*,unsigned,float*);reinterpret_cast<Query>((*reinterpret_cast<void***>(object))[0x1b4/4])(object,name,output);
}
void __fastcall boolHook(void* object,void*,unsigned name,BYTE* output){
 if(name==0xb08&&raster.driver==object){*output=raster.valid;return;}
 using Query=void(__thiscall*)(void*,unsigned,BYTE*);reinterpret_cast<Query>((*reinterpret_cast<void***>(object))[0x1a4/4])(object,name,output);
}
// Popup updates run independently of mesh visibility. Never use the UI driver's
// current matrices here: UI rendering has already replaced the scene camera.
int* __fastcall anchorHook(BYTE* model,void*,int* output){
 output[0]=*reinterpret_cast<int*>(model+0x138);output[1]=*reinterpret_cast<int*>(model+0x13c);
 auto d=*reinterpret_cast<BYTE**>(engine+0xf1b70);
#ifdef DAMAGE_PROJECTION_TEST
 auto driver=fixtureDriver;
#else
 auto driver=reinterpret_cast<BYTE*>(GetModuleHandleW(L"AsrD3DDrv.dll"));
#endif
 if(!d||!driver)return output;
 auto table=*reinterpret_cast<BYTE***>(d);
 if(table[0x1b4/4]!=driver+0x80a4||table[0x1a4/4]!=driver+0x9b8c||table[0x394/4]!=driver+0x1897c)return output;
 output[0]=output[1]=-1;
 auto camera=*reinterpret_cast<BYTE**>(engine+0xf2290);if(!camera)return output;
 auto lens=*reinterpret_cast<BYTE**>(camera+4);if(!lens)return output;
 int width=*reinterpret_cast<int*>(engine+0xf1b48),height=*reinterpret_cast<int*>(engine+0xf1b4c);
 double fov=*reinterpret_cast<double*>(lens+0x10),nearPlane=*reinterpret_cast<double*>(lens+0x20),farPlane=*reinterpret_cast<double*>(lens+0x28);
 if(width<=0||height<=0||!std::isfinite(fov)||fov<=0||fov>=180||!std::isfinite(nearPlane)||!std::isfinite(farPlane)||nearPlane<=0||farPlane<=nearPlane)return output;
 double p[]={*reinterpret_cast<float*>(model+0x12c),*reinterpret_cast<float*>(model+0x130),*reinterpret_cast<float*>(model+0x134),1},tmp[4];
 transform(reinterpret_cast<float*>(model+0xb4),p,tmp);memcpy(p,tmp,sizeof(p));
 // Native traversal applies each ancestor's +4c, but only this model's +b4.
 BYTE* seen[64]{};unsigned depth=0;
 for(auto node=model;node;node=*reinterpret_cast<BYTE**>(node+8)){
  if(depth==64)return output;for(unsigned i=0;i<depth;++i)if(seen[i]==node)return output;seen[depth++]=node;
  // Native 392fd -> 39aa0 omits this node's spatial transform when either
  // flag is exactly 1. A skipped child still inherits non-skipped ancestors.
  if(*reinterpret_cast<int*>(node+0x10c)!=1&&*reinterpret_cast<int*>(node+0x110)!=1){
   transform(reinterpret_cast<float*>(node+0x4c),p,tmp);memcpy(p,tmp,sizeof(p));
  }
 }
 transform(reinterpret_cast<float*>(camera+0x80),p,tmp);
 double scale=1/std::tan(fov*3.14159265358979323846/360),w=-tmp[2];
 double x=tmp[0]*scale*height/width,y=tmp[1]*scale,z=(tmp[2]*farPlane+nearPlane*farPlane)/(nearPlane-farPlane);
 if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(z)||!std::isfinite(w)||w<=0||x < -w||x>w||y < -w||y>w||z<0||z>w)return output;
 output[0]=static_cast<int>((x/w+1)*width*.5);output[1]=height-static_cast<int>((y/w+1)*height*.5);
 *reinterpret_cast<int*>(model+0x138)=output[0];*reinterpret_cast<int*>(model+0x13c)=output[1];return output;
}
// Numeric widgets are registered below the battle GUI, not below the popup.
// Hiding only the popup leaves their independently drawn digit children visible
// at an invalid or stale position during a skill-camera cut.
void __fastcall popupVisibilityHook(BYTE* popup,void*,int hidden){
 using Hide=void(__thiscall*)(BYTE*,int);
 reinterpret_cast<Hide>(engine+0x4c893)(popup,hidden);
 auto number=*reinterpret_cast<BYTE**>(popup+0xf4);if(!number)return;
 auto hide=[&](BYTE* object){reinterpret_cast<Hide>((*reinterpret_cast<void***>(object))[0x28/4])(object,hidden);};
 hide(number);
 BYTE* seen[16]{};unsigned count=0;
 for(auto digit=*reinterpret_cast<BYTE**>(number+0x18);digit;digit=*reinterpret_cast<BYTE**>(digit+0x10)){
  if(count==16)return;for(unsigned i=0;i<count;++i)if(seen[i]==digit)return;seen[count++]=digit;
  hide(digit);
 }
}
struct Site{DWORD rva;BYTE original[6];void* hook;DWORD pointerOriginal=0;};
Site sites[]={{0x474cf,{0xff,0x92,0x94,3,0,0},rasterHook},{0x474ec,{0xff,0x92,0xb4,1,0,0},floatHook},{0x47509,{0xff,0x92,0xa4,1,0,0},boolHook},
 {0xaa0ba,{0xe8,0xd1,0x24,0,0,0xc7},anchorHook},{0xaa398,{0xe8,0xf3,0x21,0,0,0x83},anchorHook},
 {0xaa629,{0xe8,0x62,0x1f,0,0,0xc7},anchorHook},{0xaa916,{0xe8,0x75,0x1c,0,0,0x83},anchorHook},
 {0xaab88,{0xe8,0x03,0x1a,0,0,0xc7},anchorHook},{0xab128,{0xe8,0x63,0x14,0,0,0x8b},anchorHook},
 {0xab453,{0xe8,0x38,0x11,0,0,0x83},anchorHook},{0xab6e1,{0xe8,0xaa,0x0e,0,0,0x8b},anchorHook},
 {0xaba34,{0xe8,0x57,0x0b,0,0,0x83},anchorHook},
 {0xc19d8,{},popupVisibilityHook,0x4c893}};
constexpr unsigned siteCount=sizeof(sites)/sizeof(sites[0]);
unsigned length(const Site& s){return s.pointerOriginal?4:6;}
void original(const Site& s,BYTE* image,BYTE* output){if(s.pointerOriginal)*reinterpret_cast<BYTE**>(output)=image+s.pointerOriginal;else memcpy(output,s.original,6);}
void changed(const Site& s,BYTE* image,BYTE* output){if(s.pointerOriginal){*reinterpret_cast<void**>(output)=s.hook;return;}output[0]=0xe8;*reinterpret_cast<int*>(output+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(s.hook)-reinterpret_cast<ULONG_PTR>(image+s.rva+5));output[5]=s.original[0]==0xe8?s.original[5]:0x90;}
bool write(BYTE* p,const BYTE* data,unsigned size){DWORD old;if(!VirtualProtect(p,size,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(p,data,size);FlushInstructionCache(GetCurrentProcess(),p,size);DWORD ignored;bool ok=VirtualProtect(p,size,old,&ignored)!=FALSE;
#ifdef DAMAGE_PROJECTION_TEST
 if(failWrite==0){failWrite=-1;return false;}if(failWrite>0)--failWrite;
#endif
 return ok;
}
}
bool setDamageProjection(BYTE* image,size_t available,bool enabled){
 if(!image||available<0x10b000)return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 BYTE patches[siteCount][6]{},previous[siteCount][6]{},originals[siteCount][6]{};bool already=true;
 for(unsigned i=0;i<siteCount;++i){auto& s=sites[i];auto size=length(s);original(s,image,originals[i]);changed(s,image,patches[i]);memcpy(previous[i],image+s.rva,size);if(memcmp(previous[i],originals[i],size)&&memcmp(previous[i],patches[i],size))return false;if(memcmp(previous[i],enabled?patches[i]:originals[i],size))already=false;}
 if(already)return !enabled||engine==image;
 for(unsigned i=0;i<siteCount;++i)if(!write(image+sites[i].rva,enabled?patches[i]:originals[i],length(sites[i]))){for(unsigned j=0;j<=i;++j)write(image+sites[j].rva,previous[j],length(sites[j]));return false;}
 engine=enabled?image:nullptr;raster={};return true;
}
bool installDamageProjection(HMODULE module,void(*logger)(const wchar_t*)){bool ok=setDamageProjection(reinterpret_cast<BYTE*>(module),0x10b000,true);if(ok&&logger)logger(L"DAMAGE_PROJECTION_READY revision=numeric_visibility_v3 source=driver_matrices logical_canvas=true raster_valid=clip_guard native_float=preserved popup_anchor=fresh_scene_camera hidden_mesh=independent spatial_skip=native_exact_one digit_visibility=popup_state validation=offline");return ok;}
#ifdef DAMAGE_PROJECTION_TEST
void initializeDamageProjectionFixture(BYTE* image){memset(image,0,0x10b000);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;for(auto& s:sites)original(s,image,image+s.rva);}
void damageProjectionWriteFailure(int index){failWrite=index;}
void damageProjectionFixtureDriver(BYTE* driver){fixtureDriver=driver;}
#endif
