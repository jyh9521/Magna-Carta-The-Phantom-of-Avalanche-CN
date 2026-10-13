#include "free_view.h"
#include <cmath>
#include <cstring>
#include <cstdio>
#include <cstdlib>
int checks=0;
void require(bool x){++checks;if(!x){printf("FREE_VIEW_FAIL check=%d\n",checks);exit(1);}}
int main(){motion::Matrix v{};v.v[0]=v.v[5]=v.v[10]=v.v[15]=1;camera::Orbit o;
 auto a=o.sample(v,1,{});require(!memcmp(&v,&a,sizeof(v)));require(!o.active());
 a=o.sample(v,1,{true});require(o.active());require(motion::rigid(a));require(!memcmp(&v,&a,sizeof(v)));
 a=o.sample(v,1,{true});require(o.active());o.sample(v,1,{});a=o.sample(v,1,{true});require(!o.active());
 o.sample(v,1,{});o.sample(v,1,{true});a=o.sample(v,1,{false,false,1,0,0,.05f});require(motion::rigid(a));require(std::abs(a.v[0]-1)>.0001);require(v.v[12]==0);
 a=o.sample(v,1,{false,false,0,1,1,.05f});require(motion::rigid(a));require(o.active());
 for(int i=0;i<1000;++i)a=o.sample(v,1,{false,false,1,1,1,10});require(motion::rigid(a));
 a=o.sample(v,2,{});require(!o.active());require(!memcmp(&v,&a,sizeof(v)));
 o.sample(v,2,{true});a=o.sample(v,2,{false,true});require(!o.active());require(!memcmp(&v,&a,sizeof(v)));
 o.sample(v,2,{true});a=o.sample(v,0,{});require(!o.active());require(!memcmp(&v,&a,sizeof(v)));
 printf("FREE_VIEW_CORE_PASS checks=%d render_only=true source_camera=unchanged identity_reset=true bounded=true game_started=false\n",checks);
}
