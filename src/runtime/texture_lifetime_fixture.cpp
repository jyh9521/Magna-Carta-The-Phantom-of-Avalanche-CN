#include "texture_lifetime.h"
#include <vector>
#include <cassert>
#include <iostream>
#include <d3d.h>

DWORD stageBound[8];
unsigned unbinds = 0, deletions = 0;
bool releaseWhileBound = false;
HRESULT WINAPI setTexture(void*, DWORD stage, void* surface) {
    if (stage >= 8 || surface) return E_INVALIDARG;
    stageBound[stage] = 0xffffffff; ++unbinds;
    return D3D_OK;
}
DWORD __fastcall mockBind(void* object, void*, DWORD, DWORD id) {
    DWORD stage = *reinterpret_cast<DWORD*>(static_cast<BYTE*>(object) + 0x108ef0);
    stageBound[stage] = id;
    return 0x12345678;
}
DWORD __fastcall mockDelete(void*, void*, int count, const DWORD* ids) {
    ++deletions;
    for (int i = 0; i < count; ++i)
        for (DWORD bound : stageBound) if (bound == ids[i]) releaseWhileBound = true;
    return 0x87654321;
}
void require(bool condition) { if (!condition) { std::cerr << "LIFETIME_FIXTURE_FAIL" << std::endl; ExitProcess(1); } }

int main() {
    std::vector<BYTE> object(0x123000);
    void* vtable[36]{}; vtable[35] = reinterpret_cast<void*>(&setTexture);
    void** deviceTable = vtable;
    *reinterpret_cast<void**>(object.data() + 0x2c) = &deviceTable;
    auto stage = reinterpret_cast<DWORD*>(object.data() + 0x108ef0);
    *stage = 0;
    for (auto& value : stageBound) value = 0xffffffff;
    DWORD baselineId = 6;
    mockBind(object.data(), nullptr, 0xde1, baselineId);
    mockDelete(object.data(), nullptr, 1, &baselineId);
    require(releaseWhileBound && unbinds == 0);
    std::cout << "TEXTURE_LIFETIME_BASELINE_REPRODUCED release_while_bound=true" << std::endl;
    releaseWhileBound = false; deletions = 0;
    for (auto& value : stageBound) value = 0xffffffff;
    configureTextureFixture(reinterpret_cast<TextureBindFn>(&mockBind), reinterpret_cast<TextureDeleteFn>(&mockDelete));
    DWORD id = 6;
    *stage = 0;
    require(fixtureBind(object.data(), nullptr, 0xde1, id) == 0x12345678);
    require(fixtureDelete(object.data(), nullptr, 1, &id) == 0x87654321);
    require(!releaseWhileBound && unbinds == 1 && deletions == 1);
    fixtureBind(object.data(), nullptr, 0xde1, 7);
    DWORD other = 8;
    fixtureDelete(object.data(), nullptr, 1, &other);
    require(stageBound[0] == 7 && unbinds == 1);
    *stage = 1; fixtureBind(object.data(), nullptr, 0xde1, 9);
    DWORD both[] = {7, 9};
    fixtureDelete(object.data(), nullptr, 2, both);
    require(!releaseWhileBound && unbinds == 3 && deletions == 3);
    auto memory = static_cast<BYTE*>(VirtualAlloc(nullptr, 0x2c000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    require(memory != nullptr);
    require(!installTextureLifetime(reinterpret_cast<HMODULE>(memory), nullptr));
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(memory);
    dos->e_magic = IMAGE_DOS_SIGNATURE; dos->e_lfanew = 0x100;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(memory + 0x100);
    nt->Signature = IMAGE_NT_SIGNATURE;
    nt->OptionalHeader.Magic = IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    nt->OptionalHeader.SizeOfImage = 0x2c000;
    auto table = reinterpret_cast<DWORD*>(memory + 0x1a5a8);
    DWORD bindAddress = reinterpret_cast<DWORD>(memory + 0x7b2f);
    DWORD deleteAddress = reinterpret_cast<DWORD>(memory + 0x5390);
    table[0x2c / 4] = bindAddress; table[0x104 / 4] = deleteAddress;
    const BYTE bytes[] = {0x55,0x8b,0xec,0x83,0xec,0x08};
    memcpy(memory + 0x7b2f, bytes, 6);
    require(!installTextureLifetime(reinterpret_cast<HMODULE>(memory), nullptr));
    memcpy(memory + 0x5390, bytes, 6);
    DWORD previous;
    require(VirtualProtect(table, 0x108, PAGE_READONLY, &previous));
    require(installTextureLifetime(reinterpret_cast<HMODULE>(memory), nullptr));
    require(table[0x2c / 4] != bindAddress && table[0x104 / 4] != deleteAddress);
    require(installTextureLifetime(reinterpret_cast<HMODULE>(memory), nullptr));
    MEMORY_BASIC_INFORMATION info{};
    require(VirtualQuery(table, &info, sizeof(info)) != 0 && info.Protect == PAGE_READONLY);
    require(VirtualProtect(table, 0x108, PAGE_READWRITE, &previous));
    table[0x2c / 4] = bindAddress; table[0x104 / 4] = deleteAddress;
    DWORD ignored;
    require(VirtualProtect(table, 0x108, previous, &ignored));
    require(table[0x2c / 4] == bindAddress && table[0x104 / 4] == deleteAddress);
    VirtualFree(memory, 0, MEM_RELEASE);
    std::cout << "TEXTURE_LIFETIME_FIXTURE_PASS unbind_before_release=true unrelated_binding_preserved=true stages=2 original_returns_preserved=true invalid_image_rejected=true install_idempotent=true page_protection_restored=true isolated_rollback=true game_started=false" << std::endl;
}
