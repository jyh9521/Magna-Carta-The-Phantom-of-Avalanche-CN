#pragma once
#include <windows.h>
#include <cstdint>
struct SampleCursor {uint64_t milliseconds=0,generation=0;bool running=false;};
bool installSampleClock(HMODULE,void(*)(const wchar_t*));
bool removeSampleClock(HMODULE);
bool sampleClockOwned(HMODULE);
bool sampleCursor(void*,SampleCursor&);
#ifdef SAMPLE_CLOCK_TEST
void sampleClockFixtureTime(uint64_t);
void sampleClockFixtureEvent(void*,unsigned);
#endif
