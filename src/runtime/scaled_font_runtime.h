#pragma once
#include <windows.h>
using ScaledOriginalGlyph=int(__thiscall*)(void*,int,int,const unsigned char*,int*,unsigned*,int);
// Observers only run inside the source-locked native text-cache build call.
void beginScaledText(void* object,int pitch);
void observeScaledGlyph(void* object,int x,int y,const unsigned char* text,int advance,
                        int pitch,ScaledOriginalGlyph original);
bool installScaledFontRuntime(HMODULE engine,void(*logger)(const wchar_t*));
bool removeScaledFontRuntime();
#ifdef SCALED_FONT_RUNTIME_TEST
void configureScaledRuntimeFixture(BYTE* engine);
void __fastcall scaledRasterFixture(void*,void*,const char*,unsigned*,int);
void* __fastcall scaledSlotFixture(void*,void*,int,int);
void __cdecl scaledUploadFixture(void*,unsigned*);
void __fastcall scaledReleaseFixture(void*,void*,void*);
size_t scaledRuntimeOwnedCount();
#endif
