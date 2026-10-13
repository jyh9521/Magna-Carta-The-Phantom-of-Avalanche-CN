#include "gamepad_cursor.h"
#include <cmath>
#include <algorithm>
namespace modern_input {
CursorPoint Cursor::update(int px,int py,int16_t ax,int16_t ay,unsigned elapsed,int width,int height,bool eligible){
 if(width<=0||height<=0||!eligible){owned_=false;blocked_=false;initialized_=false;return {float(px),float(py),false};}
 if(!initialized_){physicalX_=px;physicalY_=py;x_=float(px);y_=float(py);owned_=false;initialized_=true;}
 bool mouseMoved=px!=physicalX_||py!=physicalY_;physicalX_=px;physicalY_=py;
 float sx=std::clamp(float(ax)/32767.f,-1.f,1.f),sy=std::clamp(float(ay)/32767.f,-1.f,1.f);
 float magnitude=std::hypot(sx,sy),deadzone=8689.f/32767;
 if(mouseMoved){owned_=false;blocked_=true;x_=float(px);y_=float(py);}
 if(magnitude<=deadzone){blocked_=false;return {owned_?x_:float(px),owned_?y_:float(py),owned_};}
 if(blocked_)return {float(px),float(py),false};
 if(!owned_){owned_=true;x_=float(px);y_=float(py);}
 float speed=std::clamp((magnitude-deadzone)/(1-deadzone),0.f,1.f)*650.f*float(height)/600.f;
 float distance=speed*float(std::min(elapsed,50u))/1000.f;
 x_=std::clamp(x_+sx/magnitude*distance,0.f,float(width-1));y_=std::clamp(y_-sy/magnitude*distance,0.f,float(height-1));
 return {x_,y_,true};
}
void Cursor::focus(float x,float y,int w,int h){if(w<=0||h<=0||!std::isfinite(x)||!std::isfinite(y))return;x_=std::clamp(x,0.f,float(w-1));y_=std::clamp(y,0.f,float(h-1));owned_=true;blocked_=false;}
}
