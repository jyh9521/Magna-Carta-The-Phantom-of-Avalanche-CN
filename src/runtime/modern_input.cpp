#include "modern_input.h"
#include <stdexcept>
#include <cstdlib>

namespace modern_input {
void mergeKeyboard(uint8_t* keys,const Frame& frame,const uint8_t (&bindings)[7]) {
    if(!keys)return;
    for(unsigned i=0;i<7;++i)if(bindings[i] && (frame.held&(1u<<i)))keys[bindings[i]]|=0x80;
}
uint32_t MenuDirection::update(const Sample& s,bool eligible){
    if(!eligible){stick=0;return 0;}
    uint32_t d=s.buttons&15;
    if(d){stick=0;if((d&3)==3)d&=~3u;if((d&12)==12)d&=~12u;return (d&3)?(d&3):(d&12);}
    int x=std::abs(int(s.x)),y=std::abs(int(s.y));
    // Latch the axis, not an obsolete sign. Fast reversals can cross the
    // neutral range entirely between native polls. Release a latched axis
    // when its own component recenters, even if the other axis is active.
    if(((stick&(Up|Down))&&y<=11000)||((stick&(Left|Right))&&x<=11000))stick=0;
    if((stick==Up&&s.y<0&&y<19000)||(stick==Down&&s.y>0&&y<19000)||
       (stick==Left&&s.x>0&&x<19000)||(stick==Right&&s.x<0&&x<19000))stick=0;
    if(!stick&&((x>y?x:y)>=19000))stick=x>y?(s.x<0?Left:Right):(s.y<0?Down:Up);
    else if((stick&(Up|Down))&&y>=19000)stick=s.y<0?Down:Up;
    else if((stick&(Left|Right))&&x>=19000)stick=s.x<0?Left:Right;
    return stick;
}
Router::Router(Config options):config(options) {
    auto single=[](uint16_t b){return b && !(b&(b-1));};
    constexpr uint16_t faces=0xf000, menuButtons=0x0030;
    if(config.release<=0 || config.engage<=config.release || config.engage>32767 ||
       !single(config.confirm)||!single(config.cancel)||!single(config.menu)||
       !(config.confirm&faces)||!(config.cancel&faces)||!(config.menu&menuButtons)||
       config.confirm==config.cancel)
        throw std::invalid_argument("invalid input thresholds or duplicate/nonsemantic bindings");
}
static int axis(int value,int previous,const Config& c) {
    if(value>=c.engage)return 1;
    if(value<=-c.engage)return -1;
    if(previous==1 && value>c.release)return 1;
    if(previous==-1 && value<-c.release)return -1;
    return 0;
}
Frame Router::update(const Sample& s,bool on,bool front) {
    uint32_t before=held;
    bool transition=s.connected!=connected || (s.connected&&s.device!=device) || on!=enabled || front!=foreground;
    connected=s.connected;device=s.device;enabled=on;foreground=front;
    if(transition || !on || !front || !s.connected) {ready=false;axisX=axisY=0;held=0;}
    bool neutral=s.buttons==0 && s.x>=-config.release && s.x<=config.release && s.y>=-config.release && s.y<=config.release
        && s.rx>=-config.release && s.rx<=config.release && s.ry>=-config.release && s.ry<=config.release && s.lt<=30 && s.rt<=30;
    if(on && front && s.connected && !transition) {
        if(!ready && neutral)ready=true;
        if(ready) {
            axisX=axis(s.x,axisX,config);axisY=axis(s.y,axisY,config);
            uint32_t next=0;
            if((s.buttons&0x0001)||axisY>0)next|=Up;
            if((s.buttons&0x0002)||axisY<0)next|=Down;
            if((s.buttons&0x0004)||axisX<0)next|=Left;
            if((s.buttons&0x0008)||axisX>0)next|=Right;
            // Conflicting pad/stick directions cancel instead of arbitrary priority.
            if((next&(Up|Down))==(Up|Down))next&=~(Up|Down);
            if((next&(Left|Right))==(Left|Right))next&=~(Left|Right);
            if(s.buttons&config.confirm)next|=Confirm;
            if(s.buttons&config.cancel)next|=Cancel;
            if(s.buttons&config.menu)next|=Menu;
            held=next;
        }
    }
    return {held,held&~before,before&~held,ready};
}
}
