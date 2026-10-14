#include "render_timeline.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <initializer_list>
using namespace motion;
int checks=0;
void require(bool b,const char* s){++checks;if(!b){std::fprintf(stderr,"FAIL %s\n",s);std::exit(1);}}
Matrix identity(float x=0){Matrix m{};m.v[0]=m.v[5]=m.v[10]=m.v[15]=1;m.v[12]=x;return m;}
bool near(float a,float b){return std::abs(a-b)<.001f;}
int main(){
 Timeline t;require(!t.phase().valid,"initial invalid");
 t.observe(1,33,0,0,100,true);auto p=t.phase();require(p.valid&&p.alpha==0,"source zero remainder");auto g=p.generation;
 t.observe(1,33,16,0,116,true);require(t.phase().tick==0&&near(t.phase().alpha,16.f/33),"no tick intermediate phase");
 t.observe(1,33,0,1,133,true);require(t.phase().tick==1&&t.phase().generation==g,"one real callback one tick");
 TransformTrack track;auto a=identity(0),b=identity(10);p={0,1,0,true};require(near(track.sample(a,p).v[12],0),"first no invented movement");
 p.tick=1;p.alpha=0;require(near(track.sample(b,p).v[12],0),"tick starts at previous world");
 p.alpha=.5f;require(near(track.sample(b,p).v[12],5),"world halfway");
 p.alpha=1;require(near(track.sample(b,p).v[12],10),"world endpoint");
 p.tick=2;p.alpha=.5f;auto rotate=identity(20);rotate.v[0]=-1;rotate.v[5]=-1;auto mid=track.sample(rotate,p);
 require(near(mid.v[12],15)&&std::abs(mid.v[0])<.001f&&std::abs(mid.v[1])>.99f,"world rotation and movement");
 auto before=b;track.sample(b,p);require(!std::memcmp(&before,&b,sizeof(b)),"input immutable");
 p.tick=4;require(near(track.sample(identity(30),p).v[12],30),"catchup skipped tick snaps");
 p.tick=5;require(near(track.sample(identity(4000),p).v[12],4000),"teleport snaps");
 ++p.generation;require(near(track.sample(identity(31),p).v[12],31),"scene generation snaps");
 p.valid=false;require(near(track.sample(identity(40),p).v[12],40),"invalid clock passthrough");
 p.valid=true;auto scaled=identity(50);scaled.v[0]=2;require(track.sample(scaled,p).v[0]==2,"scale passthrough");
 auto nan=identity();nan.v[12]=std::nanf("");require(std::isnan(track.sample(nan,p).v[12]),"nonfinite passthrough");
 TransformTrack cam;p={0,20,0,true};auto viewA=inverseRigid(identity(100));require(near(cam.sample(viewA,p,true).v[12],-100),"camera first");
 p.tick=1;p.alpha=.5f;auto viewB=inverseRigid(identity(120));auto view=cam.sample(viewB,p,true);require(near(inverseRigid(view).v[12],110),"camera pose rather than view translation");
 auto world=multiply(view,identity(12));auto recovered=multiply(inverseRigid(view),world);
 require(near(recovered.v[12],12),"strip smoothed view avoids double interpolation");
 auto r=rotate;r.v[12]=37;r.v[13]=11;auto product=multiply(r,inverseRigid(r));require(near(product.v[0],1)&&near(product.v[5],1)&&near(product.v[12],0)&&near(product.v[13],0),"column-major inverse");
 p.tick=2;require(near(cam.sample(inverseRigid(identity(2000)),p,true).v[12],-2000),"camera cut snaps");
 t.observe(1,33,0,5,150,true);require(!t.phase().valid,"overload drops interpolation");
 t.observe(1,33,0,1,170,true);g=t.phase().generation;t.observe(1,33,0,0,500,true);require(t.phase().generation!=g,"pause resets");
 g=t.phase().generation;t.observe(2,33,0,0,501,true);require(t.phase().generation!=g,"job lifecycle resets");
 t.observe(2,33,0,0,502,false);require(!t.phase().valid,"inactive callback no interpolation");
 t.observe(2,16,0,0,503,true);require(!t.phase().valid,"unknown interval rejects");
 t.observe(2,33,33,0,504,true);require(!t.phase().valid,"invalid remainder rejects");
 t.observe(2,33,0,0,0xfffffff0,true);g=t.phase().generation;t.observe(2,33,16,1,5,true);require(t.phase().generation==g,"timeGetTime wrap retains continuity");
 unsigned events=0;Timeline timer;for(unsigned ms=0;ms<330;++ms){unsigned n=(ms&&ms%33==0)?1:0;events+=n;timer.observe(7,33,ms%33,n,ms,true);}require(events==9&&timer.phase().tick==9,"33ms event count independent from render");
 auto stretchA=identity(),stretchB=identity(10);for(int k:{0,5,10})stretchA.v[k]=stretchB.v[k]=1.008f;
 require(rigid(stretchA)&&rigid(stretchB),"near-unit native stretch reaches existing accepted branch");
 Matrix stretchMid{};blend(stretchA,stretchB,.5f,stretchMid);
 require(near(stretchMid.v[0],1.008f)&&near(stretchMid.v[5],1.008f)&&near(stretchMid.v[10],1.008f),"intermediate pose must preserve accepted native stretch instead of breathing to unit scale");
 auto quarter=identity();quarter.v[0]=quarter.v[5]=0;quarter.v[1]=1;quarter.v[4]=-1;
 auto shear=identity();shear.v[4]=.005f;auto turned=multiply(quarter,shear);Matrix shearMid{};blend(shear,turned,.5f,shearMid);
 auto gram=[](const Matrix& m,int a,int b){float v=0;for(int k=0;k<3;++k)v+=m.v[a*4+k]*m.v[b*4+k];return v;};
 for(int a=0;a<3;++a)for(int b=0;b<3;++b)require(std::abs(gram(shearMid,a,b)-gram(shear,a,b))<1e-5f,"rotation must preserve accepted shear Gram metric");
 for(unsigned frame=0;frame<=60;++frame){Matrix m{};blend(stretchA,stretchB,float(frame)/60,m);require(std::abs(m.v[0]-1.008f)<1e-5f,"full display phase cannot pump source scale");}
 Matrix endpoint{};blend(shear,turned,0,endpoint);require(!memcmp(&endpoint,&shear,sizeof(endpoint)),"stretch endpoint zero byte exact");blend(shear,turned,1,endpoint);require(!memcmp(&endpoint,&turned,sizeof(endpoint)),"stretch endpoint one byte exact");
 auto inverseInput=multiply(quarter,shear);for(int c=0;c<3;++c)for(int r=0;r<3;++r)inverseInput.v[c*4+r]*=1.008f;
 inverseInput.v[12]=37;inverseInput.v[13]=-11;inverseInput.v[14]=4;
 require(rigid(inverseInput),"source inverse regression uses accepted near-rigid branch");
 auto inverse=inverseRigid(inverseInput);auto left=multiply(inverse,inverseInput),right=multiply(inverseInput,inverse);auto unit=identity();
 for(int k=0;k<16;++k)require(std::abs(left.v[k]-unit.v[k])<1e-5f&&std::abs(right.v[k]-unit.v[k])<1e-5f,"near-rigid inverse cancels native stretch and shear on both sides");
 auto twice=inverseRigid(inverse);for(int k=0;k<16;++k)require(std::abs(twice.v[k]-inverseInput.v[k])<1e-5f,"view to pose round trip preserves native near-rigid transform");
 TransformTrack nearCamera;Phase nearPhase{0,30,0,true};auto firstNear=nearCamera.sample(inverseInput,nearPhase,true);
 for(int k=0;k<16;++k)require(std::abs(firstNear.v[k]-inverseInput.v[k])<1e-5f,"camera first frame cannot change source transform through inverse round trip");
 std::printf("RENDER_TIMELINE_FIXTURE PASS checks=%d world=true rotation=true camera=true phase=engine_remainder logic_events=unchanged game_started=false\n",checks);
}
