#pragma once
#include <windows.h>
bool installCollisionGuard(HMODULE,void(*)(const wchar_t*));
bool removeCollisionGuard(HMODULE);
#ifdef COLLISION_GUARD_TEST
void initializeCollisionGuardFixture(BYTE*);
void configureCollisionGuardFixture(void(__thiscall*)(void*),int(__thiscall*)(void*,float,float,float),void(__thiscall*)(void*,float,float,float));
void invokeCollisionGuardFixture(void*);
#endif
