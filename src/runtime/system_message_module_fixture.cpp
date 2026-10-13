#include <windows.h>
#ifdef SYSTEM_MESSAGE_FIELDS_HEADER
#include SYSTEM_MESSAGE_FIELDS_HEADER
#endif
extern "C" __declspec(dllexport) int __cdecl SystemFixtureMessage(const char* text) {
    return MessageBoxA(reinterpret_cast<HWND>(0x1234),text,"Critical - Magna Carta",0x1010);
}
