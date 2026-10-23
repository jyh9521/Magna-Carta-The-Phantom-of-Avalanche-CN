#pragma once
#include <cstdint>
namespace combat_input {
enum class BattlePadRoute {Outside,Field,Menu,Result,Blocked};
inline BattlePadRoute battlePadRoute(unsigned mode){
 return mode==1?BattlePadRoute::Field:(mode==4||mode==5||mode==6)?BattlePadRoute::Menu:mode==7?BattlePadRoute::Result:BattlePadRoute::Blocked;
}
class PadContextGate {
 uintptr_t owner_=0;unsigned mode_=0;uint16_t blocked_=0,previous_=0;
public:
 bool changed=false;
 uint16_t update(uintptr_t owner,unsigned mode,uint16_t buttons){
  changed=owner!=owner_||mode!=mode_;owner_=owner;mode_=mode;
  // A/B/X/Y/Start/R3 must be released across a route boundary. Directions
  // retain the native field/menu semantics and never create a face-button edge.
  constexpr uint16_t semantic=0xf090;
  if(changed)blocked_|=buttons&previous_&semantic;
  previous_=buttons;
  blocked_&=buttons;return buttons&~blocked_;
 }
 void reset(){owner_=0;mode_=0;blocked_=previous_=0;changed=false;}
};
}
