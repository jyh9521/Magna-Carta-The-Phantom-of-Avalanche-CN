#pragma once
#include <windows.h>
#include <cstddef>
bool installGuiParentGuard(HMODULE, void(*)(const wchar_t*));
bool removeGuiParentGuard(HMODULE);
// Pure encoder also exercised by the offline fixture; no game/module loading.
size_t encodeGuiParentGuard(BYTE* output, DWORD engine, DWORD address);
#ifdef GUI_PARENT_GUARD_TEST
void initializeGuiParentGuardFixture(BYTE*);
#endif
