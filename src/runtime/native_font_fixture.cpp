#include "native_font.h"
#include <cstdio>
#include <cstring>
#include <vector>
#include <iterator>
struct NativeLabel {const char* source;const char* target;};
#include NATIVE_FONT_DATA_HEADER
static int failures=0;
#define CHECK(v) do {if(!(v)){std::printf("FAILED line=%d\n",__LINE__);++failures;}}while(0)

int main(){
    CHECK(blendNativePixel(0,0xffffffff,0)==0);
    CHECK(blendNativePixel(0,0xffffffff,128)==0x80ffffff);
    CHECK(blendNativePixel(0xff000000,0xffffffff,128)==0xff808080);
    CHECK(blendNativePixel(0x12345678,0xffffffff,255)==0xffffffff);
    std::string translated;
    for(const auto& label:nativeLabels){
        std::string saved="       ";saved+=label.source;saved+=" (0:3)";
        auto original=saved;CHECK(translateNativeLabel(saved.c_str(),translated));
        CHECK(translated==std::string("       ")+label.target+" (0:3)");CHECK(saved==original);
        CHECK(!translateNativeLabel((saved+"junk").c_str(),translated));
        CHECK(!translateNativeLabel((std::string(label.source)+"suffix").c_str(),translated));
    }
    CHECK(!translateNativeLabel("unknown (0:3)",translated));
    auto image=static_cast<unsigned char*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
    CHECK(image!=nullptr);if(!image)return 1;
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=128;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+128);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
    const unsigned char prologues[][6]={{0x55,0x8b,0xec,0x83,0xec,0x34},{0x55,0x8b,0xec,0x83,0xec,0x20},{0x55,0x8b,0xec,0x83,0xec,0x20}};
    const size_t rvas[]={0x1fb39,0x1f5ad,0x1f86f};const unsigned char pops[]={24,4,12};
    const unsigned char contexts[][32]={{EXPECTED_GLYPH_BYTES},{EXPECTED_MEASURE_BYTES},{EXPECTED_TEXT_BYTES}};
    for(int i=0;i<3;++i)memcpy(image+rvas[i],contexts[i],32);
    CHECK(nativeFontImageMatches(image,0x10b000));CHECK(!nativeFontImageMatches(image,0x10b000-1));
    image[0x1f86f+20]^=1;CHECK(!nativeFontImageMatches(image,0x10b000));image[0x1f86f+20]^=1;
    for(int i=0;i<3;++i){
        // Entire executable fixture is owned stub code, not copied game bodies.
        memcpy(image+rvas[i],prologues[i],6);
        const unsigned char stub[]={0xb8,77,0,0,0,0xc9,0xc2,pops[i],0};memcpy(image+rvas[i]+6,stub,sizeof(stub));
    }
    CHECK(!installNativeFont(nullptr));image[0x1fb39]=0;CHECK(!installNativeFont(reinterpret_cast<HMODULE>(image)));image[0x1fb39]=0x55;
    CHECK(installNativeFont(reinterpret_cast<HMODULE>(image)));CHECK(installNativeFont(reinterpret_cast<HMODULE>(image)));
    unsigned char object[64]={},font[108]={};*reinterpret_cast<unsigned char**>(object+8)=font;*reinterpret_cast<unsigned short*>(font+0x58)=14;
    *reinterpret_cast<unsigned*>(object+0x2c)=0xffffffff;
    std::vector<unsigned> guarded(14*128+2,0x12345678);std::fill(guarded.begin()+1,guarded.end()-1,0);
    const unsigned char text[]={static_cast<unsigned char>(coveragePairs[0]>>8),static_cast<unsigned char>(coveragePairs[0]),0};int advance=0;
    using Glyph=int(__thiscall*)(void*,int,int,const unsigned char*,int*,unsigned*,int);
    CHECK(reinterpret_cast<Glyph>(image+0x1fb39)(object,0,1,text,&advance,guarded.data()+1,128)==2);CHECK(advance==14);
    bool partial=false;for(size_t i=1;i<guarded.size()-1;++i)if((guarded[i]>>24)>0 && (guarded[i]>>24)<255)partial=true;
    CHECK(partial);CHECK(guarded.front()==0x12345678 && guarded.back()==0x12345678);
    unsigned char ascii[]="A";CHECK(reinterpret_cast<Glyph>(image+0x1fb39)(object,0,1,ascii,&advance,guarded.data()+1,128)==77);
    for(int height:{14,22}){*reinterpret_cast<unsigned short*>(font+0x58)=static_cast<unsigned short>(height);
        for(int origin:{-20,0,127,256})for(int y:{-2,0,1,2,30}){std::vector<unsigned> buffer(height*128+2,0);buffer.front()=buffer.back()=0xfedcba98;int a=origin;
            CHECK(drawNativeCoverage(object,-1,y,text,&a,buffer.data()+1,128));CHECK(a==origin+height);CHECK(buffer.front()==0xfedcba98 && buffer.back()==0xfedcba98);}}
    CHECK(removeNativeFont());for(int i=0;i<3;++i)CHECK(!memcmp(image+rvas[i],prologues[i],6));
    CHECK(reinterpret_cast<Glyph>(image+0x1fb39)(object,0,1,text,&advance,guarded.data()+1,128)==77);
    VirtualFree(image,0,MEM_RELEASE);
    if(failures)return 1;
    std::printf("NATIVE_FONT_FIXTURE PASS grayscale=true metrics=unchanged labels=%zu save_bytes=unchanged clipping=guarded contexts=32x3 rollback=exact commercial_code_executed=false game_started=false\n",std::size(nativeLabels));return 0;
}
