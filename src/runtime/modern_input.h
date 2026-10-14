#pragma once
#include <cstdint>

namespace modern_input {
enum Action : uint32_t { Up=1,Down=2,Left=4,Right=8,Confirm=16,Cancel=32,Menu=64 };
struct Sample {
    bool connected=false;
    uint32_t device=0;
    uint16_t buttons=0;
    int16_t x=0,y=0;
    int16_t rx=0,ry=0;
    uint8_t lt=0,rt=0;
};
struct Config {
    int engage=16000,release=10000;
    uint16_t confirm=0x1000,cancel=0x2000,menu=0x0010;
};
struct Frame { uint32_t held=0,pressed=0,released=0; bool armed=false; };
void mergeKeyboard(uint8_t* keys,const Frame&,const uint8_t (&bindings)[7]);
// Backend-neutral action state. No keyboard injection or game memory access.
// Menu stick direction is discrete and latched until recentering; world analog
// movement remains independent. D-pad always has explicit priority.
class MenuDirection {
    uint32_t stick=0;
public:
    uint32_t update(const Sample&,bool eligible);
};
class Router {
    Config config;
    uint32_t held=0,device=0;
    bool ready=false,connected=false,enabled=false,foreground=false;
    int axisX=0,axisY=0;
public:
    explicit Router(Config options={});
    Frame update(const Sample&,bool enabled,bool foreground);
};
}
