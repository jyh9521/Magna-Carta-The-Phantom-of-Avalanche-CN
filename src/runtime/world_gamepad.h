#pragma once
#include <windows.h>
bool installWorldGamepad(HMODULE,void(*logger)(const wchar_t*));
bool removeWorldGamepad(HMODULE);
bool canSetWorldGamepad(HMODULE,bool enabled);

using WorldTickObserver=void(*)(BYTE*,bool);
void setWorldTickObserver(WorldTickObserver);
void notifyWorldTickObserver(BYTE*,bool);
