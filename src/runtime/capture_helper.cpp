#include <windows.h>
#include <dbghelp.h>
#include <bcrypt.h>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <vector>
#include <filesystem>
#include <iostream>
#include <cstdio>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;

int fixtureFilter(EXCEPTION_POINTERS*, int(WINAPI*dialog)()) {
    printf("CAPTURE_FIXTURE_READY pid=%lu\n", GetCurrentProcessId());
    fflush(stdout);
    if (dialog) {
        int result = dialog();
        printf("FIXTURE_DIALOG_RESULT value=%d\n", result);
        fflush(stdout);
    } else Sleep(8000);
    return EXCEPTION_EXECUTE_HANDLER;
}

void fixture(int(WINAPI*dialog)() = nullptr) {
    auto heap = static_cast<DWORD*>(HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, 16));
    if (!heap) return;
    heap[0] = 0x54455854; heap[1] = 0x13572468;
    printf("FIXTURE_HEAP address=0x%08lx\n", reinterpret_cast<DWORD>(heap));
    fflush(stdout);
    __try {
        volatile LONG value = *reinterpret_cast<volatile LONG*>(0x78);
        (void)value;
    } __except(fixtureFilter(GetExceptionInformation(), dialog)) {}
    HeapFree(GetProcessHeap(), 0, heap);
}

bool below(const fs::path& path, const fs::path& root) {
    auto p = fs::weakly_canonical(path).wstring(), r = fs::weakly_canonical(root).wstring();
    if (r.back() != L'\\') r += L'\\';
    return p.size() > r.size() && !_wcsnicmp(p.c_str(), r.c_str(), r.size());
}

// Shared-runtime capture is opt-in through the existing exception hook. The
// target must be this owned fixture or the exact supported game beside it.
std::string fileDigest(const fs::path& path) {
    if (!fs::is_regular_file(path) || fs::file_size(path)>16*1024*1024)
        throw std::runtime_error("Unsupported capture input size");
    std::ifstream file(path,std::ios::binary);
    std::vector<unsigned char> raw((std::istreambuf_iterator<char>(file)),{});
    if (!file.eof() && file.fail()) throw std::runtime_error("Capture input read failed");
    BCRYPT_ALG_HANDLE algorithm=nullptr;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)!=0)
        throw std::runtime_error("Capture digest initialization failed");
    struct CloseAlgorithm {BCRYPT_ALG_HANDLE value;~CloseAlgorithm(){BCryptCloseAlgorithmProvider(value,0);}} close{algorithm};
    DWORD objectSize=0,used=0;
    if(BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<BYTE*>(&objectSize),4,&used,0)!=0)
        throw std::runtime_error("Capture digest object failed");
    std::vector<unsigned char> object(objectSize);BCRYPT_HASH_HANDLE hash=nullptr;
    if(BCryptCreateHash(algorithm,&hash,object.data(),objectSize,nullptr,0,0)!=0)
        throw std::runtime_error("Capture digest creation failed");
    struct CloseHash {BCRYPT_HASH_HANDLE value;~CloseHash(){BCryptDestroyHash(value);}} closeHash{hash};
    unsigned char digest[32]{};
    if(BCryptHashData(hash,raw.data(),static_cast<ULONG>(raw.size()),0)!=0
        ||BCryptFinishHash(hash,digest,32,0)!=0)
        throw std::runtime_error("Capture digest failed");
    std::ostringstream result;
    for(unsigned char byte:digest)result<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(byte);
    return result.str();
}

