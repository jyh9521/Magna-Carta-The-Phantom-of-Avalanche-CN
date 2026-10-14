#include "ui_focus.h"
#include <cstdio>
#include <cstdlib>
int main(){using modern_input::FocusTarget;std::vector<FocusTarget> menu={{1,350,400,450,440},{2,350,450,450,490},{3,350,500,450,540},{4,350,550,450,590}};int checks=0;
 auto test=[&](bool b){++checks;if(!b){fprintf(stderr,"UI_FOCUS FAIL check=%d\n",checks);exit(1);}};
 test(modern_input::chooseFocus(menu,400,300,0,1)==0);test(modern_input::chooseFocus(menu,400,420,0,1)==1);test(modern_input::chooseFocus(menu,400,570,0,1)==0);test(modern_input::chooseFocus(menu,400,420,0,-1)==3);
 test(modern_input::chooseFocus(menu,400,470,1,0)==-1);test(modern_input::chooseFocus(menu,400,470,-1,0)==-1);
 std::vector<FocusTarget> grid={{1,0,0,20,20},{2,30,0,50,20},{3,0,30,20,50},{4,30,30,50,50}};
 test(modern_input::chooseFocus(grid,10,10,1,0)==1);test(modern_input::chooseFocus(grid,10,10,0,1)==2);test(modern_input::chooseFocus(grid,40,40,-1,0)==2);test(modern_input::chooseFocus(grid,40,40,0,-1)==1);
 test(modern_input::chooseFocus({},0,0,0,1)==-1);test(modern_input::chooseFocus(grid,10,10,1,1)==-1);
 printf("UI_FOCUS_FIXTURE PASS checks=%d directional=true wrap=true grid=true game_started=false\n",checks);
}
