#include "camera_relative_input.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>
int checks=0;void require(bool v,const char* s){++checks;if(!v){fprintf(stderr,"FAIL %s\n",s);exit(1);}}
int main(){
 float camera[16]{};camera[0]=camera[5]=camera[10]=camera[15]=1;
 auto move=[&](int x,int y,unsigned b=0){return modern_input::cameraRelative(short(x),short(y),static_cast<uint16_t>(b),camera);};
 require(!move(0,0).active,"neutral");require(!move(7849,0).active,"radial deadzone boundary");
 auto m=move(32767,0);require(m.active&&m.x>.999f&&std::abs(m.y)<.001f&&m.speed==1,"screen right world right");
 m=move(0,32767);require(m.y>.999f&&std::abs(m.x)<.001f,"screen up world up");
 m=move(32767,32767);require(std::abs(std::hypot(m.x,m.y)-1)<.001f&&m.speed==1,"diagonal no speed boost");
 m=move(-32768,0);require(m.x<-.999f&&m.speed==1,"signed endpoint clamps");
 m=move(18000,0);require(m.speed>0&&m.speed<1,"analog magnitude");
 m=move(0,0,8);require(m.x>.999f&&m.speed==1,"dpad camera relative");require(!move(0,0,12).active,"opposite dpad cancels");
 camera[0]=0;camera[4]=1;camera[1]=-1;camera[5]=0;
 m=move(32767,0);require(m.y>.999f&&std::abs(m.x)<.001f,"rotated camera right");m=move(0,32767);require(m.x<-.999f,"rotated camera up");
 camera[0]=1;camera[4]=0;camera[1]=0;camera[5]=0;camera[6]=-1;
 require(move(0,32767).y>.999f,"horizontal camera forward fallback");
 camera[0]=camera[4]=0;require(!move(32767,0).active,"degenerate right bypass");camera[0]=std::nanf("");require(!move(32767,0).active,"nonfinite camera bypass");
 printf("CAMERA_RELATIVE_INPUT PASS checks=%d ground=XY direction=continuous magnitude=analog game_started=false\n",checks);
}
