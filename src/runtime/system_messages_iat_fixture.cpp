#include "system_messages.h"
#include <cstring>
#include <cstdio>
#include <filesystem>
#include <vector>
#include SYSTEM_MESSAGE_RULES_HEADER
namespace {
std::wstring captured;int callsA=0,callsW=0;bool good=true;
int WINAPI sinkA(HWND owner,LPCSTR text,LPCSTR caption,UINT flags) {
    ++callsA;good &= owner==reinterpret_cast<HWND>(0x1234) && text && caption && flags==0x1010;return 17;
}
int WINAPI sinkW(HWND owner,LPCWSTR text,LPCWSTR caption,UINT flags) {
    ++callsW;good &= owner==reinterpret_cast<HWND>(0x1234) && text && caption && flags==0x1010;
    captured=text;return 29;
}
bool replaceImport(HMODULE module,const char* wanted,void* target) {
    auto base=reinterpret_cast<BYTE*>(module);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(base+dos->e_lfanew);
    auto imports=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    for (;imports->Name;++imports) {
        if (!imports->OriginalFirstThunk) continue;
        auto names=reinterpret_cast<IMAGE_THUNK_DATA32*>(base+imports->OriginalFirstThunk);
        auto slots=reinterpret_cast<IMAGE_THUNK_DATA32*>(base+imports->FirstThunk);
        for (;names->u1.AddressOfData;++names,++slots) {
            if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
            auto name=reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(base+names->u1.AddressOfData)->Name;
            if (strcmp(reinterpret_cast<char*>(name),wanted)) continue;
            DWORD old,ignored;if (!VirtualProtect(&slots->u1.Function,4,PAGE_READWRITE,&old)) return false;
            slots->u1.Function=reinterpret_cast<DWORD>(target);
            return VirtualProtect(&slots->u1.Function,4,old,&ignored)!=FALSE;
        }
    }
    return false;
}
FARPROC currentImport(HMODULE module,const char* wanted) {
    auto base=reinterpret_cast<BYTE*>(module);auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(base+dos->e_lfanew);
    auto imports=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    for (;imports->Name;++imports) {
        if (!imports->OriginalFirstThunk) continue;
        auto names=reinterpret_cast<IMAGE_THUNK_DATA32*>(base+imports->OriginalFirstThunk);
        auto slots=reinterpret_cast<IMAGE_THUNK_DATA32*>(base+imports->FirstThunk);
        for (;names->u1.AddressOfData;++names,++slots) {
            if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
            auto name=reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(base+names->u1.AddressOfData)->Name;
            if (!strcmp(reinterpret_cast<char*>(name),wanted))
                return reinterpret_cast<FARPROC>(*reinterpret_cast<volatile DWORD*>(&slots->u1.Function));
        }
    }
    return nullptr;
}
std::string encode(const wchar_t* text) {
    int n=WideCharToMultiByte(localeSystemCodePage,0,text,-1,nullptr,0,nullptr,nullptr);
    std::vector<char> b(n);WideCharToMultiByte(localeSystemCodePage,0,text,-1,b.data(),n,nullptr,nullptr);return b.data();
}
}
int wmain(int argc,wchar_t** argv) {
    if (argc!=4) return 2;
    bool modified=!wcscmp(argv[3],L"modified");
    SetEnvironmentVariableW(L"MC_WORKSPACE_SESSION",L"Software\\MagnaCartaWorkspace\\Sessions\\system-message-fixture");
    auto log=(std::filesystem::absolute(argv[2]).parent_path()/L"system-message-fixture.log").wstring();
    SetEnvironmentVariableW(L"MC_WORKSPACE_LOG",log.c_str());SetEnvironmentVariableW(L"MC_SYSTEM_MESSAGES",L"1");
    SetEnvironmentVariableW(L"MC_NATIVE_TEXT_STEP",L"0");SetEnvironmentVariableW(L"MC_FOCUS_GUARD",L"0");
    SetEnvironmentVariableW(L"MC_TEXTURE_LIFETIME",L"0");SetEnvironmentVariableW(L"MC_CAPTURE_HELPER",nullptr);
    HMODULE target=LoadLibraryW(argv[1]);if (!target) return 3;
    if (!replaceImport(target,"MessageBoxA",reinterpret_cast<void*>(&sinkA))) return 4;
    HMODULE profile=LoadLibraryW(argv[2]);if (!profile) return 5;
    // Suppress real windows: the Unicode import of the owned profile points to
    // an owned recording sink. No commercial image or game process is loaded.
    replaceImport(profile,"MessageBoxW",reinterpret_cast<void*>(&sinkW));
    using Loader=HMODULE(WINAPI*)(LPCWSTR);
    auto loader=reinterpret_cast<Loader>(currentImport(GetModuleHandleW(nullptr),"LoadLibraryW"));
    if (!loader || !loader(L"user32.dll")) return 6; // read the live IAT rather than a compiler-cached function pointer
    using Call=int(__cdecl*)(const char*);
    auto call=reinterpret_cast<Call>(GetProcAddress(target,"SystemFixtureMessage"));
    if (!call) call=reinterpret_cast<Call>(GetProcAddress(target,"_SystemFixtureMessage"));
    if (!call) return 7;
    unsigned cases=0;
    for (const auto& item:localeSystemFixtureCases) {
        auto bytes=encode(item.source);int result=call(bytes.c_str());
        if (result!=(modified?29:17) || (modified && captured!=item.target)) return 8;
        ++cases;
    }
    if (call("unrecognized")!=17 || !good) return 9;
    if ((modified && (callsW!=9 || callsA!=1)) || (!modified && (callsW || callsA!=10))) return 10;
    printf("SYSTEM_MESSAGES_IAT_%s PASS fields=%u unicode_calls=%d unchanged_calls=%d owner_flags_returns=preserved game_started=false\n",modified?"MODIFIED":"BASELINE",cases,callsW,callsA);
    return 0;
}
