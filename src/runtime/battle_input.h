#pragma once
#include <cstdint>
namespace combat_input {
// All times are native 33 ms logic ticks, never presentation frames.
struct ComboState {
 uintptr_t owner=0;
 bool active=false,timed=false;
 unsigned tick=0,count=0,interval=0,window=0;
 unsigned precision=0;uintptr_t actor=0;unsigned action=0;
};
class ComboAssist {
 uintptr_t owner=0;bool running=false,triggerHeld=false,release=false;
 unsigned age=0,lastCount=0,previousTick=0,previousCount=0;bool timedSeen=false;
 uintptr_t actor=0;unsigned action=0;
public:
 void reset(){owner=0;running=false;release=false;age=lastCount=previousTick=previousCount=0;timedSeen=false;actor=0;action=0;}
 bool pending() const{return running;}
 bool update(const ComboState& s,bool trigger,bool eligible){
  const bool edge=trigger&&!triggerHeld;triggerHeld=trigger;
  if(!eligible||!s.owner||!s.active){reset();return false;}
  // A scene object can be reused by the next actor/command. Never carry a
  // request into a rewound sequence even if the scene address is unchanged.
  if(running&&(owner!=s.owner||actor!=s.actor||action!=s.action||
      (timedSeen&&(s.tick<previousTick||s.count<previousCount))))reset();
  if(edge){reset();owner=s.owner;actor=s.actor;action=s.action;running=true;if(!s.timed){release=true;return true;}}
  if(!running)return false;
  if(!s.timed&&timedSeen){reset();return false;}
  // Observe every poll, including the mandatory key-up poll.
  if(s.timed){timedSeen=true;previousTick=s.tick;previousCount=s.count;}
  const unsigned maxAge=s.interval>=2&&s.interval<=300&&s.window<=s.interval?2*s.interval+s.window+60:90;
  if(++age>maxAge){reset();return false;}
  // Give GetKeyboardState one native key-up poll between synthetic presses.
  if(release){release=false;return false;}
  if(!s.timed)return false;
  if(s.count>=3){reset();return false;}
  if(s.count<1||s.interval<2||s.interval>300||!s.window||s.window>s.interval)return false;
  const uint64_t start=uint64_t(s.interval)*s.count;
  // The native scorer uses key 0x25, narrower than the handler's key 0x24.
  // Legacy callers without a precision field retain the loose-window policy.
  const unsigned aim=s.precision&&s.precision<=s.window?s.precision:s.window;
  const uint64_t target=start+(aim-1)/2;
  if(s.tick>=target&&s.tick<start+aim&&lastCount!=s.count){lastCount=s.count;release=true;return true;}
  if(s.tick>=start+aim){reset();return false;}
  return false;
 }
};
// A is a keyboard confirmation in battle: the native combo handler accepts
// Space-down (event 0x13), not a cursor-dependent click on any arbitrary pixel.
inline unsigned confirmKey(bool battle,unsigned menuKey){return battle?0x20:menuKey;}
}
