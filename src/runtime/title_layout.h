#pragma once
#include <windows.h>
#include <cstddef>
bool setTitleLayout(BYTE*,size_t,bool);
bool installTitleLayout(HMODULE,void(*logger)(const wchar_t*));
#ifdef TITLE_LAYOUT_TEST
void initializeTitleLayoutFixture(BYTE*);
void configureTitleBackgroundFixture(bool enabled);
void configureTitleLayoutFixture(int physical,int canvas);
#endif
