#include "render_timeline.h"
#include <cmath>
#include <algorithm>
#include <cstring>
namespace motion {
void Timeline::reset(){ ++phase_.generation;phase_.valid=false;phase_.alpha=1;owner_=0; }
void Timeline::observe(uintptr_t owner,unsigned interval,unsigned remainder,unsigned consumed,uint32_t timestamp,bool active){
 if(!owner||interval!=33||remainder>=interval||consumed>=5||!active){reset();timestamp_=timestamp;return;}
 if(owner_!=owner||!phase_.valid||uint32_t(timestamp-timestamp_)>250){++phase_.generation;phase_.tick=0;}
 else phase_.tick+=consumed;
 owner_=owner;timestamp_=timestamp;phase_.alpha=float(remainder)/float(interval);phase_.valid=true;
}
struct Q {float x,y,z,w;};
static Q quaternion(const Matrix& m){
 Q q{};float t=m.v[0]+m.v[5]+m.v[10];
 if(t>0){float s=std::sqrt(t+1)*2;q.w=s/4;q.x=(m.v[9]-m.v[6])/s;q.y=(m.v[2]-m.v[8])/s;q.z=(m.v[4]-m.v[1])/s;}
 else if(m.v[0]>m.v[5]&&m.v[0]>m.v[10]){float s=std::sqrt(1+m.v[0]-m.v[5]-m.v[10])*2;q.w=(m.v[9]-m.v[6])/s;q.x=s/4;q.y=(m.v[1]+m.v[4])/s;q.z=(m.v[2]+m.v[8])/s;}
 else if(m.v[5]>m.v[10]){float s=std::sqrt(1+m.v[5]-m.v[0]-m.v[10])*2;q.w=(m.v[2]-m.v[8])/s;q.x=(m.v[1]+m.v[4])/s;q.y=s/4;q.z=(m.v[6]+m.v[9])/s;}
 else{float s=std::sqrt(1+m.v[10]-m.v[0]-m.v[5])*2;q.w=(m.v[4]-m.v[1])/s;q.x=(m.v[2]+m.v[8])/s;q.y=(m.v[6]+m.v[9])/s;q.z=s/4;}return q;
}
bool rigid(const Matrix& m){
 for(float x:m.v)if(!std::isfinite(x))return false;
 for(int r=0;r<3;++r){float n=0;for(int c=0;c<3;++c)n+=m.v[r*4+c]*m.v[r*4+c];if(std::abs(n-1)>0.03f)return false;
 for(int s=0;s<r;++s){float d=0;for(int c=0;c<3;++c)d+=m.v[r*4+c]*m.v[s*4+c];if(std::abs(d)>0.03f)return false;}}
 float det=m.v[0]*(m.v[5]*m.v[10]-m.v[6]*m.v[9])-m.v[1]*(m.v[4]*m.v[10]-m.v[6]*m.v[8])+m.v[2]*(m.v[4]*m.v[9]-m.v[5]*m.v[8]);
 return det>0.97f&&det<1.03f&&std::abs(m.v[3])+std::abs(m.v[7])+std::abs(m.v[11])<0.001f&&std::abs(m.v[15]-1)<0.001f;
}
void blend(const Matrix& a,const Matrix& b,float t,Matrix& out){
 out=b;if(!rigid(a)||!rigid(b)||!std::isfinite(t))return;
 if(t>=1)return;if(t<=0){out=a;return;}
 Q x=quaternion(a),y=quaternion(b);float dot=x.x*y.x+x.y*y.y+x.z*y.z+x.w*y.w;
 if(dot<0){y.x=-y.x;y.y=-y.y;y.z=-y.z;y.w=-y.w;}
 Q q{x.x+(y.x-x.x)*t,x.y+(y.y-x.y)*t,x.z+(y.z-x.z)*t,x.w+(y.w-x.w)*t};
 float n=std::sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w);if(n<0.001f)return;q.x/=n;q.y/=n;q.z/=n;q.w/=n;
 out.v[0]=1-2*(q.y*q.y+q.z*q.z);out.v[1]=2*(q.x*q.y-q.z*q.w);out.v[2]=2*(q.x*q.z+q.y*q.w);
 out.v[4]=2*(q.x*q.y+q.z*q.w);out.v[5]=1-2*(q.x*q.x+q.z*q.z);out.v[6]=2*(q.y*q.z-q.x*q.w);
 out.v[8]=2*(q.x*q.z-q.y*q.w);out.v[9]=2*(q.y*q.z+q.x*q.w);out.v[10]=1-2*(q.x*q.x+q.y*q.y);
 for(int i=12;i<15;++i)out.v[i]=a.v[i]+(b.v[i]-a.v[i])*t;
}
Matrix multiply(const Matrix& a,const Matrix& b){Matrix o{};for(int c=0;c<4;++c)for(int r=0;r<4;++r)for(int k=0;k<4;++k)o.v[c*4+r]+=a.v[k*4+r]*b.v[c*4+k];return o;}
Matrix inverseRigid(const Matrix& m){Matrix o{};o.v[15]=1;for(int c=0;c<3;++c)for(int r=0;r<3;++r)o.v[c*4+r]=m.v[r*4+c];for(int r=0;r<3;++r)for(int k=0;k<3;++k)o.v[12+r]-=o.v[k*4+r]*m.v[12+k];return o;}
Matrix TransformTrack::sample(const Matrix& input,Phase p,bool camera){
 if(!p.valid||!rigid(input)){reset();return input;}
 Matrix value=camera?inverseRigid(input):input;
 bool cut=false;if(initialized_){float distance=0;for(int k=12;k<15;++k){float d=value.v[k]-current_.v[k];distance+=d*d;}cut=distance>256.f*256.f;
 if(camera){auto a=quaternion(current_),b=quaternion(value);cut=cut||std::abs(a.x*b.x+a.y*b.y+a.z*b.z+a.w*b.w)<.5f;}}
 bool discontinuity=!initialized_||stamp_.generation!=p.generation||p.tick<stamp_.tick||p.tick>stamp_.tick+1||cut;
 // Removing a changing camera may introduce float roundoff into a stationary actor.
 if(!discontinuity&&p.tick==stamp_.tick)for(int i=0;i<16;++i)
  if(std::abs(value.v[i]-current_.v[i])>(i>=12&&i<=14?.01f:.0005f)){discontinuity=true;break;}
 if(discontinuity){previous_=current_=value;initialized_=true;}
 else if(p.tick!=stamp_.tick){previous_=current_;current_=value;}
 stamp_=p;Matrix out{};blend(previous_,current_,p.alpha,out);return camera?inverseRigid(out):out;
}
}
