#include "battle_edge.h"
extern "C" {
__declspec(dllexport) void* edge_create(){return new combat_input::SpaceEdgeLatch;}
__declspec(dllexport) void edge_destroy(void* p){delete static_cast<combat_input::SpaceEdgeLatch*>(p);}
__declspec(dllexport) void edge_sample(void* p,uintptr_t owner,uint32_t now,int valid){static_cast<combat_input::SpaceEdgeLatch*>(p)->sample(owner,now,valid!=0);}
__declspec(dllexport) void edge_message(void* p,uintptr_t owner,uint32_t now,uint32_t stamp,int down,int repeat,int valid){static_cast<combat_input::SpaceEdgeLatch*>(p)->message(owner,now,stamp,down!=0,repeat!=0,valid!=0);}
__declspec(dllexport) int edge_consume(void* p,uintptr_t owner,uint32_t now,int valid){return static_cast<combat_input::SpaceEdgeLatch*>(p)->consume(owner,now,valid!=0)?1:0;}
}
