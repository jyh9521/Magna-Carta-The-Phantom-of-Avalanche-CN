#pragma once
#include <windows.h>
bool installTitleStyle(HMODULE,void(*logger)(const wchar_t*));
bool removeTitleStyle();
#ifdef TITLE_STYLE_TEST
void titleStyleFixtureRenderer(void*,float*);
#endif
