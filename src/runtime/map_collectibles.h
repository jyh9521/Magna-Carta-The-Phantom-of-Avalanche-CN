#pragma once
#include <windows.h>
#include <cstdint>
#include <cstring>

enum class MapCollectibleState {
 ContainerAvailable, ContainerConsumed, NpcReward, NoReward, Unknown
};

namespace map_collectibles_detail {
// Runtime reads remain on the exploration tick. Readability alone does not prove
// an object identity; the PE, scene, record key and switch-manager guards do that.
inline bool readable(const void* address,size_t size){
 auto p=reinterpret_cast<uintptr_t>(address),end=p+size;
 if(!p||!size||end<p)return false;
 while(p<end){
  MEMORY_BASIC_INFORMATION m{};
  if(!VirtualQuery(reinterpret_cast<const void*>(p),&m,sizeof m)||m.State!=MEM_COMMIT||
     (m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
  DWORD protection=m.Protect&0xff;
  if(protection!=PAGE_READONLY&&protection!=PAGE_READWRITE&&protection!=PAGE_WRITECOPY&&
     protection!=PAGE_EXECUTE_READ&&protection!=PAGE_EXECUTE_READWRITE&&protection!=PAGE_EXECUTE_WRITECOPY)return false;
  auto next=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;
  if(next<=p)return false;p=next;
 }
 return true;
}
inline const BYTE* offset(const void* base,size_t displacement){
 auto p=reinterpret_cast<uintptr_t>(base);
 return p&&p+displacement>=p?reinterpret_cast<const BYTE*>(p+displacement):nullptr;
}
inline bool copy(const void* source,void* target,size_t size){
 if(!readable(source,size))return false;
 // An allocation can disappear between VirtualQuery and the read. Fail closed.
 __try{std::memcpy(target,source,size);return true;}
 __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
template<class T> inline bool read(const void* base,size_t displacement,T& value){
 return copy(offset(base,displacement),&value,sizeof value);
}
inline bool image(const BYTE* engine){
 IMAGE_DOS_HEADER dos{};IMAGE_NT_HEADERS32 nt{};
 return sizeof(void*)==4&&read(engine,0,dos)&&dos.e_magic==IMAGE_DOS_SIGNATURE&&
  dos.e_lfanew>=LONG(sizeof dos)&&dos.e_lfanew<=0x1000&&read(engine,size_t(dos.e_lfanew),nt)&&
  nt.Signature==IMAGE_NT_SIGNATURE&&nt.FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&
  nt.FileHeader.TimeDateStamp==0x3ed73966&&nt.OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&
  nt.OptionalHeader.SizeOfImage==0x10b000;
}
inline bool uniqueRecord(const BYTE* records,int count,int objectId,BYTE (&row)[0x48]){
 if(!readable(records,size_t(count)*0x48))return false;
 bool found=false;
 __try{
  for(int i=0;i<count;++i){
   int id=0;std::memcpy(&id,records+size_t(i)*0x48,4);
   if(id!=objectId)continue;
   if(found)return false;
   std::memcpy(row,records+size_t(i)*0x48,sizeof row);found=true;
  }
 }__except(EXCEPTION_EXECUTE_HANDLER){return false;}
 return found;
}
}

// Call only for live, identity-checked NPC/container objects. object+d4 is a
// separate disabled flag, never the collection state. No game memory is written.
inline MapCollectibleState classifyMapCollectible(const BYTE* engine,const BYTE* scene,int objectId,int nativeType){
 using namespace map_collectibles_detail;
 const auto unknown=MapCollectibleState::Unknown;
 if(objectId<0||(nativeType!=0x168&&nativeType!=0x16a)||!image(engine))return unknown;
 const BYTE *vptr=nullptr,*records=nullptr;int count=0;
 if(!read(scene,0,vptr)||vptr!=offset(engine,0xc12bc)||!read(scene,0x1514,count)||
    count<=0||count>4096||!read(scene,0x1518,records))return unknown;
 BYTE row[0x48]{};if(!uniqueRecord(records,count,objectId,row))return unknown;
 int kind=0;int16_t item=-1,index=-1;
 std::memcpy(&kind,row+8,4);std::memcpy(&item,row+0x24,2);std::memcpy(&index,row+0x26,2);
 if((nativeType==0x168&&kind!=6&&kind!=7)||(nativeType==0x16a&&kind!=3))return unknown;
 if(kind==3&&item==-1)return MapCollectibleState::NoReward;
 if(item<0||index<0)return unknown;
 const BYTE *manager=nullptr,*switches=nullptr;int switchCount=0,state=0;
 if(!read(engine,0xf2304,manager)||!read(manager,0,vptr)||vptr!=offset(engine,0xbe774)||
    !read(manager,0x28,switchCount)||switchCount<=0||switchCount>2000||index>=switchCount||
    !read(manager,0x24,switches)||!read(switches,size_t(index)*4,state))return unknown;
 if(kind==3)return state==0?MapCollectibleState::NpcReward:MapCollectibleState::NoReward;
 if(state==0||state==1||(kind==7&&state==4))return MapCollectibleState::ContainerAvailable;
 if(state==2||state==3)return MapCollectibleState::ContainerConsumed;
 return unknown;
}
