#include <windows.h>
#include <cstring>
#include <cwchar>

namespace {
wchar_t session[512]{};
wchar_t logPath[32768]{};
constexpr char gameKey[] = "SOFTWARE\\Softmax\\MagnaCarta";

void trace(const wchar_t* message) {
    HANDLE f = CreateFileW(logPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return;
    char text[8192];
    int n = WideCharToMultiByte(CP_UTF8, 0, message, -1, text, sizeof(text), nullptr, nullptr);
    DWORD written;
    if (n > 1) WriteFile(f, text, n - 1, &written, nullptr);
    WriteFile(f, "\r\n", 2, &written, nullptr);
    CloseHandle(f);
}

bool gameKeyMatch(HKEY root, LPCSTR key) {
    if (root != HKEY_LOCAL_MACHINE || !key) return false;
    size_t prefix = sizeof(gameKey) - 1;
    if (_strnicmp(key, gameKey, prefix) || (key[prefix] && key[prefix] != '\\')) return false;
    return true;
}

bool redirect(HKEY root, LPCSTR key, wchar_t* result, size_t capacity) {
    if (!gameKeyMatch(root, key)) return false;
    size_t prefix = sizeof(gameKey) - 1;
    wchar_t suffix[512]{};
    if (!MultiByteToWideChar(CP_ACP, 0, key + prefix, -1, suffix, 512)) return false;
    if (swprintf_s(result, capacity, L"%s%s", session, suffix) < 0) return false;
    return true;
}

LSTATUS WINAPI openKey(HKEY root, LPCSTR key, DWORD options, REGSAM access, PHKEY output) {
    wchar_t path[1024];
    if (redirect(root, key, path, 1024)) {
        trace(L"REG_OPEN redirected");
        return RegOpenKeyExW(HKEY_CURRENT_USER, path, options,
            access & ~(KEY_WOW64_32KEY | KEY_WOW64_64KEY), output);
    }
    if (gameKeyMatch(root, key)) return ERROR_INVALID_NAME;
    return RegOpenKeyExA(root, key, options, access, output);
}

LSTATUS WINAPI createKey(HKEY root, LPCSTR key, DWORD reserved, LPSTR cls, DWORD options,
    REGSAM access, LPSECURITY_ATTRIBUTES security, PHKEY output, LPDWORD disposition) {
    wchar_t path[1024];
    if (redirect(root, key, path, 1024)) {
        trace(L"REG_CREATE redirected");
        return RegCreateKeyExW(HKEY_CURRENT_USER, path, reserved, nullptr, options,
            access & ~(KEY_WOW64_32KEY | KEY_WOW64_64KEY), security, output, disposition);
    }
    if (gameKeyMatch(root, key)) return ERROR_INVALID_NAME;
    return RegCreateKeyExA(root, key, reserved, cls, options, access, security, output, disposition);
}

void patch(HMODULE module);
void dependencies() {
    const wchar_t* names[] = {L"MCAlpha.dll", L"Asura.dll", L"MCSetup.exe"};
    for (const wchar_t* name : names) {
        if (HMODULE module = GetModuleHandleW(name)) patch(module);
    }
}
void loaded(HMODULE module) {
    wchar_t path[32768]{};
    if (GetModuleFileNameW(module, path, 32768)) {
        wchar_t message[33000];
        swprintf_s(message, L"MODULE_LOADED path=%s", path);
        trace(message);
    }
}
HMODULE WINAPI loadA(LPCSTR name) {
    HMODULE result = LoadLibraryA(name);
    if (result) { loaded(result); patch(result); dependencies(); }
    return result;
}
HMODULE WINAPI loadW(LPCWSTR name) {
    HMODULE result = LoadLibraryW(name);
    if (result) { loaded(result); patch(result); dependencies(); }
    return result;
}

void patch(HMODULE module) {
    wchar_t path[32768]{};
    if (!GetModuleFileNameW(module, path, 32768)) return;
    const wchar_t* base = wcsrchr(path, L'\\');
    base = base ? base + 1 : path;
    bool allowed = module == GetModuleHandleW(nullptr) ||
        !_wcsicmp(base, L"MCAlpha.dll") || !_wcsicmp(base, L"MCSetup.exe") ||
        !_wcsicmp(base, L"Asura.dll");
    if (!allowed) return;
    auto bytes = reinterpret_cast<BYTE*>(module);
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(bytes);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(bytes + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC) return;
    auto dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dir.VirtualAddress || dir.VirtualAddress >= nt->OptionalHeader.SizeOfImage) return;
    unsigned changes = 0;
    auto desc = reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(bytes + dir.VirtualAddress);
    for (; desc->Name; ++desc) {
        if (!desc->OriginalFirstThunk) continue;
        auto names = reinterpret_cast<IMAGE_THUNK_DATA32*>(bytes + desc->OriginalFirstThunk);
        auto slots = reinterpret_cast<IMAGE_THUNK_DATA32*>(bytes + desc->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++slots) {
            if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
            auto name = reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(bytes + names->u1.AddressOfData)->Name;
            void* replacement = nullptr;
            if (!strcmp(reinterpret_cast<char*>(name), "LoadLibraryA")) replacement = reinterpret_cast<void*>(&loadA);
            if (!strcmp(reinterpret_cast<char*>(name), "LoadLibraryW")) replacement = reinterpret_cast<void*>(&loadW);
            if (!strcmp(reinterpret_cast<char*>(name), "RegOpenKeyExA")) replacement = reinterpret_cast<void*>(&openKey);
            if (!strcmp(reinterpret_cast<char*>(name), "RegCreateKeyExA")) replacement = reinterpret_cast<void*>(&createKey);
            if (!replacement || slots->u1.Function == reinterpret_cast<DWORD>(replacement)) continue;
            DWORD previous;
            if (!VirtualProtect(&slots->u1.Function, sizeof(DWORD), PAGE_READWRITE, &previous)) continue;
            InterlockedExchange(reinterpret_cast<LONG*>(&slots->u1.Function), reinterpret_cast<LONG>(replacement));
            DWORD ignored;
            VirtualProtect(&slots->u1.Function, sizeof(DWORD), previous, &ignored);
            ++changes;
        }
    }
    if (changes) {
        wchar_t text[33000];
        swprintf_s(text, L"IAT_READY changes=%u module=%s", changes, path);
        trace(text);
    }
}
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        if (!GetEnvironmentVariableW(L"MC_WORKSPACE_SESSION", session, 512) ||
            !GetEnvironmentVariableW(L"MC_WORKSPACE_LOG", logPath, 32768)) return FALSE;
        constexpr wchar_t prefix[] = L"Software\\MagnaCartaWorkspace\\Sessions\\";
        if (wcsncmp(session, prefix, wcslen(prefix))) return FALSE;
        patch(GetModuleHandleW(nullptr));
        trace(L"PROFILE_ATTACHED");
    }
    return TRUE;
}
