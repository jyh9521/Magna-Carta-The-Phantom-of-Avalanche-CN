#pragma once
#include <windows.h>
#include <cstddef>
bool menuPhaseVisible(int phase);
bool menuVisibilityImageMatches(unsigned char* image,size_t available);
bool installMenuVisibility(HMODULE module,void(*logger)(const wchar_t*));
bool removeMenuVisibility(); // Controlled fixtures only; not hot-unload during rendering.
