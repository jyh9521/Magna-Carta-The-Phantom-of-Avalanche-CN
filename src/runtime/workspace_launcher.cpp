#include <windows.h>
#include <bcrypt.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <vector>
#include <stdexcept>

namespace fs = std::filesystem;
constexpr wchar_t sourceKey[] = L"SOFTWARE\\Softmax\\MagnaCarta";
constexpr wchar_t virtualKey[] = L"Software\\Classes\\VirtualStore\\MACHINE\\SOFTWARE\\WOW6432Node\\SOFTMAX\\MagnaCarta";

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

bool inside(const fs::path& path, const fs::path& root) {
    auto p = fs::weakly_canonical(path).wstring();
    auto r = fs::weakly_canonical(root).wstring();
    if (!_wcsicmp(p.c_str(), r.c_str())) return true;
    if (!r.empty() && r.back() != L'\\') r += L'\\';
    return p.size() >= r.size() && !_wcsnicmp(p.c_str(), r.c_str(), r.size());
}

bool ansiPath(const wchar_t* path) {
    UINT codePage = GetACP();
    BOOL usedDefault = FALSE;
    int result = WideCharToMultiByte(codePage, codePage == CP_UTF8 ? 0 : WC_NO_BEST_FIT_CHARS,
        path, -1, nullptr, 0, nullptr, codePage == CP_UTF8 ? nullptr : &usedDefault);
    return result > 0 && !usedDefault;
}

std::string sha256(const fs::path& path) {
    std::ifstream file(path, std::ios::binary);
    require(file.good(), "Input file missing");
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    require(BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) == 0, "SHA256 initialization failed");
    DWORD objectSize = 0, used = 0;
    BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<BYTE*>(&objectSize), 4, &used, 0);
    std::vector<BYTE> object(objectSize), buffer(1024 * 1024);
    require(BCryptCreateHash(algorithm, &hash, object.data(), objectSize, nullptr, 0, 0) == 0, "SHA256 creation failed");
    while (file.read(reinterpret_cast<char*>(buffer.data()), buffer.size()) || file.gcount())
        BCryptHashData(hash, buffer.data(), static_cast<ULONG>(file.gcount()), 0);
    BYTE digest[32];
    require(BCryptFinishHash(hash, digest, 32, 0) == 0, "SHA256 finish failed");
    BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm, 0);
    std::ostringstream output;
    for (BYTE b : digest) output << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned>(b);
    return output.str();
}

void copyTree(HKEY source, HKEY target) {
    for (DWORD i = 0;; ++i) {
        wchar_t name[512]; DWORD length = 512, bytes = 65536, type;
        std::vector<BYTE> data(bytes);
        LONG result = RegEnumValueW(source, i, name, &length, nullptr, &type, data.data(), &bytes);
        if (result == ERROR_NO_MORE_ITEMS) break;
        require(result == ERROR_SUCCESS, "Registry value enumeration failed");
        require(RegSetValueExW(target, name, 0, type, data.data(), bytes) == ERROR_SUCCESS, "Profile value copy failed");
    }
    for (DWORD i = 0;; ++i) {
        wchar_t name[512]; DWORD length = 512;
        LONG result = RegEnumKeyExW(source, i, name, &length, nullptr, nullptr, nullptr, nullptr);
        if (result == ERROR_NO_MORE_ITEMS) break;
        require(result == ERROR_SUCCESS, "Registry subkey enumeration failed");
        HKEY child = nullptr, output = nullptr;
        require(RegOpenKeyExW(source, name, 0, KEY_READ, &child) == ERROR_SUCCESS, "Source subkey open failed");
        require(RegCreateKeyExW(target, name, 0, nullptr, 0, KEY_ALL_ACCESS, nullptr, &output, nullptr) == ERROR_SUCCESS, "Profile subkey creation failed");
        copyTree(child, output);
        RegCloseKey(output); RegCloseKey(child);
    }
}

