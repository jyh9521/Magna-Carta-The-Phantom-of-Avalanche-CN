#pragma once
#include <cstdint>
namespace modern_input {
struct MoveIntent {float x=0,y=0,speed=0;bool active=false;};
// XY is the game's ground plane, Z is height. camera is a column-major view.
MoveIntent cameraRelative(int16_t x,int16_t y,uint16_t buttons,const float* camera,int deadzone=7849);
}
