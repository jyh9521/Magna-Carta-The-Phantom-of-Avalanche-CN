#pragma once
#include <windows.h>
#include <cstddef>

// Only the observed text-layout instruction is changed, never the disk image.
bool setNativeTextStep(BYTE* image, size_t available, bool enabled);
bool installNativeTextStep(HMODULE module);
unsigned nativeTextStepModel(unsigned lead, bool enabled);

#ifdef NATIVE_TEXT_STEP_TEST
void initializeTextStepFixture(BYTE* image, size_t available);
#endif
