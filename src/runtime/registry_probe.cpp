#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>

int main(int argc, char** argv) {
    bool write = argc > 1 && !strcmp(argv[1], "--write-session");
    HKEY key;
    LONG result = RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Softmax\\MagnaCarta", 0,
        KEY_READ | (write ? KEY_SET_VALUE : 0), &key);
    if (result != ERROR_SUCCESS) return 10;
    char directory[2048]{};
    BYTE setting[52]{};
    DWORD type, size = sizeof(directory);
    result = RegQueryValueExA(key, "Directory", nullptr, &type, reinterpret_cast<BYTE*>(directory), &size);
    if (result != ERROR_SUCCESS) return 11;
    size = sizeof(setting);
    LONG settingResult = RegQueryValueExA(key, "MCSetting", nullptr, &type, setting, &size);
    char* expected = nullptr;
    size_t expectedSize = 0;
    _dupenv_s(&expected, &expectedSize, "MC_PROBE_EXPECT_DIRECTORY");
    if (expected && strcmp(expected, directory)) return 12;
    if (write) {
        if (settingResult != ERROR_SUCCESS || size != 52 || setting[1] != 0) return 13;
        setting[0] ^= 1;
        if (RegSetValueExA(key, "MCSetting", 0, REG_BINARY, setting, 52) != ERROR_SUCCESS) return 14;
        const DWORD marker = 1234;
        if (RegSetValueExA(key, "WorkspaceProbe", 0, REG_DWORD, reinterpret_cast<const BYTE*>(&marker), 4) != ERROR_SUCCESS) return 15;
    }
    RegCloseKey(key);
    HMODULE kernel = LoadLibraryA("kernel32.dll");
    if (!kernel) return 16;
    FreeLibrary(kernel);
    printf("REGISTRY_PROBE PASS redirected=%s renderer=%s\n", expected ? "true" : "false",
        settingResult == ERROR_SUCCESS ? (setting[1] == 0 ? "direct3d" : "opengl") : "absent");
    free(expected);
    return 0;
}
