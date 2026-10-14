#pragma once
#include "camera_relative_input.h"
#include <windows.h>
bool installModernGamepad(HMODULE,void(*logger)(const wchar_t*));
bool removeModernGamepad(HMODULE);
void modernGamepadWorldScope(bool enabled);
bool modernGamepadConsumeInteraction();
bool modernGamepadMenuCancellation();
bool modernGamepadCursorHidden();
modern_input::MoveIntent modernGamepadMoveIntent();
struct GamepadNavigation {unsigned held=0,pressed=0;DWORD serial=0,time=0;bool active=false;};
GamepadNavigation modernGamepadNavigation();
void modernGamepadFocusCursor(float x,float y);
#ifdef MODERN_INPUT_TEST
#include <Xinput.h>
void configureModernGamepadFixture(BOOL(WINAPI*)(PBYTE),DWORD(WINAPI*)(DWORD,XINPUT_STATE*),bool);
void configureModernNavigationFixture(BYTE*,GamepadNavigation);
#endif

unsigned modernGamepadMapButtons();
