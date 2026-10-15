#include "map_overlay.h"
#include <cstdio>
#include <cstring>
#include <limits>
int checks=0;void require(bool b){++checks;if(!b){fprintf(stderr,"MAP_OVERLAY_FAIL check=%d\n",checks);ExitProcess(1);}}
int wmain(int argc,wchar_t** argv){
 if(argc!=1&&argc!=3&&!(argc==4&&!wcscmp(argv[3],L"--mini"))){fprintf(stderr,"MAP_OVERLAY_USAGE_ERROR expected: [ASSETS OUTPUT.png [--mini]]\n");return 2;}
 const bool mini=argc==4;
 MapMetadata m{{'M','C','M','1'},512,512,{10,20,110,120},{12,12},4};float x=0,y=0;require(mapMetadataValid(m));require(mapPixel(m,10,20,x,y)&&x==12&&y==500);require(mapPixel(m,110,120,x,y)&&x==412&&y==100);m.scale=0;require(!mapPixel(m,0,0,x,y));m.scale=4;m.magic[0]='X';require(!mapMetadataValid(m));m.magic[0]='M';require(!mapPixel(m,std::numeric_limits<float>::infinity(),0,x,y));
 BYTE scene[0x15c4]{},actor[0x340]{},level[0x10c]{},brush[0x128]{};int mapId=9;auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(image!=nullptr);mapOverlayTestInitialize(image);*reinterpret_cast<BYTE**>(scene+0x1558)=level;*reinterpret_cast<BYTE**>(level)=image+0xc15ac;*reinterpret_cast<BYTE**>(level+0xf0)=brush;*reinterpret_cast<BYTE**>(brush)=image+0xbdcec;*reinterpret_cast<int**>(brush+0x124)=&mapId;*reinterpret_cast<BYTE**>(scene)=image+0xc12bc;*reinterpret_cast<BYTE**>(actor)=image+0xc11e4;*reinterpret_cast<BYTE**>(actor+0x20)=scene;*reinterpret_cast<BYTE**>(scene+0x1564)=actor;*reinterpret_cast<int*>(scene+0x10d0)=9;float position[]={11,22,33};memcpy(actor+0x154,position,12);
 BYTE npc[0x200]{},chest[0x200]{},nodes[2][8]{};*reinterpret_cast<int*>(npc+4)=0x16a;*reinterpret_cast<int*>(npc+0xf0)=101;*reinterpret_cast<int*>(chest+4)=0x168;*reinterpret_cast<int*>(chest+0xf0)=102;
 float npcPosition[]={-100,250,33},chestPosition[]={-180,320,33};memcpy(npc+0x48,npcPosition,12);memcpy(chest+0x48,chestPosition,12);
 *reinterpret_cast<BYTE**>(nodes[0])=npc;*reinterpret_cast<BYTE**>(nodes[0]+4)=nodes[1];*reinterpret_cast<BYTE**>(nodes[1])=chest;*reinterpret_cast<BYTE**>(scene+0x159c)=nodes[0];
 observeMapWorld(scene,true);auto markers=readMapSnapshot();require(markers.landmarkCount==2&&markers.landmarks[0].id==101&&markers.landmarks[0].kind==1&&markers.landmarks[0].x==-100&&markers.landmarks[1].kind==2);
 *reinterpret_cast<int*>(npc+0xd4)=1;observeMapWorld(scene,true);require(readMapSnapshot().landmarkCount==1);*reinterpret_cast<int*>(npc+0xd4)=0;
 *reinterpret_cast<BYTE**>(nodes[0]+4)=nodes[0];observeMapWorld(scene,true);require(readMapSnapshot().landmarkCount==1);*reinterpret_cast<BYTE**>(nodes[0]+4)=nodes[1];
 *reinterpret_cast<float*>(npc+0x48)=std::numeric_limits<float>::quiet_NaN();observeMapWorld(scene,true);require(readMapSnapshot().landmarkCount==1);memcpy(npc+0x48,npcPosition,12);
 *reinterpret_cast<float*>(actor+0x148)=1;*reinterpret_cast<float*>(actor+0x154)=16;observeMapWorld(scene,true);require(readMapSnapshot().trailCount==2&&readMapSnapshot().directionX==1);
 *reinterpret_cast<float*>(actor+0x154)=300;observeMapWorld(scene,true);require(readMapSnapshot().trailCount==1);memcpy(actor+0x154,position,12);observeMapWorld(scene,true);require(readMapSnapshot().trailCount==1);
 MapView view;require(mapView(m,11,22,true,view));require(mapViewPoint(m,view,11,22,256,x,y)&&x==128&&y==128);require(mapView(m,11,22,false,view)&&view.left==0&&view.top==0&&view.span==512);
 observeMapWorld(scene,true);auto s=readMapSnapshot();require(s.valid&&s.identifier==9&&s.x==11&&s.y==22&&s.z==33);require(!memcmp(actor+0x154,position,12));observeMapWorld(scene,false);require(!readMapSnapshot().valid);*reinterpret_cast<int*>(scene+0x10d0)=-1;observeMapWorld(scene,true);require(!readMapSnapshot().valid);*reinterpret_cast<int*>(scene+0x10d0)=9;*reinterpret_cast<BYTE**>(actor+0x20)=nullptr;observeMapWorld(scene,true);require(!readMapSnapshot().valid);*reinterpret_cast<BYTE**>(actor+0x20)=scene;mapId=10;observeMapWorld(scene,true);require(!readMapSnapshot().valid);mapId=9;
 if(argc>=3){float displayedPlayer[]={-120,260,33};memcpy(actor+0x154,displayedPlayer,12);observeMapWorld(scene,true);for(int i=0;i<8;++i){*reinterpret_cast<float*>(actor+0x154)+=5;observeMapWorld(scene,true);}
  SetEnvironmentVariableW(L"MC_MAP_ASSETS",argv[1]);require(installMapOverlay(reinterpret_cast<HMODULE>(image),nullptr));observeMapWorld(scene,true);require(mapOverlayTestWait());require(mapOverlayTestHiddenWindow());require(mapOverlayTestClickThrough());stopMapOverlay();require(!mapOverlayTestHiddenWindow());SetEnvironmentVariableW(L"MC_MAP_ASSETS",nullptr);
  require(mapOverlayTestRender(argv[1],argv[2],mini));
  printf("MAP_OVERLAY_RENDER PASS mode=%s size=536x584 source=owned_fixture pixels=rendered game_started=false\n",mini?"mini":"large");}
 VirtualFree(image,0,MEM_RELEASE);
 printf("MAP_OVERLAY_FIXTURE PASS checks=%d read_only=true source_coordinates=unchanged metadata_guard=true pixel_alignment=true game_started=false\n",checks);
}
