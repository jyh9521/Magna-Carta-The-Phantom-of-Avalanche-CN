#pragma once
#include <windows.h>
bool installModernGamepad(HMODULE,void(*logger)(const wchar_t*));
#ifdef MODERN_INPUT_TEST
#include <Xinput.h>
void configureModernGamepadFixture(BOOL(WINAPI*)(PBYTE),DWORD(WINAPI*)(DWORD,XINPUT_STATE*),bool);
#endif
