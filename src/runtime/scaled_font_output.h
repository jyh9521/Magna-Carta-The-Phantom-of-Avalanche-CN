#pragma once
#include <string>
struct ScaledFontOutput { unsigned width=0,height=0; };
bool parseScaledFontOutput(const wchar_t* text,ScaledFontOutput& output);
bool resolveScaledFontOutput(const std::wstring& profile,const std::wstring& window,
                             unsigned desktopWidth,unsigned desktopHeight,ScaledFontOutput& output);
bool highScaledFontOutput(const ScaledFontOutput& output);
