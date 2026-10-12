#include "native_text_step.h"
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>

void check(bool value) { if (!value) throw std::runtime_error("native text step fixture failed"); }
int main() {
    BYTE* image = nullptr;
    try {
        constexpr size_t size = 0x10b000;
        image = static_cast<BYTE*>(VirtualAlloc(nullptr,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
        check(image != nullptr);
        initializeTextStepFixture(image,size);
        std::vector<BYTE> original(image,image+size);
        check(!setNativeTextStep(image,size-1,true));
        for (unsigned lead=0;lead<256;++lead) {
            check(nativeTextStepModel(lead,false)==(lead>=0xa4 && lead<0xca ? 2u : 1u));
            check(nativeTextStepModel(lead,true)==(lead>=0xa4 ? 2u : 1u));
        }
        check(nativeTextStepModel(256,true)==0);
        check(setNativeTextStep(image,size,true));
        check(setNativeTextStep(image,size,true));
        unsigned changes=0;
        for (size_t i=0;i<size;++i) if (image[i]!=original[i]) { ++changes; check(i==0x1f000 && image[i]==0); }
        check(changes==1);
        check(setNativeTextStep(image,size,false));
        check(!memcmp(image,original.data(),size));
        // Tampered context, unsupported architecture and unexpected immediate all fail closed.
        image[0x1efcd]^=1; check(!setNativeTextStep(image,size,true)); image[0x1efcd]^=1;
        image[0x1f000]=0x01; check(!setNativeTextStep(image,size,true)); image[0x1f000]=0xca;
        auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);
        nt->FileHeader.Machine=IMAGE_FILE_MACHINE_AMD64; check(!setNativeTextStep(image,size,true));
        nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;
        check(!memcmp(image,original.data(),size));
        VirtualFree(image,0,MEM_RELEASE);
        std::cout << "NATIVE_TEXT_STEP_FIXTURE PASS leads=256 changed_bytes=1 rollback=exact mismatch_rejected=true commercial_code_executed=false game_started=false" << std::endl;
        return 0;
    } catch (const std::exception& error) {
        if (image) VirtualFree(image,0,MEM_RELEASE);
        std::cerr << error.what() << std::endl; return 1;
    }
}
