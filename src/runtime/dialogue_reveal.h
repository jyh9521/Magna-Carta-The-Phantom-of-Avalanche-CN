#pragma once
#include <windows.h>
bool installDialogueReveal(HMODULE,void(*)(const wchar_t*));
bool removeDialogueReveal(HMODULE);
#ifdef DIALOGUE_REVEAL_TEST
void initializeDialogueRevealFixture(BYTE*);
void configureDialogueRevealFixture(int(__thiscall*)(void*,void*,int,int,int),void(__thiscall*)(void*),void(__thiscall*)(void*));
void configureDialogueVoiceFixture(void(__thiscall*)(void*),int(__thiscall*)(void*,int),void*);
void startDialogueVoiceFixture(BYTE*,BYTE*,int);
void expireDialogueVoiceDeadlineFixture();
#endif

void* dialogueCaptionStream(void*);
