#pragma once
#include <windows.h>
// Opt-in source-locked provider selection. Native allocation and playback remain native.
bool installAudioProviderPolicy(HMODULE module, void(*logger)(const wchar_t*));
bool removeAudioProviderPolicy(HMODULE module);
