#pragma once
#include <cmath>
#include <limits>
namespace render_input {
// Original mouse ray uses inverse(view) * (screenDx,0,screenDy).
// Solve the original ground-plane basis for the displayed view's ground ray.
inline bool mouseViewPoint(const float* source,const float* displayed,int cx,int cy,int x,int y,int& outX,int& outY){
 if(!source||!displayed)return false;
 for(unsigned i=0;i<16;++i)if(!std::isfinite(source[i])||!std::isfinite(displayed[i]))return false;
 double a=source[0],b=source[2],c=source[4],d=source[6],det=a*d-b*c;
 if(std::abs(det)<1e-5)return false;
 double dx=double(x)-cx,dy=double(y)-cy;
 double wx=displayed[0]*dx+displayed[2]*dy,wy=displayed[4]*dx+displayed[6]*dy;
 double ox=cx+(d*wx-b*wy)/det,oy=cy+(a*wy-c*wx)/det;
 if(!std::isfinite(ox)||!std::isfinite(oy)||ox<std::numeric_limits<int>::min()+1.0||ox>std::numeric_limits<int>::max()-1.0||oy<std::numeric_limits<int>::min()+1.0||oy>std::numeric_limits<int>::max()-1.0)return false;
 outX=static_cast<int>(std::lround(ox));outY=static_cast<int>(std::lround(oy));return true;
}
}
