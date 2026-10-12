#include "texture_lifetime.h"
#include <d3d.h>
#include <array>
#include <cstring>

namespace {
using BindFn = DWORD(__thiscall*)(void*, DWORD, DWORD);
using DeleteFn = DWORD(__thiscall*)(void*, int, const DWORD*);
BindFn originalBind = nullptr;
DeleteFn originalDelete = nullptr;
void(*logMessage)(const wchar_t*) = nullptr;
SRWLOCK stateLock = SRWLOCK_INIT;
struct State {
    void* object = nullptr;
    void* device = nullptr;
    std::array<DWORD, 8> bound;
    State() { bound.fill(0xffffffff); }
};
State states[32];

State* findState(void* object) {
    auto device = *reinterpret_cast<void**>(static_cast<BYTE*>(object) + 0x2c);
    for (auto& state : states) if (state.object == object) {
        if (state.device != device) { state.device = device; state.bound.fill(0xffffffff); }
        return &state;
    }
    for (auto& state : states) if (!state.object) { state.object = object; state.device = device; return &state; }
    return nullptr;
}

DWORD __fastcall bindHook(void* object, void*, DWORD target, DWORD id) {
    DWORD result = originalBind(object, target, id);
    if (target == 0xde0 || target == 0xde1) {
        DWORD stage = *reinterpret_cast<DWORD*>(static_cast<BYTE*>(object) + 0x108ef0);
        if (stage < 8) {
            AcquireSRWLockExclusive(&stateLock);
            if (State* state = findState(object)) state->bound[stage] = id;
            ReleaseSRWLockExclusive(&stateLock);
        }
    }
    return result;
}

DWORD __fastcall deleteHook(void* object, void*, int count, const DWORD* ids) {
    if (ids && count > 0 && count <= 4096) {
        std::array<DWORD, 8> bound;
        bound.fill(0xffffffff);
        AcquireSRWLockExclusive(&stateLock);
        if (State* state = findState(object)) bound = state->bound;
        ReleaseSRWLockExclusive(&stateLock);
        auto device = *reinterpret_cast<IDirect3DDevice7**>(static_cast<BYTE*>(object) + 0x2c);
        for (DWORD stage = 0; device && stage < 8; ++stage) {
            bool deletingBound = false;
            for (int i = 0; i < count; ++i)
                if (ids[i] < 4096 && bound[stage] == ids[i]) deletingBound = true;
            if (!deletingBound) continue;
            HRESULT result = device->SetTexture(stage, nullptr);
            if (SUCCEEDED(result)) {
                AcquireSRWLockExclusive(&stateLock);
                if (State* state = findState(object)) state->bound[stage] = 0xffffffff;
                ReleaseSRWLockExclusive(&stateLock);
                if (logMessage) logMessage(L"TEXTURE_LIFETIME_UNBOUND_BEFORE_DELETE");
            } else if (logMessage) logMessage(L"TEXTURE_LIFETIME_UNBIND_FAILED");
        }
    }
    return originalDelete(object, count, ids);
}
}

bool installTextureLifetime(HMODULE module, void(*logger)(const wchar_t*)) {
    auto base = reinterpret_cast<BYTE*>(module);
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 || dos->e_lfanew > 4096) return false;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
        nt->OptionalHeader.SizeOfImage != 0x2c000) return false;
    auto table = reinterpret_cast<DWORD*>(base + 0x1a5a8);
    if (table[0x2c / 4] == reinterpret_cast<DWORD>(&bindHook) &&
        table[0x104 / 4] == reinterpret_cast<DWORD>(&deleteHook)) return true;
    const BYTE bindBytes[] = {0x55,0x8b,0xec,0x83,0xec,0x08};
    const BYTE deleteBytes[] = {0x55,0x8b,0xec,0x83,0xec,0x08};
    if (table[0x2c / 4] != reinterpret_cast<DWORD>(base + 0x7b2f) ||
        table[0x104 / 4] != reinterpret_cast<DWORD>(base + 0x5390) ||
        memcmp(base + 0x7b2f, bindBytes, sizeof(bindBytes)) ||
        memcmp(base + 0x5390, deleteBytes, sizeof(deleteBytes))) return false;
    DWORD oldProtection;
    if (!VirtualProtect(table, 0x108, PAGE_READWRITE, &oldProtection)) return false;
    originalBind = reinterpret_cast<BindFn>(base + 0x7b2f);
    originalDelete = reinterpret_cast<DeleteFn>(base + 0x5390);
    logMessage = logger;
    InterlockedExchange(reinterpret_cast<LONG*>(table + 0x2c / 4), reinterpret_cast<LONG>(&bindHook));
    InterlockedExchange(reinterpret_cast<LONG*>(table + 0x104 / 4), reinterpret_cast<LONG>(&deleteHook));
    DWORD ignored;
    if (!VirtualProtect(table, 0x108, oldProtection, &ignored)) {
        InterlockedExchange(reinterpret_cast<LONG*>(table + 0x2c / 4), reinterpret_cast<LONG>(originalBind));
        InterlockedExchange(reinterpret_cast<LONG*>(table + 0x104 / 4), reinterpret_cast<LONG>(originalDelete));
        VirtualProtect(table, 0x108, oldProtection, &ignored);
        return false;
    }
    return true;
}

#ifdef TEXTURE_LIFETIME_TEST
void configureTextureFixture(TextureBindFn bind, TextureDeleteFn erase) {
    originalBind = bind; originalDelete = erase;
    for (auto& state : states) { state.object = nullptr; state.bound.fill(0xffffffff); }
}
DWORD __fastcall fixtureBind(void* object, void* unused, DWORD target, DWORD id) { return bindHook(object, unused, target, id); }
DWORD __fastcall fixtureDelete(void* object, void* unused, int count, const DWORD* ids) { return deleteHook(object, unused, count, ids); }
#endif
