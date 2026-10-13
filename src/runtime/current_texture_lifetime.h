#pragma once
#include <windows.h>
bool installCurrentTextureLifetime(HMODULE,void(*)(const wchar_t*));
bool removeCurrentTextureLifetime(HMODULE);
#ifdef CURRENT_TEXTURE_TEST
using CurrentDeleteFn=DWORD(__thiscall*)(void*,int,const DWORD*);
void configureCurrentTextureFixture(CurrentDeleteFn);
DWORD __fastcall currentTextureFixtureDelete(void*,void*,int,const DWORD*);
#endif
