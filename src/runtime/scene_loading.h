#pragma once
#include <windows.h>
bool installSceneLoading(HMODULE,void(*)(const wchar_t*));
bool removeSceneLoading(HMODULE);
#ifdef SCENE_LOADING_TEST
void initializeSceneLoadingFixture(BYTE*,BYTE*);
void setSceneLoadingFixtureDriver(BYTE*);
#endif
