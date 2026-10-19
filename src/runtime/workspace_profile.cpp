#include "map_overlay.h"
#include "window_mode.h"
#include "world_gamepad.h"
#include "current_texture_lifetime.h"
#include <windows.h>
#include <cstring>
#include <cwchar>
#include "texture_lifetime.h"
#include "focus_guard.h"
#include "native_text_step.h"
#include "dialogue_reveal.h"
#include "field_return_height.h"
#include "gui_parent_guard.h"
#include "native_font.h"
#include "system_messages.h"
#include "modern_gamepad.h"
#include "advanced_display.h"
#include "wide_ui.h"
#include "menu_visibility.h"
#include "motion60.h"
#include "title_layout.h"
#include "title_style.h"
#include "mouse_view.h"

namespace {
wchar_t session[512]{};
wchar_t logPath[32768]{};
wchar_t captureHelper[32768]{};
bool textureLifetime = false;
bool focusGuard = false;
bool nativeTextStep = false;
bool systemMessages = false;
bool modernInput = false;
bool mapOverlay=false,cameraInput=false;
bool wideDisplay=false,render60=false,titleBackground4k=false;
wchar_t textureDriverPath[32768]{};
using MessageFunction = int(WINAPI*)(HWND, LPCSTR, LPCSTR, UINT);
MessageFunction originalExceptionMessage = MessageBoxA;
MessageFunction originalSystemMessage = MessageBoxA;
int WINAPI localizedSystemMessage(HWND owner,LPCSTR text,LPCSTR caption,UINT flags) {
    return dispatchSystemMessage(owner,text,caption,flags,originalSystemMessage,MessageBoxW);
}
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
int WINAPI exceptionMessage(HWND owner, LPCSTR text, LPCSTR caption, UINT type) {
    if (caption && !strcmp(caption, "Exception") && captureHelper[0]) {
        wchar_t output[32768]{};
        wcscpy_s(output, logPath);
        wchar_t* slash = wcsrchr(output, L'\\');
        if (slash) {
            *slash = 0;
            wchar_t dump[32768]{};
            swprintf_s(dump, L"%s\\engine-%lu-%llu.dmp", output, GetCurrentProcessId(), GetTickCount64());
            wchar_t command[65536]{};
            swprintf_s(command, L"\"%s\" --pid %lu --output \"%s\"", captureHelper, GetCurrentProcessId(), dump);
            STARTUPINFOW start{}; start.cb = sizeof(start);
            PROCESS_INFORMATION info{};
            if (CreateProcessW(captureHelper, command, nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
                               nullptr, nullptr, &start, &info)) {
                DWORD waited = WaitForSingleObject(info.hProcess, 30000), code = 1;
                if (waited == WAIT_OBJECT_0) GetExitCodeProcess(info.hProcess, &code);
                trace(waited == WAIT_OBJECT_0 && code == 0 ? L"ENGINE_FULL_CAPTURE_PASS" : L"ENGINE_FULL_CAPTURE_FAILED");
                CloseHandle(info.hThread); CloseHandle(info.hProcess);
            } else trace(L"ENGINE_FULL_CAPTURE_START_FAILED");
        }
    }
    // Preserve the original error dialog, return value and termination behavior.
    return originalExceptionMessage(owner, text, caption, type);
}
void dependencies() {
    const wchar_t* names[] = {L"MCAlpha.dll", L"Asura.dll", L"MCSetup.exe", L"Core.dll"};
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
    if (textureLifetime && !_wcsicmp(base, L"AsrD3DDrv.dll")) {
        bool matched = textureDriverPath[0] && !_wcsicmp(path, textureDriverPath);
        if(!matched || !(installCurrentTextureLifetime(module, trace) || installTextureLifetime(module, trace))){trace(L"TEXTURE_LIFETIME_REJECTED");ExitProcess(125);}
        trace(L"TEXTURE_LIFETIME_READY");
        if(!(wideDisplay||render60))return;
    }
    if(!_wcsicmp(base,L"AsrD3DDrv.dll")){
        wchar_t size[40]{};
        if(GetEnvironmentVariableW(L"MC_WINDOW_RESOLUTION",size,40)&&!installWindowPresentation(reinterpret_cast<BYTE*>(module),0x2c000)){trace(L"WINDOW_PRESENTATION_REJECTED");ExitProcess(125);}
    }
    if((wideDisplay||render60)&&!_wcsicmp(base,L"AsrD3DDrv.dll")) {
        if(!installAdvancedDriver(module,wideDisplay,render60,trace)){trace(L"ADVANCED_DRIVER_REJECTED");ExitProcess(125);}
        if((render60||cameraInput)&&!installMotion60Driver(module,trace)){trace(L"MOTION60_CAMERA_REJECTED");ExitProcess(125);}
        return;
    }
    bool exceptionModule = captureHelper[0] && !_wcsicmp(base, L"Core.dll");
    bool allowed = module == GetModuleHandleW(nullptr) ||
        !_wcsicmp(base, L"MCAlpha.dll") || !_wcsicmp(base, L"MCSetup.exe") ||
        !_wcsicmp(base, L"Asura.dll") || exceptionModule;
    if (!allowed) return;
    auto bytes = reinterpret_cast<BYTE*>(module);
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(bytes);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(bytes + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC) return;
    if (focusGuard && !_wcsicmp(base, L"MCAlpha.dll"))
        trace(installFocusGuard(module, trace) ? L"FOCUS_GUARD_READY" : L"FOCUS_GUARD_REJECTED");
    if (modernInput && !_wcsicmp(base,L"MCAlpha.dll") && !installModernGamepad(module,trace)) {
        trace(L"MODERN_INPUT_REJECTED");ExitProcess(125);
    }
    if(cameraInput&&!_wcsicmp(base,L"MCAlpha.dll")&&(!installWorldGamepad(module,trace)||!installMouseView(module,trace))){
        trace(L"CAMERA_INPUT_REJECTED");ExitProcess(125);
    }
    if(mapOverlay&&!_wcsicmp(base,L"MCAlpha.dll")){
        if(!installWorldGamepad(module,trace)||!installMapOverlay(module,trace)){trace(L"MAP_OVERLAY_REJECTED");ExitProcess(125);}
        setWorldTickObserver(&observeMapWorld);
    }
    if((wideDisplay||render60)&&!_wcsicmp(base,L"MCAlpha.dll")&&!installAdvancedEngine(module,wideDisplay,render60,trace)){trace(L"ADVANCED_ENGINE_REJECTED");ExitProcess(125);}
    if (nativeTextStep && !_wcsicmp(base, L"MCAlpha.dll")) {
        if (!installNativeTextStep(module)) {
            trace(L"NATIVE_TEXT_STEP_REJECTED");
            ExitProcess(125);
        }
        trace(L"NATIVE_TEXT_STEP_READY");
        wchar_t reveal[8]{};
        if(!(GetEnvironmentVariableW(L"MC_DIALOGUE_REVEAL",reveal,8)==1 && reveal[0]==L'0') && !installDialogueReveal(module,trace)){trace(L"DIALOGUE_REVEAL_REJECTED");ExitProcess(125);}
    }
    wchar_t windowMode[8]{};
    if(!_wcsicmp(base,L"MCAlpha.dll") && GetEnvironmentVariableW(L"MC_WINDOWED",windowMode,8)==1 && windowMode[0]==L'1'){
        if(!setNativeWindowed(reinterpret_cast<BYTE*>(module),nt->OptionalHeader.SizeOfImage,true)){trace(L"NATIVE_WINDOW_MODE_REJECTED");ExitProcess(125);}
        wchar_t size[40]{};int width=0,height=0;
        DWORD length=GetEnvironmentVariableW(L"MC_WINDOW_RESOLUTION",size,40);
        if(length&&(length>=40||!parseWindowResolution(size,width,height)||!installWindowSizing(reinterpret_cast<BYTE*>(module),nt->OptionalHeader.SizeOfImage,width,height,trace))){trace(L"WINDOW_SIZE_REJECTED");ExitProcess(125);}
        trace(L"NATIVE_WINDOW_MODE windowed=true source_locked=true");
    }
    wchar_t guiParentFlag[8]{};
    if(!_wcsicmp(base,L"MCAlpha.dll") && GetEnvironmentVariableW(L"MC_GUI_PARENT_GUARD",guiParentFlag,8)==1 && guiParentFlag[0]==L'1'){
        if(!installGuiParentGuard(module,trace)){trace(L"GUI_PARENT_GUARD_REJECTED");ExitProcess(125);}
    }
    wchar_t fieldReturnFlag[8]{};
    if(!_wcsicmp(base,L"MCAlpha.dll") && GetEnvironmentVariableW(L"MC_FIELD_RETURN_HEIGHT",fieldReturnFlag,8)==1 && fieldReturnFlag[0]==L'1'){
        if(!installFieldReturnHeight(module,trace)){trace(L"FIELD_RETURN_HEIGHT_REJECTED");ExitProcess(125);}
    }
    bool localizedModule=systemMessages && !_wcsicmp(base,L"MCAlpha.dll");
    if (localizedModule && !systemMessageModuleMatches(module)) {
        trace(L"SYSTEM_MESSAGES_REJECTED");ExitProcess(125);
    }
    if(localizedModule && !installMenuVisibility(module,trace)) {
        trace(L"MENU_VISIBILITY_REJECTED");ExitProcess(125);
    }
      wchar_t titleStyleFlag[8]{};
      bool titleStyleEnabled=!(GetEnvironmentVariableW(L"MC_TITLE_STYLE",titleStyleFlag,8)==1&&titleStyleFlag[0]==L'0');
      if(localizedModule && titleStyleEnabled && !installTitleStyle(module,trace)) {
          trace(L"TITLE_STYLE_REJECTED");ExitProcess(125);
      }
    if(localizedModule && wideDisplay && !installWideUi(module,trace)) {
        trace(L"WIDE_UI_REJECTED");ExitProcess(125);
    }
    if(localizedModule && !installTitleLayout(module,trace)) {
        trace(L"TITLE_LAYOUT_REJECTED");ExitProcess(125);
    }
    if(localizedModule && (render60||cameraInput) && !installMotion60(module,trace)) {
        trace(L"MOTION60_REJECTED");ExitProcess(125);
    }
#ifdef NATIVE_FONT_DATA_HEADER
    if (localizedModule && !installNativeFont(module)) {
        trace(L"NATIVE_FONT_REJECTED");ExitProcess(125);
    }
    if (localizedModule) trace(L"NATIVE_FONT_READY");
#endif
    auto dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dir.VirtualAddress || dir.VirtualAddress >= nt->OptionalHeader.SizeOfImage) return;
    unsigned changes = 0;
    bool systemSlotPatched=false;
    auto desc = reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(bytes + dir.VirtualAddress);
    for (; desc->Name; ++desc) {
        if (!desc->OriginalFirstThunk) continue;
        auto names = reinterpret_cast<IMAGE_THUNK_DATA32*>(bytes + desc->OriginalFirstThunk);
        auto slots = reinterpret_cast<IMAGE_THUNK_DATA32*>(bytes + desc->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++slots) {
            if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
            auto name = reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(bytes + names->u1.AddressOfData)->Name;
            void* replacement = nullptr;
            if (exceptionModule) {
                if (!strcmp(reinterpret_cast<char*>(name), "MessageBoxA") ||
                    !strcmp(reinterpret_cast<char*>(name), "_MessageBoxA@16")) replacement = reinterpret_cast<void*>(&exceptionMessage);
                else continue;
            }
            if (!strcmp(reinterpret_cast<char*>(name), "LoadLibraryA")) replacement = reinterpret_cast<void*>(&loadA);
            if (!strcmp(reinterpret_cast<char*>(name), "LoadLibraryW")) replacement = reinterpret_cast<void*>(&loadW);
            if (!strcmp(reinterpret_cast<char*>(name), "RegOpenKeyExA")) replacement = reinterpret_cast<void*>(&openKey);
            if (!strcmp(reinterpret_cast<char*>(name), "RegCreateKeyExA")) replacement = reinterpret_cast<void*>(&createKey);
            bool messageSlot=localizedModule && !strcmp(reinterpret_cast<char*>(name),"MessageBoxA");
            if (messageSlot) replacement=reinterpret_cast<void*>(&localizedSystemMessage);
            if (messageSlot && slots->u1.Function==reinterpret_cast<DWORD>(replacement)) systemSlotPatched=true;
            if (!replacement || slots->u1.Function == reinterpret_cast<DWORD>(replacement)) continue;
            DWORD previous;
            if (!VirtualProtect(&slots->u1.Function, sizeof(DWORD), PAGE_READWRITE, &previous)) continue;
            if (exceptionModule) originalExceptionMessage = reinterpret_cast<MessageFunction>(slots->u1.Function);
            if (messageSlot) originalSystemMessage=reinterpret_cast<MessageFunction>(slots->u1.Function);
            InterlockedExchange(reinterpret_cast<LONG*>(&slots->u1.Function), reinterpret_cast<LONG>(replacement));
            if (messageSlot) systemSlotPatched=true;
            DWORD ignored;
            VirtualProtect(&slots->u1.Function, sizeof(DWORD), previous, &ignored);
            ++changes;
        }
    }
    if (localizedModule && !systemSlotPatched) {trace(L"SYSTEM_MESSAGES_IMPORT_REJECTED");ExitProcess(125);}
    if (localizedModule) trace(L"SYSTEM_MESSAGES_READY");
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
        GetEnvironmentVariableW(L"MC_CAPTURE_HELPER", captureHelper, 32768);
        wchar_t option[8]{};
        textureLifetime = GetEnvironmentVariableW(L"MC_TEXTURE_LIFETIME", option, 8) && !wcscmp(option, L"1");
        focusGuard = GetEnvironmentVariableW(L"MC_FOCUS_GUARD", option, 8) && !wcscmp(option, L"1");
        nativeTextStep = GetEnvironmentVariableW(L"MC_NATIVE_TEXT_STEP", option, 8) && !wcscmp(option, L"1");
        systemMessages = GetEnvironmentVariableW(L"MC_SYSTEM_MESSAGES",option,8) && !wcscmp(option,L"1");
        mapOverlay=GetEnvironmentVariableW(L"MC_MAP_OVERLAY",option,8)&&!wcscmp(option,L"1");
        cameraInput=GetEnvironmentVariableW(L"MC_FREE_VIEW",option,8)&&!wcscmp(option,L"1");
        modernInput = GetEnvironmentVariableW(L"MC_MODERN_INPUT",option,8) && !wcscmp(option,L"1");
        wideDisplay=GetEnvironmentVariableW(L"MC_WIDE_DISPLAY",option,8)&&!wcscmp(option,L"1");
        titleBackground4k=GetEnvironmentVariableW(L"MC_TITLE_BACKGROUND4K",option,8)&&!wcscmp(option,L"1");
        render60=GetEnvironmentVariableW(L"MC_RENDER60",option,8)&&!wcscmp(option,L"1");
        GetEnvironmentVariableW(L"MC_TEXTURE_DRIVER", textureDriverPath, 32768);
        patch(GetModuleHandleW(nullptr));
        trace(L"PROFILE_ATTACHED");
    }
    return TRUE;
}
