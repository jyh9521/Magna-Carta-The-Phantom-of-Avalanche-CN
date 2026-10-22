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
 printf("BATTLE_INPUT PASS checks=%u native_space=true edge_only=true cadence=logic_ticks focus_cancel=true scene_cancel=true timeout=bounded game_started=false\n",checks);
}
