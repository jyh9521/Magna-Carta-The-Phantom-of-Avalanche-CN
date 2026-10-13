#pragma once
#include <windows.h>
bool installTitleTexture(HMODULE engine,HMODULE asura,void(*logger)(const wchar_t*));
bool setTitleTexture(BYTE* engine,BYTE* asura,bool enabled,void(*logger)(const wchar_t*));
