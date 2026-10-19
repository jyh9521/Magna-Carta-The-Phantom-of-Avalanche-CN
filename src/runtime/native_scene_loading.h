#pragma once
#include <windows.h>
bool installNativeSceneLoading(HMODULE,void(*)(const wchar_t*));
bool removeNativeSceneLoading(HMODULE);
#ifdef NATIVE_SCENE_LOADING_TEST
void initializeNativeSceneLoadingFixture(BYTE*,BYTE*);
void configureNativeSceneLoadingFixture(BYTE*,void(__cdecl*)(void*),void(__cdecl*)());
#endif
