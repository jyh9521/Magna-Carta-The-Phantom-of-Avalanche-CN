#pragma once
#include <windows.h>
bool installTextureLifetime(HMODULE module, void(*logger)(const wchar_t*));
#ifdef TEXTURE_LIFETIME_TEST
using TextureBindFn = DWORD(__thiscall*)(void*, DWORD, DWORD);
using TextureDeleteFn = DWORD(__thiscall*)(void*, int, const DWORD*);
void configureTextureFixture(TextureBindFn bind, TextureDeleteFn erase);
DWORD __fastcall fixtureBind(void*, void*, DWORD, DWORD);
DWORD __fastcall fixtureDelete(void*, void*, int, const DWORD*);
#endif
