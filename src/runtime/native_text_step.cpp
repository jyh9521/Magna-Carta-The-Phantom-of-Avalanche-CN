#include "native_text_step.h"
#include <cstring>

namespace {
constexpr DWORD imageSize = 0x10b000;
constexpr size_t functionRva = 0x1efcd;
constexpr size_t patchRva = 0x1f000;
constexpr BYTE expected[] = {
    0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc,0x8b,0x45,0x08,0x0f,0xbe,
    0x08,0x83,0xf9,0xb0,0x7d,0x19,0x8b,0x55,0x08,0x0f,0xbe,0x02,
    0x83,0xf8,0xa4,0x7d,0x07,0xb8,0x01,0x00,0x00,0x00,0xeb,0x1e,
    0xb8,0x02,0x00,0x00,0x00,0xeb,0x17,0x8b,0x4d,0x08,0x0f,0xbe,
    0x11,0x83,0xfa,0xca,0x7d,0x07,0xb8,0x02,0x00,0x00,0x00,0xeb,
    0x05,0xb8,0x01,0x00,0x00,0x00,0x8b,0xe5,0x5d,0xc2,0x04,0x00
};
static_assert(patchRva-functionRva == 51);
bool validImage(BYTE* image, size_t available) {
    if (!image || available < imageSize) return false;
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(image);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 || dos->e_lfanew > 4096) return false;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(image + dos->e_lfanew);
    return nt->Signature == IMAGE_NT_SIGNATURE && nt->FileHeader.Machine == IMAGE_FILE_MACHINE_I386 &&
        nt->OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC && nt->OptionalHeader.SizeOfImage == imageSize;
}
}

unsigned nativeTextStepModel(unsigned lead, bool enabled) {
    if (lead > 255) return 0;
    int value = lead < 128 ? static_cast<int>(lead) : static_cast<int>(lead)-256;
    if (value < -80) return value < -92 ? 1 : 2;
    return value < (enabled ? 0 : -54) ? 2 : 1;
}

bool setNativeTextStep(BYTE* image, size_t available, bool enabled) {
    if (!validImage(image, available)) return false;
    const BYTE current = image[patchRva];
    if (current != 0xca && current != 0x00) return false;
    for (size_t i = 0; i < sizeof(expected); ++i)
        if (i != patchRva-functionRva && image[functionRva+i] != expected[i]) return false;
    const BYTE desired = enabled ? 0x00 : 0xca;
    if (current == desired) return true;
    DWORD previous;
    if (!VirtualProtect(image+patchRva, 1, PAGE_EXECUTE_READWRITE, &previous)) return false;
    image[patchRva] = desired;
    bool flushed = FlushInstructionCache(GetCurrentProcess(), image+patchRva, 1) != FALSE;
    if (!flushed) image[patchRva] = current;
    DWORD ignored;
    if (!VirtualProtect(image+patchRva, 1, previous, &ignored)) {
        image[patchRva] = current;
        FlushInstructionCache(GetCurrentProcess(), image+patchRva, 1);
        VirtualProtect(image+patchRva, 1, previous, &ignored);
        return false;
    }
    return flushed;
}

bool installNativeTextStep(HMODULE module) {
    // Full on-disk SHA-256 is checked by workspace_launcher before process creation.
    return setNativeTextStep(reinterpret_cast<BYTE*>(module), imageSize, true);
}

#ifdef NATIVE_TEXT_STEP_TEST
void initializeTextStepFixture(BYTE* image, size_t available) {
    if (!image || available < imageSize) return;
    memset(image, 0, available);
    auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(image);
    dos->e_magic = IMAGE_DOS_SIGNATURE; dos->e_lfanew = 0x100;
    auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);
    nt->Signature = IMAGE_NT_SIGNATURE; nt->FileHeader.Machine = IMAGE_FILE_MACHINE_I386;
    nt->OptionalHeader.Magic = IMAGE_NT_OPTIONAL_HDR32_MAGIC; nt->OptionalHeader.SizeOfImage = imageSize;
    memcpy(image+functionRva, expected, sizeof(expected));
}
#endif
