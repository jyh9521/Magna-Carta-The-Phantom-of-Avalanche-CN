#pragma once
#include <windows.h>
bool installWorldGamepad(HMODULE,void(*logger)(const wchar_t*));
bool removeWorldGamepad(HMODULE);
bool canSetWorldGamepad(HMODULE,bool enabled);
