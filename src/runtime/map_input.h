#pragma once
#include <cstdint>
namespace map_input {
// Source-message edges survive a down/up pair between overlay refreshes.
// The caller owns synchronization and supplies a validated exploration context.
class CycleLatch {
 uintptr_t owner_=0;uint32_t generation_=0,sample_=0,edges_[8]{};
 unsigned count_=0;bool armed_=false,held_=true;
 bool current(uint32_t now)const{return owner_&&uint32_t(now-sample_)<=maxAge;}
public:
 static constexpr uint32_t maxAge=250;
 void clear(){owner_=0;generation_=sample_=count_=0;armed_=false;held_=true;}
 void context(uintptr_t owner,uint32_t generation,uint32_t now,bool valid){
  if(!valid||!owner){clear();return;}
  if(owner_!=owner||generation_!=generation||!current(now)){clear();owner_=owner;generation_=generation;}
  sample_=now;
 }
 void keyboard(uint32_t now,bool down,bool valid){
  if(!valid||!current(now)){clear();return;}
  if(!down){armed_=true;held_=false;}
 }
 void message(uint32_t now,uint32_t stamp,bool down,bool repeat,bool valid){
  if(!valid||!current(now)){clear();return;}
  if(uint32_t(now-stamp)>maxAge)return;
  if(!down){armed_=true;held_=false;return;}
  if(armed_&&!held_&&!repeat){
   if(count_==8){for(unsigned i=1;i<8;++i)edges_[i-1]=edges_[i];--count_;}
   edges_[count_++]=stamp;
  }
  held_=true;
 }
 unsigned consume(uint32_t now,bool valid){
  if(!valid||!current(now)){clear();return 0;}
  unsigned result=0;for(unsigned i=0;i<count_;++i)if(uint32_t(now-edges_[i])<=maxAge)++result;
  count_=0;return result;
 }
};
}
