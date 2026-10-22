#pragma once
#include <cstdint>
namespace combat_input {
// One physical edge per input sample, not a macro or a success-window buffer.
class SpaceEdgeLatch {
 uintptr_t owner_=0;uint32_t poll_=0,stamp_=0;bool pending_=false;
public:
 static constexpr uint32_t maxAge=66;
 void clear(){owner_=0;poll_=stamp_=0;pending_=false;}
 void sample(uintptr_t owner,uint32_t now,bool valid){
  if(!valid||!owner){clear();return;}
  if(owner_!=owner||uint32_t(now-poll_)>maxAge)pending_=false;
  owner_=owner;poll_=now;
 }
 void message(uintptr_t owner,uint32_t now,uint32_t stamp,bool down,bool repeat,bool valid){
  if(!valid||!owner||owner_!=owner||uint32_t(now-poll_)>maxAge){clear();return;}
  if(down&&!repeat&&uint32_t(now-stamp)<=maxAge){pending_=true;stamp_=stamp;}
 }
 bool consume(uintptr_t owner,uint32_t now,bool valid){
  sample(owner,now,valid);
  bool edge=pending_&&uint32_t(now-stamp_)<=maxAge;pending_=false;return edge;
 }
};
}
