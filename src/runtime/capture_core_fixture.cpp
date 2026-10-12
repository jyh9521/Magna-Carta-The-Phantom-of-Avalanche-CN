#include <windows.h>
// Linked against the fixture sink rather than user32.
extern "C" __declspec(dllexport) int WINAPI ShowFixtureException() {
    return MessageBoxA(nullptr, "Fixture access violation", "Exception", 0);
}
