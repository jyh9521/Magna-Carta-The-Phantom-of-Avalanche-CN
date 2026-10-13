#include "ui_focus.h"
#include <cmath>
#include <limits>
namespace modern_input {
int chooseFocus(const std::vector<FocusTarget>& targets,float x,float y,int dx,int dy){
 if((dx==0)==(dy==0)||!std::isfinite(x)||!std::isfinite(y))return -1;
 int best=-1;float score=std::numeric_limits<float>::infinity();
 auto valid=[](const FocusTarget& r){return std::isfinite(r.left)&&std::isfinite(r.right)&&std::isfinite(r.top)&&std::isfinite(r.bottom)&&r.right>r.left&&r.bottom>r.top;};
 for(unsigned i=0;i<targets.size();++i){const auto& r=targets[i];if(!valid(r))continue;
  if(x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom)continue;
  float vx=(r.left+r.right)*.5f-x,vy=(r.top+r.bottom)*.5f-y;
  float ahead=vx*dx+vy*dy,across=std::abs(vx*dy-vy*dx);if(ahead<=.5f)continue;
  float s=ahead+across*4+across*across/(ahead+1);
  if(s<score){score=s;best=static_cast<int>(i);}
 }
 if(best>=0)return best;
 // Wrap to the opposite end, staying on the same row/column where possible.
 for(unsigned i=0;i<targets.size();++i){const auto& r=targets[i];if(!valid(r))continue;
  if(x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom)continue;
  float vx=(r.left+r.right)*.5f-x,vy=(r.top+r.bottom)*.5f-y;
  float s=vx*dx+vy*dy+std::abs(vx*dy-vy*dx)*8;
  if(s<score){score=s;best=static_cast<int>(i);}
 }
 return best;
}
}
