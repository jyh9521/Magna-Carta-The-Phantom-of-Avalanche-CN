#include "map_overlay.h"
#include <cstdio>
#include <cstring>
#include <limits>
#include <utility>
#include <initializer_list>
#include <cmath>
int checks=0;void require(bool b){++checks;if(!b){fprintf(stderr,"MAP_OVERLAY_FAIL check=%d\n",checks);ExitProcess(1);}}
int wmain(int argc,wchar_t** argv){
 const bool cycleOnly=argc==2&&!wcscmp(argv[1],L"--cycle-self-test");
 const bool pointsOnly=argc==3&&!wcscmp(argv[1],L"--points-self-test");
 const bool rewards=argc==4&&!wcscmp(argv[3],L"--mini-rewards"),collected=argc==4&&!wcscmp(argv[3],L"--mini-collected");
 const wchar_t* headingFlags[]={L"--mini-east",L"--mini-north",L"--mini-west",L"--mini-south"};int headingIndex=-1;
 if(argc==4)for(int i=0;i<4;++i)if(!wcscmp(argv[3],headingFlags[i]))headingIndex=i;
 if(argc!=1&&!cycleOnly&&argc!=3&&!(argc==4&&(!wcscmp(argv[3],L"--mini")||!wcscmp(argv[3],L"--full")||headingIndex>=0||rewards||collected))){fprintf(stderr,"MAP_OVERLAY_USAGE_ERROR expected: [ASSETS OUTPUT.png [--mini|--full|--mini-east|--mini-north|--mini-west|--mini-south|--mini-rewards|--mini-collected]] or --cycle-self-test\n");return 2;}
 const bool mini=rewards||collected||headingIndex>=0||(argc==4&&!wcscmp(argv[3],L"--mini")),full=argc==4&&!wcscmp(argv[3],L"--full");
 const float headings[4][3]={{1,0,0},{0,1,0},{-1,0,0},{0,-1,0}};
 MapDisplayState display;require(display.mode==MapDisplayMode::Off);
 require(mapDisplayStep(display,true,true)==MapDisplayMode::Off); // Startup key must first be released.
 require(mapDisplayStep(display,true,false)==MapDisplayMode::Off);
 require(mapDisplayStep(display,true,true)==MapDisplayMode::Mini);
 for(int i=0;i<30;++i)require(mapDisplayStep(display,true,true)==MapDisplayMode::Mini);
 require(mapDisplayStep(display,true,false)==MapDisplayMode::Mini);
 require(mapDisplayStep(display,true,true)==MapDisplayMode::Full);
 require(mapDisplayStep(display,true,false)==MapDisplayMode::Full);
 require(mapDisplayStep(display,true,true)==MapDisplayMode::Off);
 mapDisplayStep(display,true,false);require(mapDisplayStep(display,true,true)==MapDisplayMode::Mini);
 require(mapDisplayStep(display,false,false)==MapDisplayMode::Off&&display.mode==MapDisplayMode::Mini);
 require(mapDisplayStep(display,false,true)==MapDisplayMode::Off&&display.mode==MapDisplayMode::Mini);
 require(mapDisplayStep(display,true,true)==MapDisplayMode::Mini); // Refocus held key never advances.
 require(mapDisplayStep(display,true,true)==MapDisplayMode::Mini);
 mapDisplayStep(display,true,false);require(mapDisplayStep(display,true,true)==MapDisplayMode::Full);
 mapDisplayStep(display,false,false);require(mapDisplayStep(display,true,false)==MapDisplayMode::Full);
 require(mapDisplayStep(display,true,true)==MapDisplayMode::Off);
 MapOverlayLayout layout;
 require(!mapOverlayLayout(1920,1080,MapDisplayMode::Off,layout));
 require(!mapOverlayLayout(0,1080,MapDisplayMode::Full,layout));
 require(!mapOverlayLayout(1920,0,MapDisplayMode::Mini,layout));
 for(auto dimensions:{std::pair<int,int>{1280,720},{1920,1080},{3840,2160},{1080,1920}}){
  require(mapOverlayLayout(dimensions.first,dimensions.second,MapDisplayMode::Full,layout)&&layout.x==0&&layout.y==0&&layout.width==dimensions.first&&layout.height==dimensions.second);
  require(mapOverlayLayout(dimensions.first,dimensions.second,MapDisplayMode::Mini,layout)&&layout.x>=0&&layout.y>=0&&layout.x+layout.width<=dimensions.first&&layout.y+layout.height<=dimensions.second&&layout.width<=dimensions.first/3);
 }
 require(mapOverlayOpacity(MapDisplayMode::Full)==150&&mapOverlayOpacity(MapDisplayMode::Mini)==235);
 if(cycleOnly){printf("MAP_F9_CYCLE_V1 PASS checks=%d cycle=off_mini_full_off held_key=single_edge inactive=hidden release_to_rearm=true full_layout=client opacity=150 game_started=false\n",checks);return 0;}
 MapPointHeader pointHeader{{'M','C','P','1'},29,9,1};MapExitPoint exitPoint{0,1,30,9,1,0,-140,280,33};
 require(mapPointAssetValid(pointHeader,&exitPoint,sizeof(pointHeader)+sizeof(exitPoint),29,9));
 require(!mapPointAssetValid(pointHeader,&exitPoint,sizeof(pointHeader)+sizeof(exitPoint)-1,29,9));require(!mapPointAssetValid(pointHeader,&exitPoint,sizeof(pointHeader)+sizeof(exitPoint),30,9));require(!mapPointAssetValid(pointHeader,&exitPoint,sizeof(pointHeader)+sizeof(exitPoint),29,10));
 exitPoint.flags=4;require(!mapPointAssetValid(pointHeader,&exitPoint,sizeof(pointHeader)+sizeof(exitPoint),29,9));exitPoint.flags=0;exitPoint.x=std::numeric_limits<float>::quiet_NaN();require(!mapPointAssetValid(pointHeader,&exitPoint,sizeof(pointHeader)+sizeof(exitPoint),29,9));exitPoint.x=-140;
 MapSnapshot pointPlayer;pointPlayer.valid=true;pointPlayer.actorIdentifier=1;require(mapExitApplies(exitPoint,pointPlayer));pointPlayer.actorIdentifier=2;require(!mapExitApplies(exitPoint,pointPlayer));pointPlayer.actorIdentifier=-1;require(!mapExitApplies(exitPoint,pointPlayer));
 if(pointsOnly){require(mapOverlayTestLoadPoints(argv[2],29,9)==3);require(mapOverlayTestPoint(0).x==-140&&mapOverlayTestPoint(0).triggerActor==1&&mapOverlayTestPoint(1).flags==1&&mapOverlayTestPoint(2).triggerActor==2);for(int id=30;id<=36;++id)require(mapOverlayTestLoadPoints(argv[2],id,9)==0);require(mapOverlayTestLoadPoints(argv[2],29,10)==0);require(mapOverlayTestLoadPoints(argv[2],29,9)==3);require(mapOverlayTestLoadPoints(argv[2],-1,9)==0);printf("MAP_POINTS_GUARD PASS format=MCP1 row_bytes=36 exact_size=true finite=true count_bound=64 field_map_match=true same_map_field_clear=true actor_match=true game_started=false\n");return 0;}
 MapMetadata m{{'M','C','M','1'},512,512,{10,20,110,120},{12,12},4};float x=0,y=0;require(mapMetadataValid(m));require(mapPixel(m,10,20,x,y)&&x==12&&y==500);require(mapPixel(m,110,120,x,y)&&x==412&&y==100);m.scale=0;require(!mapPixel(m,0,0,x,y));m.scale=4;m.magic[0]='X';require(!mapMetadataValid(m));m.magic[0]='M';require(!mapPixel(m,std::numeric_limits<float>::infinity(),0,x,y));
 BYTE scene[0x15c4]{},actor[0x340]{},level[0x10c]{},brush[0x128]{};int mapId=9;auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(image!=nullptr);mapOverlayTestInitialize(image);*reinterpret_cast<BYTE**>(scene+0x1558)=level;*reinterpret_cast<BYTE**>(level)=image+0xc15ac;*reinterpret_cast<BYTE**>(level+0xf0)=brush;*reinterpret_cast<BYTE**>(brush)=image+0xbdcec;*reinterpret_cast<int**>(brush+0x124)=&mapId;*reinterpret_cast<BYTE**>(scene)=image+0xc12bc;*reinterpret_cast<BYTE**>(actor)=image+0xc11e4;*reinterpret_cast<BYTE**>(actor+0x20)=scene;*reinterpret_cast<BYTE**>(scene+0x1564)=actor;*reinterpret_cast<int*>(scene+0x10d0)=9;float position[]={11,22,33};memcpy(actor+0x154,position,12);
 *reinterpret_cast<int*>(scene+0x10cc)=29;*reinterpret_cast<int*>(actor+0x328)=1;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->FileHeader.TimeDateStamp=0x3ed73966;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 BYTE records[2*0x48]{},manager[0x2c]{};int switches[2000]{};*reinterpret_cast<BYTE**>(scene+0x1518)=records;*reinterpret_cast<int*>(scene+0x1514)=2;*reinterpret_cast<BYTE**>(image+0xf2304)=manager;*reinterpret_cast<BYTE**>(manager)=image+0xbe774;*reinterpret_cast<int**>(manager+0x24)=switches;*reinterpret_cast<int*>(manager+0x28)=2000;
 *reinterpret_cast<int*>(records)=101;*reinterpret_cast<int*>(records+8)=3;*reinterpret_cast<short*>(records+0x24)=-1;*reinterpret_cast<short*>(records+0x26)=1;*reinterpret_cast<int*>(records+0x48)=102;*reinterpret_cast<int*>(records+0x48+8)=6;*reinterpret_cast<short*>(records+0x48+0x26)=0;
 BYTE npc[0x200]{},chest[0x200]{},nodes[2][8]{};*reinterpret_cast<int*>(npc+4)=0x16a;*reinterpret_cast<int*>(npc+0xf0)=101;*reinterpret_cast<int*>(chest+4)=0x168;*reinterpret_cast<int*>(chest+0xf0)=102;
 float npcPosition[]={-100,250,33},chestPosition[]={-180,320,33};memcpy(npc+0x48,npcPosition,12);memcpy(chest+0x48,chestPosition,12);
 *reinterpret_cast<BYTE**>(nodes[0])=npc;*reinterpret_cast<BYTE**>(nodes[0]+4)=nodes[1];*reinterpret_cast<BYTE**>(nodes[1])=chest;*reinterpret_cast<BYTE**>(scene+0x159c)=nodes[0];
 *reinterpret_cast<int*>(image+0xf1b4c)=600;observeMapWorld(scene,true);require(readMapSnapshot().uiHeight==600);*reinterpret_cast<int*>(image+0xf1b4c)=-1;observeMapWorld(scene,true);require(readMapSnapshot().uiHeight==480);*reinterpret_cast<int*>(image+0xf1b4c)=0;
 observeMapWorld(scene,true);auto markers=readMapSnapshot();require(markers.landmarkCount==2&&markers.landmarks[0].id==101&&markers.landmarks[0].kind==1&&markers.landmarks[0].x==-100&&markers.landmarks[1].kind==2);
 require(markers.landmarks[0].collectible==MapCollectibleState::NoReward&&markers.landmarks[1].collectible==MapCollectibleState::ContainerAvailable);
 switches[0]=2;observeMapWorld(scene,true);require(readMapSnapshot().landmarkCount==1);switches[0]=0;
 *reinterpret_cast<short*>(records+0x48+0x26)=-1;observeMapWorld(scene,true);require(readMapSnapshot().landmarkCount==2&&readMapSnapshot().landmarks[1].collectible==MapCollectibleState::Unknown);*reinterpret_cast<short*>(records+0x48+0x26)=0;
 *reinterpret_cast<short*>(records+0x24)=42;observeMapWorld(scene,true);require(readMapSnapshot().landmarks[0].collectible==MapCollectibleState::NpcReward);switches[1]=1;observeMapWorld(scene,true);require(readMapSnapshot().landmarks[0].collectible==MapCollectibleState::NoReward);switches[1]=0;*reinterpret_cast<short*>(records+0x24)=-1;
 require(markers.fieldIdentifier==29&&markers.identifier==9&&markers.actorIdentifier==1);
 *reinterpret_cast<int*>(actor+0x328)=-1;observeMapWorld(scene,true);require(readMapSnapshot().valid&&readMapSnapshot().actorIdentifier==-1);*reinterpret_cast<int*>(actor+0x328)=10000;observeMapWorld(scene,true);require(readMapSnapshot().valid&&readMapSnapshot().actorIdentifier==-1);*reinterpret_cast<int*>(actor+0x328)=1;
 *reinterpret_cast<int*>(scene+0x10cc)=-1;observeMapWorld(scene,true);require(readMapSnapshot().valid&&readMapSnapshot().fieldIdentifier==-1);*reinterpret_cast<int*>(scene+0x10cc)=10000;observeMapWorld(scene,true);require(readMapSnapshot().valid&&readMapSnapshot().fieldIdentifier==-1);*reinterpret_cast<int*>(scene+0x10cc)=29;
 for(int frame=1;frame<=4;++frame){float moved[]={npcPosition[0]+frame*7.f,npcPosition[1]-frame*3.f,npcPosition[2]};memcpy(npc+0x48,moved,sizeof(moved));observeMapWorld(scene,true);auto live=readMapSnapshot();require(live.landmarks[0].x==moved[0]&&live.landmarks[0].y==moved[1]&&live.landmarks[0].kind==1);require(!memcmp(npc+0x48,moved,sizeof(moved)));}memcpy(npc+0x48,npcPosition,12);
 *reinterpret_cast<int*>(npc+0xd4)=1;observeMapWorld(scene,true);require(readMapSnapshot().landmarkCount==1);*reinterpret_cast<int*>(npc+0xd4)=0;
 *reinterpret_cast<BYTE**>(nodes[0]+4)=nodes[0];observeMapWorld(scene,true);require(readMapSnapshot().landmarkCount==1);*reinterpret_cast<BYTE**>(nodes[0]+4)=nodes[1];
 *reinterpret_cast<float*>(npc+0x48)=std::numeric_limits<float>::quiet_NaN();observeMapWorld(scene,true);require(readMapSnapshot().landmarkCount==1);memcpy(npc+0x48,npcPosition,12);
 *reinterpret_cast<float*>(actor+0x148)=1;*reinterpret_cast<float*>(actor+0x154)=16;observeMapWorld(scene,true);require(readMapSnapshot().trailCount==2&&readMapSnapshot().directionX==1);
 *reinterpret_cast<float*>(actor+0x154)=300;observeMapWorld(scene,true);require(readMapSnapshot().trailCount==1);memcpy(actor+0x154,position,12);observeMapWorld(scene,true);require(readMapSnapshot().trailCount==1);
 for(const auto& direction:headings){memcpy(actor+0x148,direction,sizeof(direction));observeMapWorld(scene,true);auto turn=readMapSnapshot();require(turn.x==position[0]&&turn.y==position[1]&&turn.trailCount==1&&turn.directionX==direction[0]&&turn.directionY==direction[1]);float sx=0,sy=0;require(mapPlayerHeading(turn.directionX,turn.directionY,sx,sy)&&sx==direction[0]&&sy==-direction[1]);require(!memcmp(actor+0x148,direction,sizeof(direction))&&!memcmp(actor+0x154,position,12));}
 float sx=0,sy=0;require(mapPlayerHeading(3,4,sx,sy)&&std::abs(sx-.6f)<.00001f&&std::abs(sy+.8f)<.00001f);require(!mapPlayerHeading(0,0,sx,sy));require(!mapPlayerHeading(std::numeric_limits<float>::quiet_NaN(),0,sx,sy));
 memcpy(actor+0x148,headings[0],12);float movedPlayer[]={21,27,33};memcpy(actor+0x154,movedPlayer,12);observeMapWorld(scene,true);auto moved=readMapSnapshot();require(moved.x==21&&moved.y==27&&moved.directionX==1&&moved.directionY==0&&moved.trailCount==2);memcpy(actor+0x154,position,12);
 *reinterpret_cast<int*>(image+0xf1b4c)=600;observeMapWorld(scene,true);require(readMapSnapshot().uiHeight==600);*reinterpret_cast<int*>(image+0xf1b4c)=-1;observeMapWorld(scene,true);require(readMapSnapshot().uiHeight==480);*reinterpret_cast<int*>(image+0xf1b4c)=0;
 MapView view;require(mapView(m,11,22,true,view));require(mapViewPoint(m,view,11,22,256,x,y)&&x==128&&y==128);require(mapView(m,11,22,false,view)&&view.left==0&&view.top==0&&view.span==512);
 observeMapWorld(scene,true);auto s=readMapSnapshot();require(s.valid&&s.identifier==9&&s.x==11&&s.y==22&&s.z==33);require(!memcmp(actor+0x154,position,12));observeMapWorld(scene,false);require(!readMapSnapshot().valid);*reinterpret_cast<int*>(scene+0x10d0)=-1;observeMapWorld(scene,true);require(!readMapSnapshot().valid);*reinterpret_cast<int*>(scene+0x10d0)=9;*reinterpret_cast<BYTE**>(actor+0x20)=nullptr;observeMapWorld(scene,true);require(!readMapSnapshot().valid);*reinterpret_cast<BYTE**>(actor+0x20)=scene;mapId=10;observeMapWorld(scene,true);require(!readMapSnapshot().valid);mapId=9;
 if(argc>=3){if(rewards){*reinterpret_cast<short*>(records+0x24)=42;*reinterpret_cast<short*>(records+0x48+0x26)=-1;}if(collected)switches[0]=2;if(headingIndex>=0)memcpy(actor+0x148,headings[headingIndex],12);float displayedPlayer[]={-120,260,33};memcpy(actor+0x154,displayedPlayer,12);observeMapWorld(scene,true);for(int i=0;i<8;++i){*reinterpret_cast<float*>(actor+0x154)+=5;observeMapWorld(scene,true);}
  SetEnvironmentVariableW(L"MC_MAP_ASSETS",argv[1]);
  for(int restart=0;restart<2;++restart){require(installMapOverlay(reinterpret_cast<HMODULE>(image),nullptr));observeMapWorld(scene,true);stopMapOverlay();require(mapOverlayTestResetState());}
  SetEnvironmentVariableW(L"MC_MAP_ASSETS",nullptr);mapOverlayTestInitialize(image);observeMapWorld(scene,true);
  require(full?mapOverlayTestRenderMode(argv[1],argv[2],MapDisplayMode::Full,1280,720):mapOverlayTestRender(argv[1],argv[2],mini));
  printf("MAP_OVERLAY_RENDER PASS mode=%s size=%s source=owned_fixture pixels=rendered game_started=false\n",full?"full":mini?"mini":"large",full?"1280x720":"536x584");}
 VirtualFree(image,0,MEM_RELEASE);
 printf("MAP_OVERLAY_FIXTURE PASS checks=%d read_only=true source_coordinates=unchanged metadata_guard=true pixel_alignment=true game_started=false\n",checks);
 printf("MAP_OVERLAY_F9 PASS cycle=off_mini_full_off held_key=single_edge inactive=hidden release_to_rearm=true full_layout=client opacity=150 game_started=false\n");
 printf("MAP_LIVE_MARKERS PASS NPC=live_green player=position_and_heading four_directions=true turn_in_place=true movement=true field_identity=independent source_unchanged=true game_started=false\n");
}
