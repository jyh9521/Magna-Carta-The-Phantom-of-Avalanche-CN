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
// Separate near-rigid stretch/shear rather than dropping it in quaternion rebuild.
static bool rotationPart(const Matrix& input,Matrix& rotation){
 rotation={};rotation.v[15]=1;for(int c=0;c<3;++c)for(int r=0;r<3;++r)rotation.v[c*4+r]=input.v[c*4+r];
 for(unsigned iteration=0;iteration<6;++iteration){
  const auto& m=rotation.v;
  float cof[9]={m[5]*m[10]-m[9]*m[6],m[8]*m[6]-m[4]*m[10],m[4]*m[9]-m[8]*m[5],
                m[9]*m[2]-m[1]*m[10],m[0]*m[10]-m[8]*m[2],m[8]*m[1]-m[0]*m[9],
                m[1]*m[6]-m[5]*m[2],m[4]*m[2]-m[0]*m[6],m[0]*m[5]-m[4]*m[1]};
  float determinant=m[0]*cof[0]+m[4]*cof[3]+m[8]*cof[6];
  if(!std::isfinite(determinant)||determinant<=1e-8f)return false;
  Matrix next=rotation;float error=0;
  for(int c=0;c<3;++c)for(int r=0;r<3;++r){int at=c*4+r;next.v[at]=.5f*(m[at]+cof[c*3+r]/determinant);error=(std::max)(error,std::abs(next.v[at]-m[at]));}
  rotation=next;if(error<1e-6f)break;
 }
 return rigid(rotation);
}
static Matrix flipPoseAxis(const Matrix& m){Matrix out=m;for(int row=0;row<3;++row)out.v[row]=-out.v[row];return out;}
bool poseInterpolatable(const Matrix& m){return rigid(m)||rigid(flipPoseAxis(m));}
void blend(const Matrix& a,const Matrix& b,float t,Matrix& out){
 out=b;if(!std::isfinite(t))return;
 Matrix positiveA=a,positiveB=b;bool mirrored=false;
 if(!rigid(positiveA)||!rigid(positiveB)){
  positiveA=flipPoseAxis(a);positiveB=flipPoseAxis(b);
  if(!rigid(positiveA)||!rigid(positiveB))return;
  mirrored=true; // Common fixed reflection cancels before quaternion extraction.
 }
 if(t>=1)return;if(t<=0){out=a;return;}
 Matrix rotationA{},rotationB{};if(!rotationPart(positiveA,rotationA)||!rotationPart(positiveB,rotationB))return;
 auto stretchA=multiply(inverseRigid(rotationA),positiveA),stretchB=multiply(inverseRigid(rotationB),positiveB);
 Q x=quaternion(rotationA),y=quaternion(rotationB);float dot=x.x*y.x+x.y*y.y+x.z*y.z+x.w*y.w;
 if(dot<0){y.x=-y.x;y.y=-y.y;y.z=-y.z;y.w=-y.w;}
 Q q{x.x+(y.x-x.x)*t,x.y+(y.y-x.y)*t,x.z+(y.z-x.z)*t,x.w+(y.w-x.w)*t};
 float n=std::sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w);if(n<0.001f)return;q.x/=n;q.y/=n;q.z/=n;q.w/=n;
 out.v[0]=1-2*(q.y*q.y+q.z*q.z);out.v[1]=2*(q.x*q.y-q.z*q.w);out.v[2]=2*(q.x*q.z+q.y*q.w);
 out.v[4]=2*(q.x*q.y+q.z*q.w);out.v[5]=1-2*(q.x*q.x+q.z*q.z);out.v[6]=2*(q.y*q.z-q.x*q.w);
 out.v[8]=2*(q.x*q.z-q.y*q.w);out.v[9]=2*(q.y*q.z+q.x*q.w);out.v[10]=1-2*(q.x*q.x+q.y*q.y);
 Matrix rotation=out;
 for(int c=0;c<3;++c)for(int r=0;r<3;++r){out.v[c*4+r]=0;for(int k=0;k<3;++k)out.v[c*4+r]+=rotation.v[k*4+r]*(stretchA.v[c*4+k]+(stretchB.v[c*4+k]-stretchA.v[c*4+k])*t);}
 for(int i=12;i<15;++i)out.v[i]=a.v[i]+(b.v[i]-a.v[i])*t;
 if(mirrored)out=flipPoseAxis(out);
}
Matrix multiply(const Matrix& a,const Matrix& b){Matrix o{};for(int c=0;c<4;++c)for(int r=0;r<4;++r)for(int k=0;k<4;++k)o.v[c*4+r]+=a.v[k*4+r]*b.v[c*4+k];return o;}
Matrix inverseRigid(const Matrix& m){
 // rigid() allows small native stretch/shear: transpose is not its inverse.
 // Callers retain the existing near-rigid admission guard; unsupported input is unchanged.
 if(!rigid(m))return m;
 const double a=m.v[0],b=m.v[4],c=m.v[8],d=m.v[1],e=m.v[5],f=m.v[9],g=m.v[2],h=m.v[6],i=m.v[10];
 const double determinant=a*(e*i-f*h)+b*(f*g-d*i)+c*(d*h-e*g);
 if(!std::isfinite(determinant)||determinant<=1e-8)return m;
 Matrix o{};o.v[15]=1;
 o.v[0]=float((e*i-f*h)/determinant);o.v[4]=float((c*h-b*i)/determinant);o.v[8]=float((b*f-c*e)/determinant);
 o.v[1]=float((f*g-d*i)/determinant);o.v[5]=float((a*i-c*g)/determinant);o.v[9]=float((c*d-a*f)/determinant);
 o.v[2]=float((d*h-e*g)/determinant);o.v[6]=float((b*g-a*h)/determinant);o.v[10]=float((a*e-b*d)/determinant);
 for(int row=0;row<3;++row){double translation=0;for(int k=0;k<3;++k)translation-=double(o.v[k*4+row])*m.v[12+k];o.v[12+row]=float(translation);}
 return o;
}
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
