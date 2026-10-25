#pragma once
#include <windows.h>
struct FramePanel {int x=0,y=0,width=0,height=0;const DWORD* pixels=nullptr;HDC alphaDC=nullptr;};
using FramePanelSource=bool(*)(int,int,FramePanel&);
bool installFrameOverlay(HMODULE,void(*)(const wchar_t*));
bool removeFrameOverlay(HMODULE);
bool frameOverlayAvailable();
void setFramePanel(unsigned,FramePanelSource);
#ifdef FRAME_OVERLAY_TEST
void initializeFrameOverlayFixture(BYTE*,BYTE*);
void frameOverlayFixtureDriver(BYTE*);
void frameOverlayFixtureFocus(bool);
bool frameOverlayFixtureWindow(HWND,HWND);
#endif
