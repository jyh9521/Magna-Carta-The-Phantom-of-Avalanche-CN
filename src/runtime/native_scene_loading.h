#pragma once
#include <windows.h>
bool installNativeSceneLoading(HMODULE,void(*)(const wchar_t*));
bool removeNativeSceneLoading(HMODULE);
#ifdef NATIVE_SCENE_LOADING_TEST
void initializeNativeSceneLoadingFixture(BYTE*);
#endif
