#include "wide_ui.h"
#include <iostream>
#include <string>
#include <cstring>
#include <stdexcept>
#include <cmath>
int checks=0;void check(bool b){++checks;if(!b)throw std::runtime_error("wide_ui fixture failure check="+std::to_string(checks));}
int physicalX=0,physicalY=0;BOOL WINAPI fakeWarp(int x,int y){physicalX=x;physicalY=y;return TRUE;}
void branch(BYTE* src,BYTE* dest){src[0]=0xe9;*reinterpret_cast<int*>(src+1)=static_cast<int>(dest-src-5);}
int main(){try{
 BYTE* e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));check(e!=nullptr);initializeWideUiFixture(e);*reinterpret_cast<DWORD*>(e+0xbd3e4)=reinterpret_cast<DWORD>(fakeWarp);

 DWORD sites[]={0x983b,0x99de,0x2dec,0x2ea5,0x2f45,0x7083a,0x70843,0x70cd4,0x70cdd,0xc15b};unsigned lengths[]={5,6,9,6,6,7,7,7,7,6};BYTE original[10][9]{};
 for(unsigned i=0;i<10;++i)memcpy(original[i],e+sites[i],lengths[i]);
 // A corrupt byte at any supported site rejects all writes.
 for(unsigned i=0;i<10;++i){e[sites[i]]^=1;check(!setWideUi(e,0x10b000,true));e[sites[i]]^=1;for(unsigned j=0;j<10;++j)check(memcmp(e+sites[j],original[j],lengths[j])==0);}
 // Owned callable stubs enter exact guarded writes and return at original resume.
 BYTE* a=e+0x400; a[0]=0xb8;*reinterpret_cast<int*>(a+1)=800;branch(a+5,e+0x983b);e[0x9840]=0xc3;
 BYTE* d=e+0x420;d[0]=0xba;*reinterpret_cast<int*>(d+1)=640;branch(d+5,e+0x99de);e[0x99e4]=0xc3;
 using Call=int(__cdecl*)();auto callA=reinterpret_cast<Call>(a);auto callD=reinterpret_cast<Call>(d);
 check(callA()==800);check(*reinterpret_cast<int*>(e+0xf1b48)==800);
 check(!setWideUi(e,5,true));e[0x70843]=0;check(!setWideUi(e,0x10b000,true));check(e[0x983b]==0xa3);e[0x70843]=0xc7;
 for(int fail=0;fail<10;++fail){configureWideUiWriteFailureFixture(fail);check(!setWideUi(e,0x10b000,true));for(unsigned j=0;j<10;++j)check(memcmp(e+sites[j],original[j],lengths[j])==0);}
 check(setWideUi(e,0x10b000,true));check(setWideUi(e,0x10b000,true));check(callA()==800);check(*reinterpret_cast<int*>(e+0xf1b48)==1067);
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
 callD();check(*reinterpret_cast<int*>(e+0xf1b48)==853);check(windowCall()==640);check(compassCall()==753);*reinterpret_cast<int*>(e+0x459)=320;check(inputCall()==427);
 // All originally supported widths preserve physical mouse round trip; unsupported identity.
 *reinterpret_cast<int*>(a+1)=1024;callA();check(*reinterpret_cast<int*>(e+0xf1b48)==1024);*reinterpret_cast<int*>(e+0x459)=512;check(inputCall()==512);
 check(setWideUi(e,0x10b000,false));for(unsigned i=0;i<10;++i)check(memcmp(e+sites[i],original[i],lengths[i])==0);check(e[0x983b]==0xa3&&e[0x99de]==0x89&&e[0x2ea5]==0xff&&e[0x70843]==0xc7);check(*reinterpret_cast<int*>(e+0xf1b48)==1024);
 *reinterpret_cast<int*>(a+1)=800;callA();check(*reinterpret_cast<int*>(e+0xf1b48)==800);VirtualFree(e,0,MEM_RELEASE);
 std::cout<<"WIDE_UI_FIXTURE PASS checks="<<checks<<" widths=853,1067 baseline=unchanged window=physical_original mouse=roundtrip compass=anchored guards=rejected rollback=exact commercial_code_executed=false game_started=false\n";return 0;
}catch(const std::exception& ex){std::cerr<<ex.what()<<'\n';return 1;}}