struct Session {
    std::wstring path;
    HKEY key = nullptr;
    Session(const fs::path& workspace, const fs::path& setting) {
        path = L"Software\\MagnaCartaWorkspace\\Sessions\\" + std::to_wstring(GetCurrentProcessId()) + L"-" + std::to_wstring(GetTickCount64());
        require(RegCreateKeyExW(HKEY_CURRENT_USER, path.c_str(), 0, nullptr, 0, KEY_ALL_ACCESS,
            nullptr, &key, nullptr) == ERROR_SUCCESS, "Session creation failed");
        try {
            HKEY source = nullptr;
            require(RegOpenKeyExW(HKEY_LOCAL_MACHINE, sourceKey, 0, KEY_READ | KEY_WOW64_32KEY, &source) == ERROR_SUCCESS, "Installed registry baseline missing");
            copyTree(source, key); RegCloseKey(source);
            if (RegOpenKeyExW(HKEY_CURRENT_USER, virtualKey, 0, KEY_READ | KEY_WOW64_64KEY, &source) == ERROR_SUCCESS) {
                copyTree(source, key); RegCloseKey(source);
            }
            auto directory = workspace.wstring();
            require(RegSetValueExW(key, L"Directory", 0, REG_SZ, reinterpret_cast<const BYTE*>(directory.c_str()),
                static_cast<DWORD>((directory.size() + 1) * 2)) == ERROR_SUCCESS, "Directory override failed");
            std::ifstream input(setting, std::ios::binary);
            std::vector<BYTE> data((std::istreambuf_iterator<char>(input)), {});
            require(data.size() == 52 && data[1] <= 1, "Unsupported settings layout");
            require(RegSetValueExW(key, L"MCSetting", 0, REG_BINARY, data.data(), 52) == ERROR_SUCCESS, "Settings override failed");
        } catch (...) { cleanup(); throw; }
    }
    void cleanup() {
        if (key) { RegCloseKey(key); key = nullptr; }
        if (!path.empty()) RegDeleteTreeW(HKEY_CURRENT_USER, path.c_str());
    }
    ~Session() { cleanup(); }
};

struct Process {
    PROCESS_INFORMATION info{};
    HANDLE job = nullptr;
    ~Process() {
        if (job) CloseHandle(job);
        if (info.hThread) CloseHandle(info.hThread);
        if (info.hProcess) CloseHandle(info.hProcess);
    }
};

