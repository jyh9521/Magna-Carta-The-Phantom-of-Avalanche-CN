#pragma once
#include <windows.h>
#include <cstddef>
#include <string>

bool installNativeFont(HMODULE module);
bool nativeFontImageMatches(unsigned char* image,size_t available);
bool removeNativeFont(); // Controlled tests only; do not hot-unload while rendering.
bool translateNativeLabel(const char* input,std::string& output);
unsigned blendNativePixel(unsigned destination,unsigned source,unsigned coverage);
bool drawNativeCoverage(void* font,int x,int y,const unsigned char* text,int* advance,unsigned* pixels,int pitch);
