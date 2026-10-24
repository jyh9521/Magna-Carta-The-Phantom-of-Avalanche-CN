#include "damage_projection.h"
#include <iostream>
#include <string>
#include <cstring>
#include <stdexcept>
#include <cmath>
#include <limits>
int checks=0;void check(bool b){++checks;if(!b)throw std::runtime_error("DAMAGE_PROJECTION FAIL check="+std::to_string(checks));}
void jump(BYTE* p,BYTE* to){p[0]=0xe9;*reinterpret_cast<int*>(p+1)=int(to-p-5);}
struct Driver{void** table;BYTE pad[0x58]{};float model[16]{},projection[16]{};};
int rasterCalls=0,floatCalls=0,boolCalls=0;
void __fastcall nopRaster(void*,void*,const float*){++rasterCalls;}
void __fastcall nopFloat(void*,void*,unsigned,float*){++floatCalls;}
void __fastcall nopBool(void*,void*,unsigned,BYTE*){++boolCalls;}
int main(int argc,char** argv){try{
 bool baseline=argc==2&&!strcmp(argv[1],"--baseline");
 BYTE* e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(e!=nullptr);initializeDamageProjectionFixture(e);
 DWORD sites[]={0x474cf,0x474ec,0x47509,0xaa0ba,0xaa398,0xaa629,0xaa916,0xaab88,0xab128,0xab453,0xab6e1,0xaba34,0xc19d8};BYTE original[13][6];for(int i=0;i<13;++i)memcpy(original[i],e+sites[i],6);
 BYTE* driver=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2c000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(driver!=nullptr);
 jump(driver+0x1897c,reinterpret_cast<BYTE*>(&nopRaster));jump(driver+0x80a4,reinterpret_cast<BYTE*>(&nopFloat));jump(driver+0x9b8c,reinterpret_cast<BYTE*>(&nopBool));damageProjectionFixtureDriver(driver);
 void* table[230]{};table[0x394/4]=driver+0x1897c;table[0x1b4/4]=driver+0x80a4;table[0x1a4/4]=driver+0x9b8c;
 Driver d{};d.table=table;static_assert(offsetof(Driver,model)==0x5c);static_assert(offsetof(Driver,projection)==0x9c);
 for(int i=0;i<4;++i)d.model[i*5]=d.projection[i*5]=1;
 // Owned ABI wrappers enter the exact three guarded CALL sites without loading a game DLL.
 BYTE rasterStub[]={0x8b,0x11,0xff,0x74,0x24,0x04};memcpy(e+0x400,rasterStub,6);jump(e+0x406,e+sites[0]);BYTE ret4[]={0xc2,4,0};memcpy(e+sites[0]+6,ret4,3);
 BYTE queryStub[]={0x8b,0x11,0xff,0x74,0x24,0x08,0xff,0x74,0x24,0x08};BYTE ret8[]={0xc2,8,0};
 for(int i=1;i<3;++i){memcpy(e+0x400+i*0x20,queryStub,10);jump(e+0x40a+i*0x20,e+sites[i]);memcpy(e+sites[i]+6,ret8,3);}
 using Raster=void(__thiscall*)(void*,const float*);using Float=void(__thiscall*)(void*,unsigned,float*);using Bool=void(__thiscall*)(void*,unsigned,BYTE*);
 auto raster=reinterpret_cast<Raster>(e+0x400);auto floats=reinterpret_cast<Float>(e+0x420);auto boolean=reinterpret_cast<Bool>(e+0x440);
 for(int i=0;i<13;++i){e[sites[i]]^=1;check(!setDamageProjection(e,0x10b000,true));e[sites[i]]^=1;for(int j=0;j<13;++j)check(!memcmp(e+sites[j],original[j],6));}
 for(int i=0;i<13;++i){damageProjectionWriteFailure(i);check(!setDamageProjection(e,0x10b000,true));for(int j=0;j<13;++j)check(!memcmp(e+sites[j],original[j],6));}
 if(!baseline){check(setDamageProjection(e,0x10b000,true));check(setDamageProjection(e,0x10b000,true));}
 float point[]={.5f,.5f,.5f},out[4]{};BYTE valid=1;*reinterpret_cast<int*>(e+0xf1b48)=800;*reinterpret_cast<int*>(e+0xf1b4c)=600;
 raster(&d,point);floats(&d,0xb07,out);boolean(&d,0xb08,&valid);
 std::cout<<"DAMAGE_POSITION mode="<<(baseline?"BASELINE":"MODIFIED")<<" x="<<out[0]<<" y_top="<<600-out[1]<<" expected=600,150 valid="<<int(valid)<<" game_started=false\n";
 if(baseline)return out[0]==600&&out[1]==450?0:1;
 check(out[0]==600&&out[1]==450&&valid==1);
 for(int width:{640,800,853,1067}){*reinterpret_cast<int*>(e+0xf1b48)=width;raster(&d,point);floats(&d,0xb07,out);check(std::abs(out[0]-width*.75f)<.001f);check(out[1]==450);}
 // Translation, homogeneous divide, clipping and non-finite matrices remain explicit.
 d.model[12]=-.5f;raster(&d,point);floats(&d,0xb07,out);check(std::abs(out[0]-1067*.5f)<.001f);d.model[12]=0;
 d.projection[15]=2;raster(&d,point);floats(&d,0xb07,out);check(std::abs(out[0]-1067*.625f)<.001f);d.projection[15]=1;
 for(float x:{-2.f,2.f,std::numeric_limits<float>::quiet_NaN()}){point[0]=x;raster(&d,point);boolean(&d,0xb08,&valid);check(!valid);}
 // Values independently replayed from the actual driver's x87 RH generator (c765).
 memset(d.projection,0,sizeof(d.projection));d.projection[0]=1.81066012f;d.projection[5]=2.41421342f;d.projection[10]=-1.001001f;d.projection[11]=-1;d.projection[14]=-1.001001f;
 point[0]=1;point[1]=1;point[2]=-5;raster(&d,point);floats(&d,0xb07,out);boolean(&d,0xb08,&valid);check(valid&&std::abs(out[0]-726.69743f)<.002f&&std::abs(out[1]-444.85281f)<.002f);
 for(float z:{-.5f,-1001.f,1.f}){point[2]=z;raster(&d,point);boolean(&d,0xb08,&valid);check(!valid);}
 memset(d.projection,0,sizeof(d.projection));for(int i=0;i<4;++i)d.projection[i*5]=1;
 point[0]=0;point[1]=.5f;point[2]=-.5f;raster(&d,point);boolean(&d,0xb08,&valid);check(!valid);
 float sentinel=123;floats(&d,0xba6,&sentinel);check(sentinel==123&&floatCalls==1);valid=99;boolean(&d,0xb60,&valid);check(valid==99&&boolCalls==1);
 // An unrecognized driver must execute its original raster/query methods.
 table[0x394/4]=nopRaster;raster(&d,point);valid=99;boolean(&d,0xb08,&valid);check(valid==99&&boolCalls==2&&rasterCalls==1);sentinel=123;floats(&d,0xb07,&sentinel);check(sentinel==123&&floatCalls==2);table[0x394/4]=driver+0x1897c;
 check(setDamageProjection(e,0x10b000,false));for(int i=0;i<13;++i)check(!memcmp(e+sites[i],original[i],6));
 memset(out,0,sizeof(out));point[0]=.5f;point[2]=.5f;raster(&d,point);floats(&d,0xb07,out);check(out[0]==0&&out[1]==0);
 VirtualFree(driver,0,MEM_RELEASE);VirtualFree(e,0,MEM_RELEASE);std::cout<<"DAMAGE_PROJECTION_FIXTURE PASS checks="<<checks<<" matrices=current logical_canvas=640,800,853,1067 clip=guarded queries=delegated unknown_driver=passthrough mismatch=rejected write_failure=transactional rollback=exact restored_position=0,600 game_started=false\n";return 0;
}catch(const std::exception& x){std::cerr<<x.what()<<'\n';return 2;}}
