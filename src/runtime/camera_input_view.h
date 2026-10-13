#pragma once
#include <cstdint>
#include <cstring>
#include <cmath>
namespace render_input {
// A copy of the most recently displayed orbit view, never an engine matrix write.
class InputView {
 float view_[16]{};uintptr_t identity_=0;uint32_t time_=0;bool valid_=false;
public:
 void reset(){valid_=false;identity_=0;}
 void publish(const float* view,uintptr_t identity,uint32_t time,bool active){
  reset();if(!active||!view||!identity)return;for(unsigned i=0;i<16;++i)if(!std::isfinite(view[i]))return;
  memcpy(view_,view,sizeof(view_));identity_=identity;time_=time;valid_=true;
 }
 bool read(uintptr_t identity,uint32_t time,float* out)const{
  if(!out||!valid_||!identity||identity!=identity_||uint32_t(time-time_)>250)return false;
  memcpy(out,view_,sizeof(view_));return true;
 }
};
inline thread_local InputView inputView;
}
