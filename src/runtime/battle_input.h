#pragma once
#include <cstdint>
namespace combat_input {
// All times are native 33 ms logic ticks, never presentation frames.
struct ComboState {
 uintptr_t owner=0;
 bool active=false,timed=false;
 unsigned tick=0,count=0,interval=0,window=0;
};
class ComboAssist {
 uintptr_t owner=0;bool running=false,triggerHeld=false,release=false;
 unsigned age=0,lastCount=0;bool timedSeen=false;
public:
 void reset(){owner=0;running=false;release=false;age=lastCount=0;timedSeen=false;}
 bool pending() const{return running;}
 bool update(const ComboState& s,bool trigger,bool eligible){
  const bool edge=trigger&&!triggerHeld;triggerHeld=trigger;
  if(!eligible||!s.owner||!s.active){reset();return false;}
  if(owner&&owner!=s.owner)reset();
  if(edge){reset();owner=s.owner;running=true;if(!s.timed){release=true;return true;}}
  if(!running)return false;
  const unsigned maxAge=s.interval>=2&&s.interval<=300&&s.window<=s.interval?2*s.interval+s.window+60:90;
  if(++age>maxAge){reset();return false;}
  // Give GetKeyboardState one native key-up poll between synthetic presses.
  if(release){release=false;return false;}
  if(!s.timed){if(timedSeen)reset();return false;}
  timedSeen=true;
  if(s.count>=3){reset();return false;}
  if(s.count<1||s.interval<2||s.interval>300||!s.window||s.window>s.interval)return false;
  const uint64_t start=uint64_t(s.interval)*s.count,end=start+s.window;
  const uint64_t target=start+(s.window-1)/2;
  if(s.tick>=target&&s.tick<end&&lastCount!=s.count){lastCount=s.count;release=true;return true;}
  if(s.tick>=end){reset();return false;}
  return false;
 }
};
// A is a keyboard confirmation in battle: the native combo handler accepts
// Space-down (event 0x13), not a cursor-dependent click on any arbitrary pixel.
inline unsigned confirmKey(bool battle,unsigned menuKey){return battle?0x20:menuKey;}
}
