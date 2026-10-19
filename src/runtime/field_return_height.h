#pragma once
#include <windows.h>
bool installFieldReturnHeight(HMODULE, void(*)(const wchar_t*));
bool removeFieldReturnHeight(HMODULE);
#ifdef FIELD_RETURN_HEIGHT_TEST
using FieldPosition = void(__thiscall*)(void*,float,float,float);
void initializeFieldReturnHeightFixture(BYTE*);
void configureFieldReturnHeightFixture(FieldPosition);
void invokeFieldReturnHeightFixture(void*,float,float,float);
#endif
