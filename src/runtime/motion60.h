#pragma once
#include <windows.h>
bool removeMotion60(HMODULE engine);
bool installMotion60(HMODULE engine, void(*logger)(const wchar_t*));
#ifdef MOTION60_TEST
struct MotionMatrix { float v[16]; };
void motion60TestBlend(const MotionMatrix&,const MotionMatrix&,float,MotionMatrix&);
#endif
#ifdef MOTION60_TEST
using MotionRenderFn=void(__thiscall*)(void*,int,MotionMatrix*,int,int,int,int,int);
using MotionAbsoluteFn=void(__cdecl*)(void*,unsigned,MotionMatrix*,MotionMatrix*);
void motion60TestConfigure(MotionRenderFn,MotionAbsoluteFn);
void motion60TestSetTime(double milliseconds);
void motion60TestRender(void*,int);
void motion60TestAbsolute(void*,unsigned,MotionMatrix*,MotionMatrix*);
#endif

#ifdef MOTION60_TEST
bool motion60TestSetMapped(BYTE*,size_t,MotionAbsoluteFn,bool);
void motion60TestInitialize(BYTE*,MotionAbsoluteFn);
#endif
