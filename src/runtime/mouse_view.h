#pragma once
#include <windows.h>
bool installMouseView(HMODULE,void(*logger)(const wchar_t*));
bool removeMouseView();
