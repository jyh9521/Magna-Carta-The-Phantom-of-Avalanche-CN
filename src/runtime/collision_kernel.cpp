#include "collision_kernel.h"
namespace {
bool finite(float x){union{float f;unsigned u;}v{x};return (v.u&0x7f800000u)!=0x7f800000u;}
bool valid(CollisionVec p){return finite(p.x)&&finite(p.y)&&finite(p.z);}
float absf(float x){return x<0?-x:x;}
struct Probe {
 CollisionQuery query;void* context;const CollisionVec* offsets;unsigned count,budget=4096;bool unknown=false;
 bool clear(CollisionVec p){
  for(unsigned i=0;i<=count;++i){
   if(!budget){unknown=true;return false;}--budget;
   CollisionVec v=p;v.z+=15;
   if(i<count){v.x+=offsets[i].x;v.y+=offsets[i].y;v.z+=offsets[i].z;}
   int r=query(v,context);if(r<0){unknown=true;return false;}if(r)return false;
  }return true;
 }
};
CollisionVec mix(CollisionVec a,CollisionVec b,float t){return {a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,a.z+(b.z-a.z)*t};}
}
unsigned __cdecl resolveCollisionStep(CollisionVec before,CollisionVec proposed,const CollisionVec* offsets,
 unsigned count,CollisionQuery query,void* context,CollisionVec* out){
 if(!out)return 4;*out=proposed;
 if(!query||count>8||(count&&!offsets)||!valid(before)||!valid(proposed))return 4;
 for(unsigned i=0;i<count;++i)if(!valid(offsets[i]))return 4;
 Probe p{query,context,offsets,count};
 if(!p.clear(before)){
  if(p.unknown)return 4;
  // Shortest sampled horizontal separating translation; no map/field coordinates.
  // Never scan through the world or move vertically to bypass a floor/ceiling.
  constexpr float dirs[16][2]={{1,0},{.9238795f,.3826834f},{.7071068f,.7071068f},{.3826834f,.9238795f},
   {0,1},{-.3826834f,.9238795f},{-.7071068f,.7071068f},{-.9238795f,.3826834f},
   {-1,0},{-.9238795f,-.3826834f},{-.7071068f,-.7071068f},{-.3826834f,-.9238795f},
   {0,-1},{.3826834f,-.9238795f},{.7071068f,-.7071068f},{.9238795f,-.3826834f}};
  for(unsigned ring=1;ring<=32;++ring)for(auto& d:dirs){
   CollisionVec candidate{before.x+d[0]*(ring*.5f),before.y+d[1]*(ring*.5f),before.z};
   if(p.clear(candidate)){*out=candidate;return 2;}if(p.unknown)return 4;
  }return 3;
 }
 float length=absf(proposed.x-before.x);
 if(absf(proposed.y-before.y)>length)length=absf(proposed.y-before.y);
 if(absf(proposed.z-before.z)>length)length=absf(proposed.z-before.z);
 if(length==0)return 0;
 // The native integration is fixed at .03. Large discontinuities are not walked
 // through: keep the known-free start rather than guessing at a teleport path.
 if(length>128){*out=before;return 1;}
 unsigned steps=1;while(float(steps)<=length)++steps;float last=0;
 for(unsigned i=1;i<=steps;++i){float t=float(i)/float(steps);
  if(!p.clear(mix(before,proposed,t))){
   if(p.unknown){*out=before;return 1;}
   float lo=last,hi=t;
   for(unsigned j=0;j<14;++j){float mid=(lo+hi)*.5f;
    if(p.clear(mix(before,proposed,mid)))lo=mid;else hi=mid;
    if(p.unknown){*out=before;return 1;}
   }
   *out=mix(before,proposed,lo);return 1;
  }last=t;
 }return 0;
}
