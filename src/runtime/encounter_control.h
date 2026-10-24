#pragma once
#include <windows.h>
bool installEncounterControl(HMODULE,void(*)(const wchar_t*));
bool removeEncounterControl();
void encounterKeyboard(PBYTE,bool);
bool encountersEnabled();
const wchar_t* encounterStatus();
#ifdef ENCOUNTER_CONTROL_TEST
bool encounterTestMapped(BYTE*,size_t,bool);
void encounterTestReset();
void encounterTestPaint(HDC,int,int);
#endif
#include "frame_overlay.h"
bool encounterFramePanel(int,int,FramePanel&);
