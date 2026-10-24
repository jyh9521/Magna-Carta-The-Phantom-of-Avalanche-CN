#pragma once
struct CollisionVec {float x,y,z;};
using CollisionQuery = int(__cdecl*)(CollisionVec,void*); // 0=free, 1=solid, -1=unknown
#ifdef COLLISION_KERNEL_EXPORT
#define COLLISION_API extern "C" __declspec(dllexport)
#else
#define COLLISION_API extern "C"
#endif
// Uses the native horizontal sweep's 15-unit step-up clearance, not a new actor size.
// 0=unchanged, 1=clipped, 2=depenetrated, 3=deep/unresolved, 4=unknown input/query.
COLLISION_API unsigned __cdecl resolveCollisionStep(CollisionVec before,CollisionVec proposed,
 const CollisionVec* offsets,unsigned count,CollisionQuery query,void* context,CollisionVec* out);
