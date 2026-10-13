#include "camera_relative_input.h"
#include <algorithm>
#include <cmath>
namespace modern_input {
MoveIntent cameraRelative(int16_t x,int16_t y,uint16_t buttons,const float* view,int deadzone){
 if(!view||deadzone<0||deadzone>=32767)return {};
 for(int i=0;i<16;++i)if(!std::isfinite(view[i]))return {};
 // Transpose the view rotation to obtain camera-right and camera-up in world XY.
 float rx=view[0],ry=view[4],ux=view[1],uy=view[5];
 float length=std::hypot(rx,ry);if(length<.001f)return {};rx/=length;ry/=length;
 float upx=-ry,upy=rx;
 float dot=upx*ux+upy*uy;
 if(std::abs(dot)<.001f)dot=upx*(-view[2])+upy*(-view[6]);
 if(dot<0){upx=-upx;upy=-upy;}
 float sx=std::clamp(float(x)/32767.f,-1.f,1.f),sy=std::clamp(float(y)/32767.f,-1.f,1.f);
 bool digital=(buttons&15)!=0;
 if(digital){sx=((buttons&8)?1.f:0.f)-((buttons&4)?1.f:0.f);sy=((buttons&1)?1.f:0.f)-((buttons&2)?1.f:0.f);}
 float magnitude=std::hypot(sx,sy),zone=float(deadzone)/32767.f;
 if(magnitude<=zone||magnitude<.001f)return {};
 float speed=digital?1.f:std::clamp((magnitude-zone)/(1-zone),0.f,1.f);
 return {(rx*sx+upx*sy)/magnitude,(ry*sx+upy*sy)/magnitude,speed,true};
}
}
