#include "field_return_height.h"
#include <cstdio>
#include <cstring>
#include <cmath>
#include <vector>
namespace {
unsigned checks=0,notices=0;bool baseline=false;
void require(bool ok,const char* text){++checks;if(!ok){printf("FAIL %s\n",text);fflush(stdout);ExitProcess(1);}}
void logger(const wchar_t*){++notices;}
int& n(BYTE* p,unsigned o){return *reinterpret_cast<int*>(p+o);}
BYTE*& ptr(BYTE* p,unsigned o){return *reinterpret_cast<BYTE**>(p+o);}
void __fastcall position(void* a,void*,float x,float y,float z){float p[]={x,y,z};memcpy(static_cast<BYTE*>(a)+0x154,p,12);}
struct Data{
 BYTE* image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
 std::vector<BYTE> data=std::vector<BYTE>(0x10000);
 BYTE *scene=data.data(),*actor=data.data()+0x2000,*dealer=data.data()+0x3000,*plans=data.data()+0x4000,*actions=data.data()+0x5000,*condition=data.data()+0x6000,*slots=data.data()+0xa000,*mover=data.data()+0x8000,*objects=data.data()+0x9000;
 Data(){require(image!=nullptr,"allocation");initializeFieldReturnHeightFixture(image);
  ptr(actor,0)=image+0xc11e4;ptr(actor,0x20)=scene;ptr(scene,0)=image+0xc12bc;ptr(scene,0x3c)=dealer;n(scene,0x10cc)=757;ptr(scene,0x1564)=actor;
  ptr(dealer,0)=image+0xc1320;ptr(dealer,0x54)=scene;ptr(dealer,0x2c)=plans;n(dealer,0x30)=4;ptr(dealer,0x34)=slots;n(dealer,0x38)=150;
  auto plan=plans+112;n(plan,0)=2;n(plan,0x20)=6;n(plan,0x24)=1;ptr(plan,8)=condition;ptr(plan,4)=actions;
  n(condition,0)=304;n(condition,4)=10000;n(condition,8)=1;
  int commands[6][15]{};commands[0][0]=7;commands[1][0]=202;commands[1][1]=10000;commands[1][2]=5;commands[1][3]=1;commands[2][0]=1;
  int talk[]={700,10000,152,0,151,0,-1,1,-1,-1,0,0,0,0,0};memcpy(commands[3],talk,sizeof(talk));commands[4][0]=1;commands[5][0]=8;memcpy(actions,commands,360);
  for(unsigned i=0;i<150;++i)n(slots,i*40)=-1;n(slots,0)=202;n(slots,4)=1;n(slots,8)=2;ptr(slots,0x14)=actions+64;ptr(slots,0x18)=mover;
  ptr(mover,0)=image+0xbea64;float point[]={250.237f,-442.234f,-96.f};memcpy(mover+0x128,point,12);memcpy(mover+0x13c,point,12);
  ptr(scene,0x1518)=objects;n(scene,0x1514)=1;n(objects,0)=5;memcpy(objects+12,point,12);
  // Execute a synthetic caller through the exact production CALL slot. It
  // retains ECX, marshals three floats, and checks both callee/caller cleanup.
  BYTE bridge[]={0x83,0xec,0x0c,0x8b,0x44,0x24,0x10,0x89,0x04,0x24,0x8b,0x44,0x24,0x14,0x89,0x44,0x24,0x04,0x8b,0x44,0x24,0x18,0x89,0x44,0x24,0x08};
  static_assert(sizeof(bridge)==0x75c0a-0x75bf0);memcpy(image+0x75bf0,bridge,sizeof(bridge));
  BYTE cleanup[]={0xc2,0x0c,0};memcpy(image+0x75c0f,cleanup,3);
  BYTE restore[]={0x8b,0xe5,0x5d,0xe9};memcpy(image+0x5a77a,restore,sizeof(restore));
  *reinterpret_cast<DWORD*>(image+0x5a77e)=DWORD(reinterpret_cast<uintptr_t>(&position)-reinterpret_cast<uintptr_t>(image+0x5a782));
  DWORD old;require(VirtualProtect(image+0x75000,0x1000,PAGE_EXECUTE_READWRITE,&old)!=0,"executable synthetic caller");require(VirtualProtect(image+0x5a000,0x1000,PAGE_EXECUTE_READWRITE,&old)!=0,"executable synthetic native setter");FlushInstructionCache(GetCurrentProcess(),image,0x10b000);
  configureFieldReturnHeightFixture(reinterpret_cast<FieldPosition>(image+0x5a773));
 }
 ~Data(){VirtualFree(image,0,MEM_RELEASE);}
 float apply(float stale=-116.4227f){reinterpret_cast<FieldPosition>(image+0x75bf0)(actor,250.237f,-442.234f,stale);return *reinterpret_cast<float*>(actor+0x15c);}
};
}
int wmain(int argc,wchar_t** argv){
 if(argc==3&&!wcscmp(argv[1],L"--image")){
  auto m=LoadLibraryExW(argv[2],nullptr,DONT_RESOLVE_DLL_REFERENCES);require(m!=nullptr,"actual PE loader mapping");auto p=reinterpret_cast<BYTE*>(m);BYTE before[5];memcpy(before,p+0x75c0a,5);
  require(installFieldReturnHeight(m,nullptr),"actual mapped-image install");require(memcmp(before,p+0x75c0a,5)!=0,"actual mapped-image changed call");
  require(removeFieldReturnHeight(m),"actual mapped-image remove");require(memcmp(before,p+0x75c0a,5)==0,"actual mapped-image exact restore");FreeLibrary(m);
  printf("FIELD_RETURN_IMAGE PASS checks=%u commercial_entry_executed=false exact_restore=true\n",checks);return 0;
 }
 baseline=argc==2&&!wcscmp(argv[1],L"--baseline");
 require(argc==1||baseline,"arguments");Data d;auto m=reinterpret_cast<HMODULE>(d.image);
 if(!baseline)require(installFieldReturnHeight(m,logger),"install");
 float end=d.apply();
 if(baseline){printf("FIELD_RETURN_BASELINE field=757 plan=2 xyz=1 expected_z=-96.000000 actual_z=%.6f unlock_path=unchanged\n",double(end));require(end==-96.f,"XYZ return must write interpolator Z");return 0;}
 require(end==-96.f,"XYZ return writes interpolator Z");require(installFieldReturnHeight(m,logger),"idempotent install");
 auto originalState=d.data;d.apply();require(d.data==originalState,"idempotent point does not mutate script or other state");
 // Synthetic boundary conditions exercise the production guard, not a second implementation.
 int* fields[]={&n(d.scene,0x10cc),&n(d.actor,0x328),&n(d.dealer,0x30),&n(d.plans+112,0),&n(d.plans+112,0xc),&n(d.condition,0),&n(d.condition,8),&n(d.actions,60+12),&n(d.slots,8),&n(d.slots,4),&n(d.objects,0)};
 int invalid[]={751,1,3,3,1,100,0,0,1,0,6};
 for(unsigned i=0;i<sizeof(fields)/sizeof(fields[0]);++i){int saved=*fields[i];*fields[i]=invalid[i];require(d.apply()==-116.4227f,"unrelated/unknown context passes original Z");*fields[i]=saved;require(d.apply()==-96.f,"restored exact guard admits correction");}
 n(d.slots,40)=202;n(d.slots,48)=2;ptr(d.slots,60)=d.actions+64;require(d.apply()==-116.4227f,"ambiguous commands do not guess");n(d.slots,40)=-1;
 float* point=reinterpret_cast<float*>(d.mover+0x128);float saved=point[2];point[2]=NAN;require(d.apply()==-116.4227f,"nonfinite interpolation rejected");point[2]=saved;
 float* target=reinterpret_cast<float*>(d.mover+0x13c);target[2]=-95.f;*reinterpret_cast<float*>(d.objects+20)=-95.f;require(d.apply()==-116.4227f,"matching but unknown marker target rejected");target[2]=-96.f;*reinterpret_cast<float*>(d.objects+20)=-96.f;
 // A zero native lock counter is deliberately untouched; this is not a forced unlock.
 n(d.scene,0x1574)=3;d.apply();require(n(d.scene,0x1574)==3,"lock count untouched");
 require(notices<=9,"bounded eight application notices plus readiness");
 BYTE actual[5];memcpy(actual,d.image+0x75c0a,5);d.image[0x75c0a]^=1;require(!removeFieldReturnHeight(m),"foreign call blocks rollback");memcpy(d.image+0x75c0a,actual,5);
 require(removeFieldReturnHeight(m),"remove");require(removeFieldReturnHeight(m),"idempotent remove");require(d.apply()==-116.4227f,"rollback restores original Z behavior");
 d.image[0x7591c]^=1;require(!installFieldReturnHeight(m,nullptr),"unknown instruction prefix rejected");d.image[0x7591c]^=1;
 DWORD old;VirtualProtect(d.image+0x75000,0x1000,PAGE_NOACCESS,&old);require(!installFieldReturnHeight(m,nullptr),"guarded code rejected without read");VirtualProtect(d.image+0x75000,0x1000,old,&old);
 printf("FIELD_RETURN_HEIGHT PASS checks=%u field=757 plan=2 xyz_z=restored call_site_abi=executed other_contexts=unchanged lock_counter=unchanged rollback=exact game_started=false\n",checks);return 0;
}
