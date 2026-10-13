#pragma once
#include <windows.h>
bool installGamepadUi(HMODULE,void(*logger)(const wchar_t*));
bool removeGamepadUi(HMODULE);
bool canSetGamepadUi(HMODULE,bool enabled);
#ifdef MODERN_INPUT_TEST
void initializeGamepadUiFixture(BYTE*);
#endif
