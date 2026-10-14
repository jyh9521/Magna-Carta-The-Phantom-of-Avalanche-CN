#include "gamepad_cursor.h"
#include <cstdio>
#include <cstdlib>
int checks=0;void require(bool b,const char* t){++checks;if(!b){fprintf(stderr,"FAIL %s\n",t);exit(1);}}
int main(){modern_input::Cursor c;
 auto p=c.update(400,300,0,0,33,800,600,true);require(!p.owned&&p.x==400,"physical baseline");
 p=c.update(400,300,32767,0,33,800,600,true);require(p.owned&&p.x>420&&p.x<423,"right stick owns virtual cursor");
 p=c.update(400,300,0,0,33,800,600,true);require(p.owned&&p.x>420,"neutral retains position");
 p=c.update(100,150,32767,0,33,800,600,true);require(!p.owned&&p.x==100,"physical mouse wins immediately");
 p=c.update(100,150,32767,0,33,800,600,true);require(!p.owned,"held stick cannot steal cursor back");c.update(100,150,0,0,33,800,600,true);
 p=c.update(100,150,0,32767,33,800,600,true);require(p.owned&&p.y<150,"neutral rearms cursor");
 p=c.update(100,150,32767,0,99999,800,600,true);require(p.x<150,"long frame capped");
 p=c.update(100,150,32767,0,33,800,600,false);require(!p.owned,"focus loss releases");
 c.focus(900,700,800,600);p=c.update(100,150,0,0,0,800,600,true);require(!p.owned,"ineligible reset requires fresh acquisition");
 c.focus(9999,-100,800,600);p=c.update(100,150,0,0,0,800,600,true);require(p.owned&&p.x==799&&p.y==0,"focus clamp");
 modern_input::Cursor committed;committed.update(400,300,0,0,33,800,600,true);
 p=committed.update(400,300,32767,0,33,800,600,true);int px=int(p.x),py=int(p.y);committed.acknowledgeWrite(px,py);
 p=committed.update(px,py,32767,0,33,800,600,true);require(p.owned&&p.x>px,"acknowledged virtual write is not a new physical mouse move");
 committed.focus(500,420,800,600);committed.acknowledgeWrite(500,420);p=committed.update(500,420,0,0,33,800,600,true);
 require(p.owned&&p.x==500&&p.y==420,"acknowledged directional focus retains ownership");
 p=committed.update(480,410,32767,0,33,800,600,true);require(!p.owned&&p.x==480&&p.y==410,"different physical point still overrides acknowledged virtual cursor");
 p=committed.update(480,410,32767,0,33,800,600,true);require(!p.owned,"held stick stays blocked after genuine mouse override");
 committed.update(480,410,0,0,33,800,600,true);p=committed.update(480,410,32767,0,33,800,600,true);require(p.owned,"neutral rearms after acknowledged-write physical override");
 printf("GAMEPAD_CURSOR_FIXTURE PASS checks=%d virtual_only=true mouse_priority=true neutral_rearm=true game_started=false\n",checks);
}
