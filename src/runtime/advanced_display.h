#pragma once
#include <windows.h>
#include <string>
bool advancedConfigMatches(const std::wstring&,const std::string&);
bool setRenderWait(BYTE* image,size_t available,bool unlocked);
bool setCameraAspect(BYTE* image,size_t available,bool enabled);
bool setZeroDeltaFps(BYTE* image,size_t available,bool enabled);
bool installAdvancedEngine(HMODULE,bool wide,bool render60,void(*logger)(const wchar_t*));
bool installAdvancedDriver(HMODULE,bool wide,bool render60,void(*logger)(const wchar_t*));
double expandedAspect(double original,int matrixMode,bool enabled);
unsigned fixedUpdates(unsigned elapsed,unsigned& remainder,unsigned interval=33);
#ifdef ADVANCED_DISPLAY_TEST
using PerspectiveFn=void(__thiscall*)(void*,double,double,double,double);
using PresentFn=BYTE(__thiscall*)(void*);
void configureAdvancedFixture(PerspectiveFn,PresentFn);
void configurePacingClockFixture(LONGLONG frequency,LONGLONG overshoot);
void advancePacingClockFixture(LONGLONG elapsed);
LONGLONG pacingClockFixtureNow();
void resetPacingClockFixture();
void initializeAdvancedEngineFixture(BYTE* image);
void initializeAdvancedDriverFixture(BYTE* image);
#endif
