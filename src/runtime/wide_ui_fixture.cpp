#include "wide_ui.h"
#include <iostream>
#include <string>
#include <cstring>
#include <stdexcept>
#include <cmath>
int checks=0;void check(bool b){++checks;if(!b)throw std::runtime_error("wide_ui fixture failure check="+std::to_string(checks));}
int physicalX=0,physicalY=0;BOOL WINAPI fakeWarp(int x,int y){physicalX=x;physicalY=y;return TRUE;}
DWORD capturedMode[7]{};
void* __cdecl fakeCreate(DWORD* info){memcpy(capturedMode,info,sizeof(capturedMode));return (info[2]==640||info[2]==800)?reinterpret_cast<void*>(0x1234):nullptr;}
void branch(BYTE* src,BYTE* dest){src[0]=0xe9;*reinterpret_cast<int*>(src+1)=static_cast<int>(dest-src-5);}
int battleWidthCheck(){
 BYTE* e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));check(e!=nullptr);initializeWideUiFixture(e);
 *reinterpret_cast<DWORD*>(e+0xbd3e4)=reinterpret_cast<DWORD>(fakeWarp);*reinterpret_cast<DWORD*>(e+0xbd048)=reinterpret_cast<DWORD>(&fakeCreate);
 DWORD rvas[]={0xaefcc,0xaf068};int widths[]={640,800};BYTE originals[2][10]{};
 for(int i=0;i<2;++i){BYTE cmp[]={0x81,0x3d,0,0,0,0,0,0,0,0};*reinterpret_cast<DWORD*>(cmp+2)=reinterpret_cast<DWORD>(e+0xf1b48);*reinterpret_cast<int*>(cmp+6)=widths[i];memcpy(e+rvas[i],cmp,10);memcpy(originals[i],cmp,10);
  // An owned continuation converts the production CMP flags into a result.
  BYTE result[]={0x0f,0x94,0xc0,0x0f,0xb6,0xc0,0xc3};memcpy(e+rvas[i]+10,result,sizeof(result));
 }
 BYTE* a=e+0x400;a[0]=0xb8;*reinterpret_cast<int*>(a+1)=800;branch(a+5,e+0x983b);e[0x9840]=0xc3;
 using Call=int(__cdecl*)();auto store=reinterpret_cast<Call>(a);
 check(setWideUi(e,0x10b000,true));
 for(int physical:{640,800,1024}){*reinterpret_cast<int*>(a+1)=physical;store();int canvas=*reinterpret_cast<int*>(e+0xf1b48);
  for(int i=0;i<2;++i){int selected=reinterpret_cast<Call>(e+rvas[i])();if(selected!=(physical==widths[i])){std::cout<<"BATTLE_WIDTH FAIL physical="<<physical<<" canvas="<<canvas<<" compare="<<widths[i]<<" selected="<<selected<<" expected="<<(physical==widths[i])<<"\n";return 1;}}
  check(*reinterpret_cast<int*>(e+0xf1b48)==canvas);
 }
 check(setWideUi(e,0x10b000,false));for(int i=0;i<2;++i)check(!memcmp(e+rvas[i],originals[i],10));
 for(int i=0;i<2;++i){e[rvas[i]]^=1;check(!setWideUi(e,0x10b000,true));e[rvas[i]]^=1;check(e[0x983b]==0xa3);}
 VirtualFree(e,0,MEM_RELEASE);std::cout<<"BATTLE_WIDTH PASS physical=640,800 virtual=853,1067 unknown=unchanged canvas=preserved guards=rejected rollback=exact game_started=false\n";return 0;
}
int main(int argc,char** argv){try{
 if(argc==2&&!strcmp(argv[1],"--battle-width-check"))return battleWidthCheck();
 BYTE* e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));check(e!=nullptr);initializeWideUiFixture(e);*reinterpret_cast<DWORD*>(e+0xbd3e4)=reinterpret_cast<DWORD>(fakeWarp);*reinterpret_cast<DWORD*>(e+0xbd048)=reinterpret_cast<DWORD>(&fakeCreate);

 DWORD sites[]={0x983b,0x99de,0x2dec,0x2ea5,0x2f45,0x7083a,0x70843,0x70cd4,0x70cdd,0xc15b,0xb95b,0xaefcc,0xaf068};unsigned lengths[]={5,6,9,6,6,7,7,7,7,6,6,10,10};BYTE original[13][10]{};
 for(unsigned i=0;i<13;++i)memcpy(original[i],e+sites[i],lengths[i]);
 // A corrupt byte at any supported site rejects all writes.
 for(unsigned i=0;i<13;++i){e[sites[i]]^=1;check(!setWideUi(e,0x10b000,true));e[sites[i]]^=1;for(unsigned j=0;j<13;++j)check(memcmp(e+sites[j],original[j],lengths[j])==0);}
 // Owned callable stubs enter exact guarded writes and return at original resume.
 BYTE* a=e+0x400; a[0]=0xb8;*reinterpret_cast<int*>(a+1)=800;branch(a+5,e+0x983b);e[0x9840]=0xc3;
 BYTE* d=e+0x420;d[0]=0xba;*reinterpret_cast<int*>(d+1)=640;branch(d+5,e+0x99de);e[0x99e4]=0xc3;
 using Call=int(__cdecl*)();auto callA=reinterpret_cast<Call>(a);auto callD=reinterpret_cast<Call>(d);
 check(callA()==800);check(*reinterpret_cast<int*>(e+0xf1b48)==800);
 check(!setWideUi(e,5,true));e[0x70843]=0;check(!setWideUi(e,0x10b000,true));check(e[0x983b]==0xa3);e[0x70843]=0xc7;
 for(int fail=0;fail<13;++fail){configureWideUiWriteFailureFixture(fail);check(!setWideUi(e,0x10b000,true));for(unsigned j=0;j<13;++j)check(memcmp(e+sites[j],original[j],lengths[j])==0);}
 check(setWideUi(e,0x10b000,true));check(setWideUi(e,0x10b000,true));check(callA()==800);check(*reinterpret_cast<int*>(e+0xf1b48)==1067);
 // Actual engine startup passes a pointer to the entire shared ASRCreateInfo.
 *reinterpret_cast<DWORD*>(e+0xbd048)=reinterpret_cast<DWORD>(&fakeCreate);
 BYTE modeCall[]={0xff,0x15,0,0,0,0};*reinterpret_cast<DWORD*>(modeCall+2)=reinterpret_cast<DWORD>(e+0xbd048);
 // The real callsite remains installed; do not overwrite its hook.
 bool baselineMode=argc==2&&!strcmp(argv[1],"--baseline-mode-check");
 if(baselineMode)memcpy(e+0xb95b,modeCall,sizeof(modeCall));
 BYTE* create=e+0x700;create[0]=0x68;*reinterpret_cast<DWORD*>(create+1)=reinterpret_cast<DWORD>(e+0xf1b40);branch(create+5,e+0xb95b);
 BYTE cleanup[]={0x83,0xc4,0x04,0xc3};memcpy(e+0xb961,cleanup,sizeof(cleanup));
 *reinterpret_cast<DWORD*>(e+0xf1b4c)=600;
 auto createCall=reinterpret_cast<Call>(create);int created=createCall();
 if(!baselineMode){check(created==0x1234);check(capturedMode[2]==800&&capturedMode[3]==600);check(*reinterpret_cast<int*>(e+0xf1b48)==1067);}
 if(baselineMode||(argc==2&&!strcmp(argv[1],"--mode-check"))){
  std::cout<<"DISPLAY_MODE_REQUEST width="<<capturedMode[2]<<" height="<<capturedMode[3]<<" ui_width="<<*reinterpret_cast<int*>(e+0xf1b48)<<" result="<<(created?"SUPPORTED":"DDERR_UNSUPPORTED")<<" commercial_code_executed=false\n";
  return created?0:1;
 }
 // CreateWindow virtual dimensions remain original, independently of expanded UI width.
 branch(e+0x500,e+0xc15b);e[0xc161]=0x8b;e[0xc162]=0xc1;e[0xc163]=0xc3;auto windowCall=reinterpret_cast<Call>(e+0x500);check(windowCall()==800);
 // Frame stub contains poll x local and returns stored x in ECX.
 BYTE input[]={0x55,0x8b,0xec,0x83,0xec,0x08,0xc7,0x45,0xf8,0,0,0,0,0xe9,0,0,0,0};
 memcpy(e+0x450,input,sizeof(input));branch(e+0x45d,e+0x2dec);e[0x2df5]=0x8b;e[0x2df6]=0xc1;e[0x2df7]=0xc9;e[0x2df8]=0xc3;auto inputCall=reinterpret_cast<Call>(e+0x450);
 for(int x:{0,100,400,799,800}){*reinterpret_cast<int*>(e+0x459)=x;int mapped=inputCall();check(mapped==static_cast<int>(std::lround(x*1067.0/800)));check(*reinterpret_cast<int*>(e+0xf20b0)==mapped);}
 // Actual patched call site dispatches the inverse warp and preserves WINAPI result.
 BYTE warp[]={0x55,0x8b,0xec,0x83,0xec,0x08,0xc7,0x45,0xf8,0,0,0,0,0x6a,0x2a,0x68,0,0,0,0,0xe9,0,0,0,0};memcpy(e+0x480,warp,sizeof(warp));branch(e+0x494,e+0x2ea5);e[0x2eab]=0xc9;e[0x2eac]=0xc3;auto warpCall=reinterpret_cast<Call>(e+0x480);
 for(int origin:{0,100,-250})for(int x:{0,100,400,799,800}){*reinterpret_cast<int*>(e+0x489)=origin;*reinterpret_cast<int*>(e+0x490)=origin+static_cast<int>(std::lround(x*1067.0/800));check(warpCall()==TRUE);check(physicalX==origin+x&&physicalY==42);}
 memcpy(e+0x600,warp,sizeof(warp));branch(e+0x614,e+0x2f45);e[0x2f4b]=0xc9;e[0x2f4c]=0xc3;auto centerCall=reinterpret_cast<Call>(e+0x600);
 for(int origin:{0,100,-250}){*reinterpret_cast<int*>(e+0x609)=origin+533;*reinterpret_cast<int*>(e+0x610)=origin+533;check(centerCall()==TRUE);check(physicalX==origin+400&&physicalY==42);}
 // Compass original local coordinates are moved to canvaswidth-100 in both init/update paths.
 BYTE compass[]={0x55,0x8b,0xec,0x83,0xec,0x20,0xe9,0,0,0,0};memcpy(e+0x4c0,compass,sizeof(compass));branch(e+0x4c6,e+0x70843);BYTE ret[]={0xd9,0x45,0xf0,0xc9,0xc3};memcpy(e+0x7084a,ret,sizeof(ret));using FloatCall=float(__cdecl*)();auto compassCall=reinterpret_cast<FloatCall>(e+0x4c0);check(compassCall()==967);
 callD();check(createCall()==0x1234);check(capturedMode[2]==640);check(*reinterpret_cast<int*>(e+0xf1b48)==853);check(windowCall()==640);check(compassCall()==753);*reinterpret_cast<int*>(e+0x459)=320;check(inputCall()==427);
 // All originally supported widths preserve physical mouse round trip; unsupported identity.
 *reinterpret_cast<int*>(a+1)=1024;callA();check(*reinterpret_cast<int*>(e+0xf1b48)==1024);*reinterpret_cast<int*>(e+0x459)=512;check(inputCall()==512);
 check(setWideUi(e,0x10b000,false));for(unsigned i=0;i<13;++i)check(memcmp(e+sites[i],original[i],lengths[i])==0);check(e[0x983b]==0xa3&&e[0x99de]==0x89&&e[0x2ea5]==0xff&&e[0x70843]==0xc7);check(*reinterpret_cast<int*>(e+0xf1b48)==1024);
 *reinterpret_cast<int*>(a+1)=800;callA();check(*reinterpret_cast<int*>(e+0xf1b48)==800);VirtualFree(e,0,MEM_RELEASE);
 std::cout<<"WIDE_UI_FIXTURE PASS checks="<<checks<<" widths=853,1067 baseline=unchanged window=physical_original mouse=roundtrip display_mode=physical_original compass=anchored guards=rejected rollback=exact commercial_code_executed=false game_started=false\n";return 0;
}catch(const std::exception& ex){std::cerr<<ex.what()<<'\n';return 1;}}
