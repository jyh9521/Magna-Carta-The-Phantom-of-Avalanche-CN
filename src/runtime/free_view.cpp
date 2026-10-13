#include "free_view.h"
#include <cmath>
#include <algorithm>
namespace camera {
void Orbit::reset(){active_=held_=false;yaw_=pitch_=0;distance_=400;identity_=0;}
motion::Matrix Orbit::sample(const motion::Matrix& view,uintptr_t identity,Input input){
 if(!identity||!motion::rigid(view)){reset();return view;}
 if(identity_!=identity){reset();identity_=identity;held_=input.toggle;return view;}
 if(input.reset){reset();identity_=identity;held_=input.toggle;return view;}
 if(input.toggle&&!held_)active_=!active_;held_=input.toggle;
 if(!active_)return view;
 if(!std::isfinite(input.seconds)||!std::isfinite(input.yaw)||!std::isfinite(input.pitch)||!std::isfinite(input.zoom))return view;
 float dt=std::clamp(input.seconds,0.f,.05f);
 yaw_=std::clamp(yaw_+std::clamp(input.yaw,-1.f,1.f)*dt,-2.094395f,2.094395f);
 pitch_=std::clamp(pitch_+std::clamp(input.pitch,-1.f,1.f)*dt,-1.22173f,1.22173f);
 distance_=std::clamp(distance_*std::exp(std::clamp(input.zoom,-1.f,1.f)*dt),16.f,4096.f);
 auto pose=motion::inverseRigid(view);float pivot[3];
 for(int k=0;k<3;++k)pivot[k]=pose.v[12+k]-pose.v[8+k]*400;
 float cy=std::cos(yaw_),sy=std::sin(yaw_),cp=std::cos(pitch_),sp=std::sin(pitch_);
 for(int c=0;c<3;++c){float x=pose.v[4*c],y=pose.v[4*c+1];pose.v[4*c]=cy*x-sy*y;pose.v[4*c+1]=sy*x+cy*y;}
 for(int k=0;k<3;++k){float u=pose.v[4+k],b=pose.v[8+k];pose.v[4+k]=cp*u+sp*b;pose.v[8+k]=-sp*u+cp*b;pose.v[12+k]=pivot[k]+pose.v[8+k]*distance_;}
 return motion::rigid(pose)?motion::inverseRigid(pose):view;
}
}
