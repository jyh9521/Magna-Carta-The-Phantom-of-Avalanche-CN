#pragma once
#include <windows.h>
bool installWideUi(HMODULE module,void(*logger)(const wchar_t*));
bool setWideUi(BYTE* image,size_t available,bool enabled);
#ifdef WIDE_UI_TEST
void configureWideUiWriteFailureFixture(int site);
void initializeWideUiFixture(BYTE* image);
void configureWideUiMouseFixture(BOOL(WINAPI* fn)(int,int));
#endif
