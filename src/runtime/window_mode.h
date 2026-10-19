#pragma once
#include <windows.h>
bool setNativeWindowed(BYTE* image,size_t available,bool enabled);
bool parseWindowResolution(const wchar_t* value,int& width,int& height);
bool resizeWindowClient(HWND window,int width,int height);
bool installWindowSizing(BYTE* image,size_t available,int width,int height,void(*logger)(const wchar_t*));
bool installWindowPresentation(BYTE* image,size_t available);
#ifdef WINDOW_SIZE_TEST
void configureWindowApisFixture(decltype(&CreateWindowExA) create,decltype(&GetCursorPos) get,decltype(&SetCursorPos) set);
void configureWindowSizeFixture(HWND window,int width,int height,ULONG_PTR caller);
BOOL offsetWindowSizeFixture(LPRECT rect,int x,int y,ULONG_PTR caller);
POINT mapWindowSizeFixture(POINT point,POINT origin,int fw,int fh,int tw,int th);
#endif
