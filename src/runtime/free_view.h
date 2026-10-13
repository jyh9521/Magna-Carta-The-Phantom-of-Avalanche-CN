#pragma once
#include "render_timeline.h"
namespace camera {
struct Input { bool toggle=false,reset=false; float yaw=0,pitch=0,zoom=0,seconds=0; };
class Orbit {
 bool active_=false,held_=false;float yaw_=0,pitch_=0,distance_=400;uintptr_t identity_=0;
public:
 void reset();
 bool active() const {return active_;}
 motion::Matrix sample(const motion::Matrix&,uintptr_t,Input);
};
}
