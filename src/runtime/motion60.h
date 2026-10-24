#pragma once
#include <windows.h>
bool removeMotion60(HMODULE engine);
bool installMotion60(HMODULE engine, void(*logger)(const wchar_t*));
bool installMotion60Driver(HMODULE driver,void(*logger)(const wchar_t*));
bool removeMotion60Driver(HMODULE driver);
#ifdef MOTION60_TEST
struct MotionMatrix { float v[16]; };
void motion60TestBlend(const MotionMatrix&,const MotionMatrix&,float,MotionMatrix&);
void motion60TestComplete(BYTE* engine,bool enabled);
void motion60TestTick(unsigned consumed,unsigned remainder,unsigned timestamp);
void motion60TestDiagnosticLogger(void(*)(const wchar_t*));
void motion60TestPrepareHistory(void*,int);
void motion60TestCamera(void* driver,MotionMatrix*,void(__thiscall*)(void*,MotionMatrix*));
bool motion60TestTimerPatch(BYTE*,bool);
bool motion60TestDriverSet(BYTE*,bool);
bool motion60TestCameraSiteMatches(BYTE*);
#endif
#ifdef MOTION60_TEST
using MotionRenderFn=void(__thiscall*)(void*,int,MotionMatrix*,int,int,int,int,int);
using MotionAbsoluteFn=void(__cdecl*)(void*,unsigned,MotionMatrix*,MotionMatrix*);
void motion60TestConfigure(MotionRenderFn,MotionAbsoluteFn);
void motion60TestSetTime(double milliseconds);
void motion60TestRender(void*,int);
void motion60TestRenderParent(void*,int,MotionMatrix*);
void motion60TestAbsolute(void*,unsigned,MotionMatrix*,MotionMatrix*);
#endif

#ifdef MOTION60_TEST
bool motion60TestSetMapped(BYTE*,size_t,MotionAbsoluteFn,bool);
void motion60TestInitialize(BYTE*,MotionAbsoluteFn);
#endif

#ifdef MOTION60_TEST
void motion60TestFreeView(bool enabled,bool toggle,bool reset,float yaw,float seconds);
#endif

#ifdef MOTION60_TEST
bool motion60TestNativeMapped(BYTE*,size_t,bool);
bool motion60TestNativeSource(void*,bool);
#endif

void motion60SceneBoundary(void*,unsigned,unsigned);
void motion60SceneCut();
