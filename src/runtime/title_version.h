#pragma once
#include <windows.h>
bool installTitleVersion(HMODULE, void(*)(const wchar_t*));
bool removeTitleVersion();
#ifdef TITLE_VERSION_TEST
void initializeTitleVersionFixture(BYTE*);
#endif
