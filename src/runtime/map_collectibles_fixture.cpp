#include "map_collectibles.h"
#include <cstdio>
#include <limits>

namespace {
int checks=0;
void require(bool value,const char* label){++checks;if(!value){std::fprintf(stderr,"MAP_COLLECTIBLES_FAIL check=%d %s\n",checks,label);ExitProcess(1);}}
template<class T> void put(void* base,size_t at,T value){std::memcpy(static_cast<BYTE*>(base)+at,&value,sizeof value);}
using State=MapCollectibleState;
}
int main(){
 static_assert(sizeof(void*)==4,"Owned replay matches the native x86 layout");
 auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
 require(image!=nullptr,"image allocation");
 IMAGE_DOS_HEADER dos{};dos.e_magic=IMAGE_DOS_SIGNATURE;dos.e_lfanew=0x100;put(image,0,dos);
 IMAGE_NT_HEADERS32 nt{};nt.Signature=IMAGE_NT_SIGNATURE;nt.FileHeader.Machine=IMAGE_FILE_MACHINE_I386;
 nt.FileHeader.TimeDateStamp=0x3ed73966;nt.OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt.OptionalHeader.SizeOfImage=0x10b000;put(image,0x100,nt);
 BYTE scene[0x151c]{},rows[3][0x48]{},manager[0x2c]{};int switches[2000]{};
 put(scene,0,image+0xc12bc);put(scene,0x1514,2);put(scene,0x1518,&rows[0][0]);
 put(rows[0],0,101);put(rows[0],8,6);put(rows[0],0x24,int16_t(70));put(rows[0],0x26,int16_t(128));
 put(rows[1],0,102);put(rows[1],8,3);put(rows[1],0x24,int16_t(-1));put(rows[1],0x26,int16_t(-1));
 put(image,0xf2304,manager);put(manager,0,image+0xbe774);put(manager,0x24,switches);put(manager,0x28,2000);
 auto classify=[&](int id=101,int type=0x168){
  BYTE oldScene[sizeof scene],oldRows[sizeof rows],oldManager[sizeof manager];int oldSwitches[2000];
  std::memcpy(oldScene,scene,sizeof scene);std::memcpy(oldRows,rows,sizeof rows);std::memcpy(oldManager,manager,sizeof manager);std::memcpy(oldSwitches,switches,sizeof switches);
  auto result=classifyMapCollectible(image,scene,id,type);
  require(!std::memcmp(scene,oldScene,sizeof scene)&&!std::memcmp(rows,oldRows,sizeof rows)&&!std::memcmp(manager,oldManager,sizeof manager)&&!std::memcmp(switches,oldSwitches,sizeof switches),"read only");
  return result;
 };
 require(classify()==State::ContainerAvailable,"kind6 unopened");
 switches[128]=1;require(classify()==State::ContainerAvailable,"kind6 opening");
 switches[128]=2;require(classify()==State::ContainerConsumed,"kind6 item granted");
 switches[128]=3;require(classify()==State::ContainerConsumed,"kind6 popup ended");
 switches[128]=4;require(classify()==State::Unknown,"kind6 unrecognized state4");
 put(rows[0],8,7);require(classify()==State::ContainerAvailable,"kind7 missing key prompt");
 switches[128]=0;require(classify()==State::ContainerAvailable,"kind7 prompt dismissed");
 for(int state=1;state<=3;++state){switches[128]=state;require(classify()==(state==1?State::ContainerAvailable:State::ContainerConsumed),"kind7 normal states");}
 switches[128]=-1;require(classify()==State::Unknown,"negative state");switches[128]=5;require(classify()==State::Unknown,"unknown state");switches[128]=0;
 require(classify(102,0x16a)==State::NoReward,"NPC item sentinel");
 put(rows[1],0x24,int16_t(43));put(rows[1],0x26,int16_t(144));require(classify(102,0x16a)==State::NpcReward,"NPC gift available");
 switches[144]=1;require(classify(102,0x16a)==State::NoReward,"NPC gift already granted");
 require(classify(102,0x168)==State::Unknown,"native type mismatch");require(classify(101,0x16a)==State::Unknown,"NPC type mismatch");
 require(classify(999)==State::Unknown,"missing record");require(classify(-1)==State::Unknown,"negative key");require(classify(101,0)==State::Unknown,"unsupported native type");
 put(rows[0],8,4);require(classify()==State::Unknown,"kind4 is not collectible");put(rows[0],8,7);
 put(rows[2],0,101);put(scene,0x1514,3);require(classify()==State::Unknown,"duplicate key rejected");put(scene,0x1514,2);
 put(rows[0],0x26,int16_t(-1));require(classify()==State::Unknown,"negative switch index");
 put(rows[0],0x26,int16_t(2000));require(classify()==State::Unknown,"switch upper bound");
 put(rows[0],0x26,int16_t(1999));require(classify()==State::ContainerAvailable,"last switch index");put(rows[0],0x26,int16_t(128));
 put(rows[0],0x24,int16_t(-1));require(classify()==State::Unknown,"container item sentinel");put(rows[0],0x24,int16_t(70));
 put(manager,0x28,0);require(classify()==State::Unknown,"empty switch table");put(manager,0x28,2001);require(classify()==State::Unknown,"excessive switch table");put(manager,0x28,100);require(classify()==State::Unknown,"dynamic switch bound");put(manager,0x28,2000);
 put(manager,0,image+0xbe778);require(classify()==State::Unknown,"manager identity");put(manager,0,image+0xbe774);
 put(scene,0,image+0xc12c0);require(classify()==State::Unknown,"scene identity");put(scene,0,image+0xc12bc);
 put(scene,0x1514,0);require(classify()==State::Unknown,"empty records");put(scene,0x1514,4097);require(classify()==State::Unknown,"record work bound");put(scene,0x1514,2);
 nt.FileHeader.TimeDateStamp^=1;put(image,0x100,nt);require(classify()==State::Unknown,"PE timestamp");nt.FileHeader.TimeDateStamp^=1;put(image,0x100,nt);
 nt.OptionalHeader.SizeOfImage-=0x1000;put(image,0x100,nt);require(classify()==State::Unknown,"PE image size");nt.OptionalHeader.SizeOfImage+=0x1000;put(image,0x100,nt);
 dos.e_lfanew=std::numeric_limits<LONG>::max();put(image,0,dos);require(classify()==State::Unknown,"PE offset bound");dos.e_lfanew=0x100;put(image,0,dos);
 auto protectedPage=static_cast<BYTE*>(VirtualAlloc(nullptr,8192,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(protectedPage!=nullptr,"guard allocation");DWORD old=0;
 require(VirtualProtect(protectedPage+4096,4096,PAGE_NOACCESS,&old)!=0,"noaccess page");
 put(scene,0x1518,protectedPage+4096-0x48);require(classify()==State::Unknown,"cross-page record range");put(scene,0x1518,&rows[0][0]);
 put(manager,0x24,protectedPage+4096);require(classify()==State::Unknown,"unreadable switches");put(manager,0x24,switches);
 put(image,0xf2304,protectedPage+4096);require(classify()==State::Unknown,"unreadable manager");put(image,0xf2304,manager);
 require(classifyMapCollectible(image,protectedPage+4096,101,0x168)==State::Unknown,"unreadable scene");
 require(classifyMapCollectible(protectedPage+4096,scene,101,0x168)==State::Unknown,"unreadable image");
 require(classifyMapCollectible(nullptr,scene,101,0x168)==State::Unknown,"null image");
 require(classify()==State::ContainerAvailable,"restored fixture behavior");
 VirtualFree(protectedPage,0,MEM_RELEASE);VirtualFree(image,0,MEM_RELEASE);
 std::printf("MAP_COLLECTIBLES_V1 PASS checks=%d read_only=true unique_key=true bounds=true consumed=hidden locked_prompt=available npc_reward=true invalid=unknown game_started=false\n",checks);
 return 0;
}
