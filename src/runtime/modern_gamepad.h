#pragma once
#include "camera_relative_input.h"
#include <windows.h>
bool installModernGamepad(HMODULE,void(*logger)(const wchar_t*),bool battleOnly=false);
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
void configureModernBattleFixture(bool native);
BOOL modernBattleKeyboardFixture(PBYTE keys,void* frame);
#endif

unsigned modernGamepadMapButtons();
void modernGamepadMapContext(const void* owner,unsigned generation,bool controlled);
unsigned modernGamepadConsumeMapCycles(bool active);

void setNativeKeyboardObserver(void(*)(PBYTE,bool));