int wmain(int argc, wchar_t** argv) {
    if (argc == 2 && std::wstring(argv[1]) == L"--fixture") { fixture(); return 0; }
    if (argc == 2 && std::wstring(argv[1]) == L"--fixture-hook") {
        wchar_t self[32768]{}; GetModuleFileNameW(nullptr, self, 32768);
        auto folder = fs::path(self).parent_path();
        if (!LoadLibraryW((folder / L"workspace_profile.dll").c_str())) return 2;
        HMODULE core = LoadLibraryA((folder / L"Core.dll").string().c_str());
        auto dialog = core ? reinterpret_cast<int(WINAPI*)()>(GetProcAddress(core, "_ShowFixtureException@0")) : nullptr;
        if (!dialog) return 3;
        fixture(dialog);
        return 0;
    }
    HANDLE process = nullptr, output = INVALID_HANDLE_VALUE;
    try {
        if (argc != 5 || std::wstring(argv[1]) != L"--pid" || std::wstring(argv[3]) != L"--output")
            throw std::runtime_error("Expected --pid PID --output NEW_DUMP");
        size_t used = 0;
        unsigned long pid = std::stoul(argv[2], &used);
        if (used != wcslen(argv[2]) || !pid) throw std::runtime_error("Invalid PID");
        wchar_t self[32768]{};
        if (!GetModuleFileNameW(nullptr, self, 32768)) throw std::runtime_error("Helper path unavailable");
        auto binary = fs::canonical(self);
        auto build = binary.parent_path().parent_path().parent_path();
        const bool buildLayout=!_wcsicmp(build.filename().c_str(),L"build");
        const auto shared=binary.parent_path().parent_path();
        const bool sharedLayout=!_wcsicmp(binary.parent_path().filename().c_str(),L"modules")
            && fs::is_regular_file(shared/L"runtime.json");
        if (!buildLayout && !sharedLayout) throw std::runtime_error("Helper must be in build or a shared runtime");
        fs::path path = fs::absolute(argv[4]);
        const auto outputRoot=sharedLayout?shared/L"cache":build;
        if (!below(path,outputRoot) || fs::exists(path)) throw std::runtime_error("Output must be new and below the capture root");
        process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
        if (!process) throw std::runtime_error("Target process unavailable");
        wchar_t image[32768]{}; DWORD length = 32768;
        if (!QueryFullProcessImageNameW(process, 0, image, &length)) throw std::runtime_error("Target image unavailable");
        fs::path target = fs::canonical(image);
        bool game = !_wcsicmp(target.filename().c_str(), L"MagnaCarta.exe")
            && (sharedLayout? target.parent_path()==fs::canonical(shared/L"data") : below(target,build));
        bool ownFixture = !_wcsicmp(target.c_str(), binary.c_str());
        if (game && sharedLayout) {
            if(fileDigest(target)!="6046b29600b5e009903b3495bd11df0b4d89fc3545adde028193ea9fbff8d4de"
                ||fileDigest(target.parent_path()/L"Core.dll")!="72c91c8102ee268ef491c41b56180babca90760df31a00075f63aed018d62571"
                ||fileDigest(target.parent_path()/L"MCAlpha.dll")!="7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e")
                throw std::runtime_error("Unsupported shared-runtime capture target");
        }
        if (!game && !ownFixture) throw std::runtime_error("Target is not an isolated game or capture fixture");
        fs::create_directories(path.parent_path());
        output = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (output == INVALID_HANDLE_VALUE) throw std::runtime_error("Dump output creation failed");
        auto flags = static_cast<MINIDUMP_TYPE>(MiniDumpWithFullMemory | MiniDumpWithThreadInfo |
                                               MiniDumpWithFullMemoryInfo | MiniDumpWithUnloadedModules);
        if (!MiniDumpWriteDump(process, pid, output, flags, nullptr, nullptr, nullptr))
            throw std::runtime_error("Full-memory snapshot failed");
        CloseHandle(output); output = INVALID_HANDLE_VALUE;
        CloseHandle(process); process = nullptr;
        std::cout << "FULL_CAPTURE_PASS pid=" << pid << " game_started=false target_terminated=false" << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FULL_CAPTURE_FAILED " << e.what() << " win32=" << GetLastError() << std::endl;
        if (output != INVALID_HANDLE_VALUE) CloseHandle(output);
        if (process) CloseHandle(process);
        return 1;
    }
}
