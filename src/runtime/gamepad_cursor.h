#pragma once
#include <cstdint>
namespace modern_input {
struct CursorPoint {float x=0,y=0;bool owned=false;};
class Cursor {
    float x_=0,y_=0;
    int physicalX_=0,physicalY_=0;
    bool initialized_=false,owned_=false,blocked_=false;
public:
    CursorPoint update(int physicalX,int physicalY,int16_t rightX,int16_t rightY,
                       unsigned elapsed,int width,int height,bool eligible);
    void focus(float x,float y,int width,int height);
    // Caller acknowledges only values it actually wrote to the game's cursor fields.
    void acknowledgeWrite(int x,int y){physicalX_=x;physicalY_=y;}
};
}
