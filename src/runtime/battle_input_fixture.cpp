#include "battle_input.h"
#include <cstdio>
#include <cstdlib>
static unsigned checks=0;
void check(bool b,const char* m){++checks;if(!b){fprintf(stderr,"FAIL %s\n",m);exit(1);}}
int main(){
 using namespace combat_input;ComboAssist a;ComboState s{1,true,false,0,0,10,4};
 check(confirmKey(true,1)==32&&confirmKey(false,1)==1,"context-specific A key");
 check(a.update(s,true,true),"fresh trigger begins with native Space press");
 check(!a.update(s,true,true),"held trigger does not retrigger");
 s.timed=true;s.count=1;s.tick=9;check(!a.update(s,false,true),"before window");
 s.tick=11;check(a.update(s,false,true),"first center window pulse");
 check(!a.update(s,false,true),"intervening key up");
 check(!a.update(s,false,true),"same combo step once only");
 s.count=2;s.tick=21;check(a.update(s,false,true),"second center window pulse");
 s.count=3;check(!a.update(s,false,true),"key up after final pulse");check(!a.update(s,false,true)&&!a.pending(),"end after third native count");
 s.count=1;s.tick=11;check(a.update(s,true,true),"new request");
 check(!a.update(s,false,false)&&!a.pending(),"focus or device loss cancels");
 check(!a.update(s,false,true),"returning focus does not restart");
 check(a.update(s,true,true),"new explicit trigger after cancellation");s.owner=2;check(!a.update(s,true,true)&&!a.pending(),"scene identity change cancels");
 a.update(s,false,true);check(a.update(s,true,true),"new scene fresh trigger");a.update(s,false,true);s.tick=14;check(!a.update(s,false,true)&&!a.pending(),"expired window does not force success");
 s.tick=0;s.timed=false;check(a.update(s,true,true),"start pending request");for(unsigned i=0;i<92;++i)a.update(s,false,true);check(!a.pending(),"bounded wait");
 s.active=false;check(!a.update(s,true,true),"outside native combo sequence no action");
 // Render-only passes do not call this logic scheduler. Duplicate 60/30 draw
 // streams observe the exact same native tick pulse sequence.
 unsigned first[3]{},second[3]{};
 for(unsigned mode=0;mode<2;++mode){ComboAssist q;ComboState n{1,true,false,0,1,10,4};unsigned out=0;
  for(unsigned tick=0;tick<25;++tick){n.tick=tick;if(tick)n.timed=true;bool pulse=q.update(n,tick==0,true);if(pulse&&out<3){(mode?second:first)[out++]=tick;if(tick)n.count++;}}
  check(out==3,"three pulses including native first press");}
 for(unsigned i=0;i<3;++i)check(first[i]==second[i],"30/60 same native schedule");
 ComboAssist large;ComboState wide{3,true,false,0,1,300,300};unsigned largePulses=0;
 for(unsigned tick=0;tick<800;++tick){wide.tick=tick;if(tick)wide.timed=true;if(large.update(wide,tick==0,true)){++largePulses;if(tick)wide.count++;}}
 check(largePulses==3,"maximum interval completes beyond old 90-tick bound");
 ComboAssist takeover;ComboState mid{4,true,true,5,1,10,4};
 check(!takeover.update(mid,true,true)&&takeover.pending(),"mid-sequence trigger waits, not an early failed hit");
 mid.tick=11;check(takeover.update(mid,false,true),"takeover fires only inside native current window");
 ComboAssist late;mid.tick=14;check(!late.update(mid,true,true)&&!late.pending(),"late takeover does not issue an out-of-window pulse");
 // The narrow precision window precedes the loose center: 10/20, not 11/21.
 ComboAssist precise;ComboState ps{9,true,true,9,1,10,4};ps.precision=2;
 check(!precise.update(ps,true,true)&&precise.pending(),"precision2 request waits before scoring window");
 ps.tick=10;check(precise.update(ps,false,true),"precision2 first pulse at native scoring center tick10");
 ps.tick=11;check(!precise.update(ps,false,true),"precision2 key up");
 ps.count=2;ps.tick=19;check(!precise.update(ps,false,true),"precision2 second prewindow");
 ps.tick=20;check(precise.update(ps,false,true),"precision2 second pulse at native scoring center tick20");
 // Tick and combo count can reset while the battle scene pointer stays alive.
 ComboAssist rewind;ComboState rs{10,true,true,5,1,10,4};
 check(!rewind.update(rs,true,true)&&rewind.pending(),"rewind request starts");
 rs.tick=4;check(!rewind.update(rs,false,true)&&!rewind.pending(),"same-owner tick regression cancels");
 rs.tick=15;rs.count=2;check(!rewind.update(rs,true,true)&&rewind.pending(),"count rewind request starts");
 rs.count=1;rs.tick=16;check(!rewind.update(rs,false,true)&&!rewind.pending(),"same-owner count regression cancels");
 ComboAssist actorChange;ComboState identity{11,true,true,5,1,10,4};identity.actor=1;identity.action=2;
 check(!actorChange.update(identity,true,true)&&actorChange.pending(),"actor identity request starts");
 identity.actor=3;identity.tick=6;check(!actorChange.update(identity,false,true)&&!actorChange.pending(),"same-owner actor change cancels");
 ComboAssist actionChange;identity.actor=1;identity.tick=5;
 check(!actionChange.update(identity,true,true)&&actionChange.pending(),"action identity request starts");
 identity.action=3;identity.tick=6;check(!actionChange.update(identity,false,true)&&!actionChange.pending(),"same-owner action change cancels");
 ComboAssist precisionLate;ComboState lateState{12,true,true,12,1,10,6};lateState.precision=2;
 check(!precisionLate.update(lateState,true,true)&&!precisionLate.pending(),"loose-only takeover cancels without a downgraded pulse");
 ComboAssist releaseRewind;ComboState releaseState{13,true,true,10,1,10,6};releaseState.precision=2;
 check(releaseRewind.update(releaseState,true,true),"release regression starts with precision pulse");
 releaseState.tick=11;releaseState.count=2;check(!releaseRewind.update(releaseState,false,true),"release poll observes count2");
 releaseState.tick=12;releaseState.count=1;check(!releaseRewind.update(releaseState,false,true)&&!releaseRewind.pending(),"count regression after key-up cancels");
 printf("BATTLE_INPUT PASS checks=%u native_space=true edge_only=true cadence=logic_ticks focus_cancel=true scene_cancel=true timeout=bounded game_started=false\n",checks);
}
