#pragma once
#include <windows.h>
// Optional observation only. Never changes collision results or audio state.
bool installContactAudioTrace(HMODULE,void(*)(const wchar_t*));
bool removeContactAudioTrace(HMODULE);
