#pragma once
#include "frame_overlay.h"
bool installStoryCaptions(HMODULE,void(*)(const wchar_t*));
bool removeStoryCaptions(HMODULE);
bool storyCaptionPanel(int,int,FramePanel&);
#ifdef STORY_CAPTIONS_TEST
void storyCaptionFixture(BYTE*,BYTE*,unsigned(WINAPI*)(void*));
void storyCaptionFixtureFrame();
void storyCaptionFixtureReset();
unsigned storyCaptionFixtureCuts();
#endif
