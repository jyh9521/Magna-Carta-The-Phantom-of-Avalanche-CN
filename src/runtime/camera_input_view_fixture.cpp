#include "camera_input_view.h"
#include <cstdio>
#include <cstdlib>
unsigned checks=0;void require(bool b){++checks;if(!b){printf("INPUT_VIEW_FAIL check=%u\n",checks);exit(1);}}
int main(){render_input::InputView v;float source[16]{},out[16]{};source[0]=source[5]=source[10]=source[15]=1;
 require(!v.read(1,100,out));v.publish(source,1,100,false);require(!v.read(1,100,out));
 v.publish(source,1,100,true);require(v.read(1,100,out)&&!memcmp(source,out,sizeof(out)));require(v.read(1,350,out));require(!v.read(1,351,out));require(!v.read(2,100,out));
 out[0]=0;require(v.read(1,100,out)&&out[0]==1);require(source[0]==1);
 v.publish(source,1,0xfffffffau,true);require(v.read(1,10,out));
 source[0]=std::nanf("");v.publish(source,1,100,true);require(!v.read(1,100,out));source[0]=1;
 v.publish(source,1,100,true);v.reset();require(!v.read(1,100,out));
 printf("CAMERA_INPUT_VIEW PASS checks=%u identity=guarded age=bounded wrap=handled source=unchanged game_started=false\n",checks);
}
