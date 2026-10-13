#pragma once
#include <cstdint>
#include <vector>
namespace modern_input {
struct FocusTarget {uintptr_t identity;float left,top,right,bottom;};
int chooseFocus(const std::vector<FocusTarget>&,float x,float y,int dx,int dy);
}
