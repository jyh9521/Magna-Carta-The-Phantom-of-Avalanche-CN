#include "map_overlay.h"
#include <cstdio>
#include <cstring>
#include <limits>
int checks=0;void require(bool b){++checks;if(!b){printf("MAP_OVERLAY_FAIL check=%d\n",checks);ExitProcess(1);}}
int wmain(int argc,wchar_t** argv){MapMetadata m{{'M','C','M','1'},512,512,{10,20,110,120},{12,12},4};float x=0,y=0;require(mapMetadataValid(m));require(mapPixel(m,10,20,x,y)&&x==12&&y==500);require(mapPixel(m,110,120,x,y)&&x==412&&y==100);m.scale=0;require(!mapPixel(m,0,0,x,y));m.scale=4;m.magic[0]='X';require(!mapMetadataValid(m));m.magic[0]='M';require(!mapPixel(m,std::numeric_limits<float>::infinity(),0,x,y));
 BYTE scene[0x1568]{},actor[0x340]{},level[0x10c]{},brush[0x128]{};int mapId=9;auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(image!=nullptr);mapOverlayTestInitialize(image);*reinterpret_cast<BYTE**>(scene+0x1558)=level;*reinterpret_cast<BYTE**>(level)=image+0xc15ac;*reinterpret_cast<BYTE**>(level+0xf0)=brush;*reinterpret_cast<BYTE**>(brush)=image+0xbdcec;*reinterpret_cast<int**>(brush+0x124)=&mapId;*reinterpret_cast<BYTE**>(scene)=image+0xc12bc;*reinterpret_cast<BYTE**>(actor)=image+0xc11e4;*reinterpret_cast<BYTE**>(actor+0x20)=scene;*reinterpret_cast<BYTE**>(scene+0x1564)=actor;*reinterpret_cast<int*>(scene+0x10d0)=9;float position[]={11,22,33};memcpy(actor+0x154,position,12);
 observeMapWorld(scene,true);auto s=readMapSnapshot();require(s.valid&&s.identifier==9&&s.x==11&&s.y==22&&s.z==33);require(!memcmp(actor+0x154,position,12));observeMapWorld(scene,false);require(!readMapSnapshot().valid);*reinterpret_cast<int*>(scene+0x10d0)=-1;observeMapWorld(scene,true);require(!readMapSnapshot().valid);*reinterpret_cast<int*>(scene+0x10d0)=9;*reinterpret_cast<BYTE**>(actor+0x20)=nullptr;observeMapWorld(scene,true);require(!readMapSnapshot().valid);*reinterpret_cast<BYTE**>(actor+0x20)=scene;mapId=10;observeMapWorld(scene,true);require(!readMapSnapshot().valid);mapId=9;
 if(argc>=3){observeMapWorld(scene,true);
  SetEnvironmentVariableW(L"MC_MAP_ASSETS",argv[1]);require(installMapOverlay(reinterpret_cast<HMODULE>(image),nullptr));observeMapWorld(scene,true);require(mapOverlayTestWait());require(mapOverlayTestHiddenWindow());require(mapOverlayTestClickThrough());stopMapOverlay();require(!mapOverlayTestHiddenWindow());SetEnvironmentVariableW(L"MC_MAP_ASSETS",nullptr);
  require(mapOverlayTestRender(argv[1],argv[2]));}
 VirtualFree(image,0,MEM_RELEASE);
 printf("MAP_OVERLAY_FIXTURE PASS checks=%d read_only=true source_coordinates=unchanged metadata_guard=true pixel_alignment=true game_started=false\n",checks);
}
