#include "title_layout.h"
#include <iostream>
#include <stdexcept>
#include <string>
#include <cstring>
#include <cmath>
unsigned checks=0;void check(bool b){++checks;if(!b)throw std::runtime_error("title fixture check="+std::to_string(checks));}
void jump(BYTE* p,BYTE* to){p[0]=0xe9;*reinterpret_cast<int*>(p+1)=static_cast<int>(to-p-5);}
int pointX=-1,pointY=-1;
int* __fastcall point(int* p,void*,int x,int y){pointX=x;pointY=y;return p;}
float tileX=0,tileY=0,tileZ=0;
BYTE tileNode[0x174]{};
void __fastcall tilePosition(void*,void*,float x,float y,float z){tileX=x;tileY=y;tileZ=z;}
int main(int argc,char** argv){try{
 BYTE* e=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(e);initializeTitleLayoutFixture(e);
 DWORD sites[]={0xb6c96,0xb79a1,0xb79d9,0x4e370};unsigned lengths[]={10,10,5,5};BYTE before[4][10]{};for(unsigned i=0;i<4;++i)memcpy(before[i],e+sites[i],lengths[i]);
 using Call=int(__cdecl*)();BYTE result[]={0x0f,0x9d,0xc0,0x0f,0xb6,0xc0,0xc3};
 jump(e+0x400,e+0xb6c96);memcpy(e+0xb6ca0,result,sizeof(result));auto bg=reinterpret_cast<Call>(e+0x400);
 jump(e+0x420,e+0xb79a1);memcpy(e+0xb79ab,result,sizeof(result));auto menu=reinterpret_cast<Call>(e+0x420);
 *reinterpret_cast<int*>(e+0xf1b48)=853;check(bg()==1&&menu()==1);
 if(argc==2&&!strcmp(argv[1],"--baseline-check")){std::cout<<"TITLE_LAYOUT_BASELINE FAIL canvas=853 selected_layout=800x600 exit_bottom=501 screen_height=480 result=CLIPPED commercial_code_executed=false\n";return 1;}
 if(argc==2&&!strcmp(argv[1],"--tile-baseline-check")){
  BYTE originalCall[]={0xe8,0x7b,0xf0,0xff,0xff};memcpy(e+0x4e370,originalCall,5);
  check(setTitleLayout(e,0x10b000,true));
  BYTE frame[]={0x55,0x8b,0xec,0xff,0x75,0x14,0xff,0x75,0x0c,0xff,0x75,0x08,0xe9,0,0,0,0};memcpy(e+0x500,frame,sizeof(frame));jump(e+0x50c,e+0x4e370);
  jump(e+0x4d3f0,reinterpret_cast<BYTE*>(&tilePosition));e[0x4e375]=0xc9;e[0x4e376]=0xc3;
  reinterpret_cast<void(__cdecl*)(float,float,int,float)>(e+0x500)(0.f,0.f,209,0.f);
  std::cout<<"TITLE_TILE_REPLAY "<<(tileX==107.f?"PASS":"FAIL")<<" child_x="<<tileX<<" expected=107 game_started=false\n";return tileX==107.f?0:1;
 }
 for(unsigned i=0;i<4;++i){e[sites[i]]^=1;check(!setTitleLayout(e,0x10b000,true));e[sites[i]]^=1;for(unsigned j=0;j<4;++j)check(!memcmp(e+sites[j],before[j],lengths[j]));}
 check(setTitleLayout(e,0x10b000,true));check(setTitleLayout(e,0x10b000,true));check(bg()==0&&menu()==0);check(*reinterpret_cast<int*>(e+0xf1b48)==853);
 // Owned frame-local point: the hook adds only horizontal centering to first X.
 BYTE button[]={0x55,0x8b,0xec,0x83,0xec,0x18,0xc7,0x45,0xe8,0x05,0x01,0,0,0xe9,0,0,0,0};memcpy(e+0x450,button,sizeof(button));jump(e+0x45d,e+0xb79d9);
 BYTE after[]={0x83,0xc4,0x04,0x8b,0x45,0xe8,0xc9,0xc3};memcpy(e+0xb79de,after,sizeof(after));auto buttonCall=reinterpret_cast<Call>(e+0x450);check(buttonCall()==368);
 // Replay final child-vector setter: the constructor's parent point is not inherited.
 BYTE tileFrame[]={0x55,0x8b,0xec,0xff,0x75,0x14,0xff,0x75,0x0c,0xff,0x75,0x08,0xe9,0,0,0,0};
 memcpy(e+0x500,tileFrame,12);e[0x50c]=0xb9;*reinterpret_cast<DWORD*>(e+0x50d)=reinterpret_cast<DWORD>(tileNode);jump(e+0x511,e+0x4e370);
 jump(e+0x4d3f0,reinterpret_cast<BYTE*>(&tilePosition));e[0x4e375]=0xc9;e[0x4e376]=0xc3;
 using Tile=void(__cdecl*)(float,float,int,float);auto tile=reinterpret_cast<Tile>(e+0x500);
 for(int id:{209,210})for(float x:{0.f,256.f,512.f}){tile(x,240.f,id,7.f);check(tileX==x+107.f&&tileY==240.f&&tileZ==7.f);}
 tile(17.f,31.f,208,9.f);check(tileX==17.f&&tileY==31.f&&tileZ==9.f);
 check(292+3*30+34<=480);check(107+640<=853);
 configureTitleLayoutFixture(800,1067);*reinterpret_cast<int*>(e+0xf1b48)=1067;check(bg()==1&&menu()==1);tile(256.f,0.f,210,3.f);check(tileX==390.f&&tileY==0.f&&tileZ==3.f);check(buttonCall()==395);check(362+3*35+34<=600);
 configureTitleLayoutFixture(640,640);*reinterpret_cast<int*>(e+0xf1b48)=640;check(bg()==0&&menu()==0);tile(256.f,0.f,209,0.f);check(tileX==256.f);check(buttonCall()==261);
 configureTitleLayoutFixture(640,853);configureTitleBackgroundFixture(true);
 for(int id:{209,210})for(float x:{0.f,256.f,512.f}){
  tile(x,256.f,id,7.f);check(abs(tileX-x*5.f*(640.f/2880.f))<0.001f&&tileY==240.f&&tileZ==7.f);
  auto scale=reinterpret_cast<float*>(tileNode+0x40);check(scale[0]==640.f/2880.f&&scale[1]==scale[0]);
 }
 tile(17.f,31.f,208,9.f);check(tileX==17.f&&tileY==31.f&&tileZ==9.f);
 configureTitleLayoutFixture(800,1067);tile(256.f,256.f,210,5.f);check(abs(tileX-355.55556f)<0.001f&&tileY==300.f&&tileZ==5.f);
 configureTitleLayoutFixture(640,640);tile(0.f,0.f,209,7.f);check(abs(tileX+106.66667f)<0.001f&&tileY==0.f);
 configureTitleLayoutFixture(800,800);tile(0.f,0.f,210,7.f);check(abs(tileX+133.33333f)<0.001f&&tileY==0.f);
 configureTitleBackgroundFixture(false);
 check(setTitleLayout(e,0x10b000,false));for(unsigned i=0;i<4;++i)check(!memcmp(e+sites[i],before[i],lengths[i]));*reinterpret_cast<int*>(e+0xf1b48)=853;check(bg()==1&&menu()==1);check(buttonCall()==261);tile(256.f,0.f,209,0.f);check(tileX==256.f);
 VirtualFree(e,0,MEM_RELEASE);std::cout<<"TITLE_LAYOUT_FIXTURE PASS checks="<<checks<<" physical_art_selection=true buttons=inside_height tile_vectors=centered_and_seam_contiguous game_canvas=unchanged rollback=exact commercial_code_executed=false game_started=false\n";return 0;
}catch(const std::exception& ex){std::cerr<<ex.what()<<'\n';return 1;}}
