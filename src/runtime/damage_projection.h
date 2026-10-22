#pragma once
#include <windows.h>
bool setDamageProjection(BYTE* image,size_t available,bool enabled);
bool installDamageProjection(HMODULE engine,void(*logger)(const wchar_t*));
#ifdef DAMAGE_PROJECTION_TEST
void initializeDamageProjectionFixture(BYTE* image);
void damageProjectionWriteFailure(int index);
void damageProjectionFixtureDriver(BYTE* driver);
#endif
