#pragma once
#include <windows.h>
#include <string>
struct SystemRule { const wchar_t* source; const wchar_t* target; };
using SystemMessageA = int(WINAPI*)(HWND,LPCSTR,LPCSTR,UINT);
using SystemMessageW = int(WINAPI*)(HWND,LPCWSTR,LPCWSTR,UINT);
bool translateSystemMessage(const std::wstring& input,std::wstring& output);
int dispatchSystemMessage(HWND owner,LPCSTR text,LPCSTR caption,UINT flags,SystemMessageA original,SystemMessageW unicode);
bool systemMessageModuleMatches(HMODULE module);
