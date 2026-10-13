#include "title_layout.h"
#include <iostream>
#include <stdexcept>
#include <string>
#include <cstring>
unsigned checks=0;void check(bool b){++checks;if(!b)throw std::runtime_error("title fixture check="+std::to_string(checks));}
void jump(BYTE* p,BYTE* to){p[0]=0xe9;*reinterpret_cast<int*>(p+1)=static_cast<int>(to-p-5);}
int pointX=-1,pointY=-1;
int* __fastcall point(int* p,void*,int x,int y){pointX=x;pointY=y;return p;}
int main(int argc,char** argv){try{
 BYTE* e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(e);initializeTitleLayoutFixture(e);
 DWORD sites[]={0xb6c96,0xb79a1,0xb79d9,0xb6ce7};unsigned lengths[]={10,10,5,5};BYTE before[4][10]{};for(unsigned i=0;i<4;++i)memcpy(before[i],e+sites[i],lengths[i]);
 using Call=int(__cdecl*)();BYTE result[]={0x0f,0x9d,0xc0,0x0f,0xb6,0xc0,0xc3};
 jump(e+0x400,e+0xb6c96);memcpy(e+0xb6ca0,result,sizeof(result));auto bg=reinterpret_cast<Call>(e+0x400);
 jump(e+0x420,e+0xb79a1);memcpy(e+0xb79ab,result,sizeof(result));auto menu=reinterpret_cast<Call>(e+0x420);
 *reinterpret_cast<int*>(e+0xf1b48)=853;check(bg()==1&&menu()==1);
 if(argc==2&&!strcmp(argv[1],"--baseline-check")){std::cout<<"TITLE_LAYOUT_BASELINE FAIL canvas=853 selected_layout=800x600 exit_bottom=501 screen_height=480 result=CLIPPED commercial_code_executed=false\n";return 1;}
 for(unsigned i=0;i<4;++i){e[sites[i]]^=1;check(!setTitleLayout(e,0x10b000,true));e[sites[i]]^=1;for(unsigned j=0;j<4;++j)check(!memcmp(e+sites[j],before[j],lengths[j]));}
 check(setTitleLayout(e,0x10b000,true));check(setTitleLayout(e,0x10b000,true));check(bg()==0&&menu()==0);check(*reinterpret_cast<int*>(e+0xf1b48)==853);
 // Owned frame-local point: the hook adds only horizontal centering to first X.
 BYTE button[]={0x55,0x8b,0xec,0x83,0xec,0x18,0xc7,0x45,0xe8,0x05,0x01,0,0,0xe9,0,0,0,0};memcpy(e+0x450,button,sizeof(button));jump(e+0x45d,e+0xb79d9);
 BYTE after[]={0x83,0xc4,0x04,0x8b,0x45,0xe8,0xc9,0xc3};memcpy(e+0xb79de,after,sizeof(after));auto buttonCall=reinterpret_cast<Call>(e+0x450);check(buttonCall()==368);
 // Background point preserves argument order, stack and original 4:3 art size.
 BYTE background[]={0x55,0x8b,0xec,0x83,0xec,0x7c,0x6a,0,0xe9,0,0,0,0};memcpy(e+0x500,background,sizeof(background));jump(e+0x508,e+0xb6ce7);
 e[0xb6cec]=0xe8;*reinterpret_cast<int*>(e+0xb6ced)=static_cast<int>(reinterpret_cast<ULONG_PTR>(&point)-reinterpret_cast<ULONG_PTR>(e+0xb6cf1));e[0xb6cf1]=0xc9;e[0xb6cf2]=0xc3;auto bgCall=reinterpret_cast<Call>(e+0x500);bgCall();check(pointX==107&&pointY==0);
 check(292+3*30+34<=480);check(107+640<=853); // Full buttons and undistorted centered panel.
 configureTitleLayoutFixture(800,1067);*reinterpret_cast<int*>(e+0xf1b48)=1067;check(bg()==1&&menu()==1);bgCall();check(pointX==134&&pointY==0);check(buttonCall()==395);check(362+3*35+34<=600);
 configureTitleLayoutFixture(640,640);*reinterpret_cast<int*>(e+0xf1b48)=640;check(bg()==0&&menu()==0);bgCall();check(pointX==0);check(buttonCall()==261);
 check(setTitleLayout(e,0x10b000,false));for(unsigned i=0;i<4;++i)check(!memcmp(e+sites[i],before[i],lengths[i]));*reinterpret_cast<int*>(e+0xf1b48)=853;check(bg()==1&&menu()==1);check(buttonCall()==261);bgCall();check(pointX==0);
 VirtualFree(e,0,MEM_RELEASE);std::cout<<"TITLE_LAYOUT_FIXTURE PASS checks="<<checks<<" physical_art_selection=true buttons=inside_height centered_panel=aspect_preserved game_canvas=unchanged rollback=exact commercial_code_executed=false game_started=false\n";return 0;
}catch(const std::exception& ex){std::cerr<<ex.what()<<'\n';return 1;}}
