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
struct Site{DWORD rva;BYTE original[6];void* hook;};
Site sites[]={{0x474cf,{0xff,0x92,0x94,3,0,0},rasterHook},{0x474ec,{0xff,0x92,0xb4,1,0,0},floatHook},{0x47509,{0xff,0x92,0xa4,1,0,0},boolHook}};
void changed(const Site& s,BYTE* image,BYTE* output){output[0]=0xe8;*reinterpret_cast<int*>(output+1)=static_cast<int>(reinterpret_cast<ULONG_PTR>(s.hook)-reinterpret_cast<ULONG_PTR>(image+s.rva+5));output[5]=0x90;}
bool write(BYTE* p,const BYTE* data){DWORD old;if(!VirtualProtect(p,6,PAGE_EXECUTE_READWRITE,&old))return false;memcpy(p,data,6);FlushInstructionCache(GetCurrentProcess(),p,6);DWORD ignored;bool ok=VirtualProtect(p,6,old,&ignored)!=FALSE;
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
 BYTE patches[3][6],previous[3][6];bool already=true;
 for(int i=0;i<3;++i){auto& s=sites[i];changed(s,image,patches[i]);memcpy(previous[i],image+s.rva,6);if(memcmp(previous[i],s.original,6)&&memcmp(previous[i],patches[i],6))return false;if(memcmp(previous[i],enabled?patches[i]:s.original,6))already=false;}
 if(already)return !enabled||engine==image;
 for(int i=0;i<3;++i)if(!write(image+sites[i].rva,enabled?patches[i]:sites[i].original)){for(int j=0;j<=i;++j)write(image+sites[j].rva,previous[j]);return false;}
 engine=enabled?image:nullptr;raster={};return true;
}
bool installDamageProjection(HMODULE module,void(*logger)(const wchar_t*)){bool ok=setDamageProjection(reinterpret_cast<BYTE*>(module),0x10b000,true);if(ok&&logger)logger(L"DAMAGE_PROJECTION_READY source=driver_matrices logical_canvas=true raster_valid=clip_guard native_float=preserved validation=offline");return ok;}
#ifdef DAMAGE_PROJECTION_TEST
void initializeDamageProjectionFixture(BYTE* image){memset(image,0,0x10b000);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;for(auto& s:sites)memcpy(image+s.rva,s.original,6);}
void damageProjectionWriteFailure(int index){failWrite=index;}
void damageProjectionFixtureDriver(BYTE* driver){fixtureDriver=driver;}
#endif