void inject(Process& child, const fs::path& shim) {
    auto name = shim.wstring(); SIZE_T size = (name.size() + 1) * sizeof(wchar_t);
    void* remote = VirtualAllocEx(child.info.hProcess, nullptr, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    require(remote != nullptr, "Shim allocation failed");
    SIZE_T written = 0;
    require(WriteProcessMemory(child.info.hProcess, remote, name.c_str(), size, &written) && written == size, "Shim path write failed");
    auto loader = reinterpret_cast<LPTHREAD_START_ROUTINE>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW"));
    HANDLE thread = CreateRemoteThread(child.info.hProcess, nullptr, 0, loader, remote, 0, nullptr);
    require(thread != nullptr, "Shim initialization thread failed");
    DWORD result = 0;
    DWORD wait = WaitForSingleObject(thread, 15000);
    if (wait == WAIT_OBJECT_0) GetExitCodeThread(thread, &result);
    CloseHandle(thread);
    if (wait == WAIT_OBJECT_0) VirtualFreeEx(child.info.hProcess, remote, 0, MEM_RELEASE);
    require(wait == WAIT_OBJECT_0 && result != 0, "Shim did not initialize");
}

int wmain(int argc, wchar_t** argv) {
    try {
        if (argc == 3 && std::wstring(argv[1]) == L"--cleanup-session") {
            std::wstring token = argv[2];
            auto split = token.find(L'-');
            require(!token.empty() && token.size() < 64 && split != std::wstring::npos &&
                split > 0 && split + 1 < token.size() && token.find(L'-', split + 1) == std::wstring::npos &&
                token.find_first_not_of(L"0123456789-") == std::wstring::npos, "Invalid session token");
            DWORD pid = std::stoul(token.substr(0, split));
            HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
            if (process) {
                DWORD status = 0; GetExitCodeProcess(process, &status); CloseHandle(process);
                require(status != STILL_ACTIVE, "Session owner is still running");
            }
            auto path = L"Software\\MagnaCartaWorkspace\\Sessions\\" + token;
            LONG result = RegDeleteTreeW(HKEY_CURRENT_USER, path.c_str());
            require(result == ERROR_SUCCESS || result == ERROR_FILE_NOT_FOUND, "Session cleanup failed");
            std::cout << "PROFILE_SESSION_REMOVED" << std::endl;
            return 0;
        }
        fs::path workspace, shim, setting, log;
        bool fixture = false, captureException = false, textureLifetime = false, focusGuard = false; DWORD seconds = 0;
        for (int i = 1; i < argc; ++i) {
            std::wstring arg = argv[i];
            if (arg == L"--fixture") fixture = true;
            else if (arg == L"--capture-exception") captureException = true;
            else if (arg == L"--texture-lifetime") textureLifetime = true;
            else if (arg == L"--focus-guard") focusGuard = true;
            else if (i + 1 < argc && arg == L"--workspace") workspace = fs::canonical(argv[++i]);
            else if (i + 1 < argc && arg == L"--shim") shim = fs::canonical(argv[++i]);
            else if (i + 1 < argc && arg == L"--profile") setting = fs::canonical(argv[++i]);
            else if (i + 1 < argc && arg == L"--log") log = fs::absolute(argv[++i]);
            else if (i + 1 < argc && arg == L"--timeout") seconds = std::stoul(argv[++i]);
            else throw std::runtime_error("Unknown or incomplete argument");
        }
        require(!workspace.empty() && !shim.empty() && !setting.empty() && !log.empty(), "Missing launch arguments");
        require(seconds <= 86400, "Timeout is out of range");
        require(!fs::exists(log), "Log path already exists");
        fs::path exe = workspace / (fixture ? L"registry_probe.exe" : L"MagnaCarta.exe");
        if (!fixture) {
            require(sha256(exe) == "be2ae107373835defc6ec33643eaf435dcc5c882ea0b6e3c47032cd013690651", "Unsupported game executable");
            require(sha256(workspace / L"MCAlpha.dll") == "79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f", "Unsupported engine module");
        }
        HKEY installed = nullptr;
        require(RegOpenKeyExW(HKEY_LOCAL_MACHINE, sourceKey, 0, KEY_READ | KEY_WOW64_32KEY, &installed) == ERROR_SUCCESS, "Installed baseline missing");
        wchar_t original[32768]{}; DWORD bytes = sizeof(original), type;
        LONG result = RegQueryValueExW(installed, L"Directory", nullptr, &type, reinterpret_cast<BYTE*>(original), &bytes);
        RegCloseKey(installed);
        require(result == ERROR_SUCCESS && type == REG_SZ, "Installed directory unavailable");
        require(!inside(workspace, original) && !inside(original, workspace), "Original install must not be used as workspace");
        require(!inside(log, original), "Log must not be written inside the original installation");
        require(ansiPath(workspace.c_str()),
            "Workspace path is not supported by the active ANSI code page");
        fs::create_directories(log.parent_path());
        fs::path captureHelper = shim.parent_path() / L"capture_helper.exe";
        if (focusGuard) {
            require(!fixture && !textureLifetime, "Focus guard requires an isolated unpatched borderless trial");
            require(sha256(workspace / L"Drv" / L"AsrD3DDrv.dll") == "00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29", "Unsupported focus driver");
            require(sha256(workspace / L"ddraw.dll") == "f75f0ac48d2782f225c483dc2f1142303a513e8dd8a60793891ade89f64755ea", "Unsupported focus graphics layer");
            require(sha256(workspace / L"DDrawCompat-MagnaCarta.ini") == "45f7df1d1c09bc3fea707d9da3dead33a6b21f48224639b7219656a572b3fa3a", "Unsupported focus graphics configuration");
        }
        if (textureLifetime) {
            require(!fixture, "Texture lifetime is not a registry fixture option");
            require(sha256(workspace / L"Drv" / L"AsrD3DDrv.dll") == "27db21dee7dde8ca3463e11fab57cc0b7cf6a7ed3338c950b6b1181eed7959ed", "Unsupported graphics driver");
        }
        if (captureException) {
            require(!fixture, "Exception capture is not a registry fixture option");
            require(sha256(workspace / L"Core.dll") == "72c91c8102ee268ef491c41b56180babca90760df31a00075f63aed018d62571", "Unsupported exception module");
            require(fs::is_regular_file(captureHelper), "Capture helper missing");
        }
        Session session(workspace, setting);
        SetEnvironmentVariableW(L"MC_WORKSPACE_SESSION", session.path.c_str());
        SetEnvironmentVariableW(L"MC_WORKSPACE_LOG", log.c_str());
        SetEnvironmentVariableW(L"MC_CAPTURE_HELPER", captureException ? captureHelper.c_str() : nullptr);
        SetEnvironmentVariableW(L"MC_TEXTURE_LIFETIME", textureLifetime ? L"1" : nullptr);
        SetEnvironmentVariableW(L"MC_FOCUS_GUARD", focusGuard ? L"1" : nullptr);
        auto textureDriver = (workspace / L"Drv" / L"AsrD3DDrv.dll").wstring();
        SetEnvironmentVariableW(L"MC_TEXTURE_DRIVER", textureLifetime ? textureDriver.c_str() : nullptr);
        if (captureException) std::cout << "EXCEPTION_CAPTURE_ENABLED" << std::endl;
        if (fixture) SetEnvironmentVariableW(L"MC_PROBE_EXPECT_DIRECTORY", workspace.c_str());
        std::wstring command = L"\"" + exe.wstring() + L"\"" + (fixture ? L" --write-session" : L"");
        STARTUPINFOW start{}; start.cb = sizeof(start);
        if (!fixture) { start.dwFlags = STARTF_USESHOWWINDOW; start.wShowWindow = SW_SHOWNORMAL; }
        Process child;
        child.job = CreateJobObjectW(nullptr, nullptr);
        require(child.job != nullptr, "Process job creation failed");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        require(SetInformationJobObject(child.job, JobObjectExtendedLimitInformation, &limits, sizeof(limits)), "Process job configuration failed");
        require(CreateProcessW(exe.c_str(), command.data(), nullptr, nullptr, TRUE, CREATE_SUSPENDED,
            nullptr, workspace.c_str(), &start, &child.info), "Child process creation failed");
        if (!AssignProcessToJobObject(child.job, child.info.hProcess)) {
            TerminateProcess(child.info.hProcess, 125);
            throw std::runtime_error("Child process job assignment failed");
        }
        inject(child, shim);
        std::ifstream trace(log);
        std::string content((std::istreambuf_iterator<char>(trace)), {});
        require(content.find("IAT_READY") != std::string::npos, "Required import redirection was not installed");
        require(ResumeThread(child.info.hThread) != static_cast<DWORD>(-1), "Child resume failed");
        std::cout << "ISOLATED_PROCESS_STARTED pid=" << child.info.dwProcessId << std::endl;
        DWORD wait = WaitForSingleObject(child.info.hProcess, seconds ? seconds * 1000 : INFINITE);
        if (wait == WAIT_TIMEOUT) {
            TerminateProcess(child.info.hProcess, 124);
            WaitForSingleObject(child.info.hProcess, 5000);
        }
        DWORD code = 125; GetExitCodeProcess(child.info.hProcess, &code);
        std::cout << "ISOLATED_PROCESS_ENDED exit=" << code << std::endl;
        return static_cast<int>(code);
    } catch (const std::exception& error) {
        std::cerr << "LAUNCH_FAILED " << error.what() << " win32=" << GetLastError() << std::endl;
        return 125;
    }
}
