#include "native_font.h"
#include <cstring>
#include <cstdint>
#include <iterator>
#ifdef SCALED_FONT_RUNTIME
#include "scaled_font_runtime.h"
#endif

struct NativeLabel {const char* source;const char* target;};
#ifdef NATIVE_FONT_DATA_HEADER
#include NATIVE_FONT_DATA_HEADER
#else
const unsigned short coveragePairs[]={0};
const unsigned char coveragePlane0[]={0},coveragePlane1[]={0};
const NativeLabel nativeLabels[]={{"",""}};
#endif

unsigned blendNativePixel(unsigned dst,unsigned src,unsigned coverage) {
    if (!coverage) return dst;
    if (coverage>=255) return src;
    // The native buffer stores straight BGRA, including transparent pixels.
    const unsigned a=((src>>24)*coverage+127)/255,da=dst>>24;
    const unsigned remainder=(da*(255-a)+127)/255,oa=a+remainder;
    if (!oa) return 0;
    unsigned result=oa<<24;
    for(unsigned shift=0;shift<24;shift+=8)
        result|=(((((src>>shift)&255)*a+((dst>>shift)&255)*remainder+oa/2)/oa)&255)<<shift;
    return result;
}

bool translateNativeLabel(const char* input,std::string& output) {
    if (!input) return false;
    const size_t length=strnlen_s(input,257);
    if (length>256) return false;
    size_t prefix=0;while(prefix<length && input[prefix]==' ')++prefix;
    for(const auto& label:nativeLabels) {
        size_t n=strlen(label.source);
        if (!n || n>length-prefix || memcmp(input+prefix,label.source,n)) continue;
        const char* suffix=input+prefix+n;
        // Exact location labels, optionally the original save-list time suffix.
        if (*suffix) {
            const char* q=suffix;
            if (*q++!=' ' || *q++!='(') continue;
            unsigned digits=0;while(*q>='0' && *q<='9'){++digits;++q;}
            if (!digits || digits>10 || *q++!=':')continue;
            digits=0;while(*q>='0' && *q<='9'){++digits;++q;}
            if (!digits || digits>10 || *q++!=')' || *q)continue;
        }
        output.assign(input,prefix);output+=label.target;output+=suffix;
        return true;
    }
    return false;
}

bool drawNativeCoverage(void* object,int x,int y,const unsigned char* text,int* advance,unsigned* pixels,int pitch) {
#ifndef NATIVE_FONT_DATA_HEADER
    (void)object;(void)x;(void)y;(void)text;(void)advance;(void)pixels;(void)pitch;
    return false;
#else
    if (!object || !text || text[0]<0xca || !text[1] || !advance || !pixels || pitch<1 || pitch>8192) return false;
    const unsigned pair=(unsigned(text[0])<<8)|text[1];
    size_t low=0,high=std::size(coveragePairs);
    while(low<high){size_t mid=(low+high)/2;if(coveragePairs[mid]<pair)low=mid+1;else high=mid;}
    if(low==std::size(coveragePairs) || coveragePairs[low]!=pair)return false;
    auto base=static_cast<unsigned char*>(object);
    auto font=*reinterpret_cast<unsigned char**>(base+8);
    if(!font)return false;
    const unsigned height=*reinterpret_cast<unsigned short*>(font+0x58);
    if(height!=14 && height!=22)return false;
    // Only a fixed-advance Chi instance is eligible; no family/metric changes.
    if(font[0x2a])return false;
    const unsigned char* coverage=(height==14?coveragePlane0:coveragePlane1)+low*height*height;
    const unsigned color=*reinterpret_cast<unsigned*>(base+0x2c);
    const int origin=*advance;const int total=static_cast<int>(height)*pitch;
    for(unsigned row=0;row<height;++row)for(unsigned col=0;col<height;++col){
        const unsigned a=coverage[row*height+col];if(!a)continue;
        const int ry=static_cast<int>(row)+y;
        const int position=ry*pitch+static_cast<int>(col)+x+origin;
        // Preserve native row/offset clipping, and reject its one-past-end case.
        if(position<0 || position>=total || position<=(ry-1)*pitch+static_cast<int>(height)+origin || position>=(ry+1)*pitch+origin)continue;
        pixels[position]=blendNativePixel(pixels[position],color,a);
    }
    *advance+=height;
    return true;
#endif
}

#ifdef NATIVE_FONT_DATA_HEADER
namespace {
using GlyphFn=int(__thiscall*)(void*,int,int,const unsigned char*,int*,unsigned*,int);
using MeasureFn=int(__thiscall*)(void*,const char*);
using TextFn=int(__thiscall*)(void*,const char*,unsigned*,int);
GlyphFn originalGlyph=nullptr;MeasureFn originalMeasure=nullptr;TextFn originalText=nullptr;
struct Hook {size_t rva;unsigned char expected[32];void* callback;unsigned char* site;void* trampoline;};
int __fastcall glyphHook(void* object,void*,int x,int y,const unsigned char* text,int* advance,unsigned* pixels,int pitch) {
#ifdef SCALED_FONT_RUNTIME
    observeScaledGlyph(object,x,y,text,*advance,pitch,originalGlyph);
#endif
    if(drawNativeCoverage(object,x,y,text,advance,pixels,pitch))return 2;
    return originalGlyph(object,x,y,text,advance,pixels,pitch);
}
int __fastcall measureHook(void* object,void*,const char* text) {
    std::string translated;
    try {if(translateNativeLabel(text,translated))return originalMeasure(object,translated.c_str());} catch (...) {}
    return originalMeasure(object,text);
}
int __fastcall textHook(void* object,void*,const char* text,unsigned* pixels,int pitch) {
#ifdef SCALED_FONT_RUNTIME
    beginScaledText(object,pitch);
#endif
    std::string translated;
    try {if(translateNativeLabel(text,translated))return originalText(object,translated.c_str(),pixels,pitch);} catch (...) {}
    return originalText(object,text,pixels,pitch);
}
// Full 32-byte entry context from the hash-locked module. Six leading bytes
// are complete position-independent instructions: push/mov/sub only.
Hook hooks[]={
    {0x1fb39,{EXPECTED_GLYPH_BYTES},reinterpret_cast<void*>(&glyphHook),nullptr,nullptr},
    {0x1f5ad,{EXPECTED_MEASURE_BYTES},reinterpret_cast<void*>(&measureHook),nullptr,nullptr},
    {0x1f86f,{EXPECTED_TEXT_BYTES},reinterpret_cast<void*>(&textHook),nullptr,nullptr}
};
HMODULE installed=nullptr;
bool writeCode(unsigned char* site,const void* data,size_t length) {
    DWORD before;if(!VirtualProtect(site,length,PAGE_EXECUTE_READWRITE,&before))return false;
    memcpy(site,data,length);bool good=FlushInstructionCache(GetCurrentProcess(),site,length)!=FALSE;
    DWORD ignored;return VirtualProtect(site,length,before,&ignored)!=FALSE && good;
}
void jump(unsigned char* bytes,void* target) {
    bytes[0]=0xe9;*reinterpret_cast<int32_t*>(bytes+1)=static_cast<int32_t>(reinterpret_cast<uintptr_t>(target)-reinterpret_cast<uintptr_t>(bytes+5));
}
}
#endif

bool removeNativeFont() {
#ifdef NATIVE_FONT_DATA_HEADER
    bool good=true;
    for(auto& hook:hooks){
        if(hook.site && !writeCode(hook.site,hook.expected,6)){good=false;continue;}
        hook.site=nullptr;
        if(hook.trampoline){VirtualFree(hook.trampoline,0,MEM_RELEASE);hook.trampoline=nullptr;}
    }
    if(good){installed=nullptr;originalGlyph=nullptr;originalMeasure=nullptr;originalText=nullptr;}
    return good;
#else
    return true;
#endif
}

bool nativeFontImageMatches(unsigned char* base,size_t available) {
#ifdef NATIVE_FONT_DATA_HEADER
    if(!base || available<0x10b000)return false;
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<1 || dos->e_lfanew>4096)return false;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(base+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386 ||
       nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC || nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
    for(auto& hook:hooks)if(memcmp(base+hook.rva,hook.expected,sizeof(hook.expected)))return false;
    return true;
#else
    (void)base;(void)available;return false;
#endif
}

bool installNativeFont(HMODULE module) {
#ifdef NATIVE_FONT_DATA_HEADER
    if(installed)return installed==module;
    auto base=reinterpret_cast<unsigned char*>(module);if(!base)return false;
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<1 || dos->e_lfanew>4096)return false;
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(base+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386 ||
       nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC || nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
#ifndef NATIVE_FONT_TEST
    if(!nativeFontImageMatches(base,0x10b000))return false;
#endif
    for(auto& hook:hooks)if(memcmp(base+hook.rva,hook.expected,
#ifdef NATIVE_FONT_TEST
        6
#else
        sizeof(hook.expected)
#endif
        ))return false;
    // Prepare every original trampoline before changing any entry point.
    for(auto& hook:hooks){
        hook.trampoline=VirtualAlloc(nullptr,16,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        if(!hook.trampoline){for(auto& h:hooks)if(h.trampoline){VirtualFree(h.trampoline,0,MEM_RELEASE);h.trampoline=nullptr;}return false;}
        auto bytes=static_cast<unsigned char*>(hook.trampoline);memcpy(bytes,hook.expected,6);
        jump(bytes+6,base+hook.rva+6);DWORD previous;
        if(!VirtualProtect(bytes,16,PAGE_EXECUTE_READ,&previous) || !FlushInstructionCache(GetCurrentProcess(),bytes,16)){
            for(auto& h:hooks)if(h.trampoline){VirtualFree(h.trampoline,0,MEM_RELEASE);h.trampoline=nullptr;}return false;
        }
    }
    originalGlyph=reinterpret_cast<GlyphFn>(hooks[0].trampoline);
    originalMeasure=reinterpret_cast<MeasureFn>(hooks[1].trampoline);
    originalText=reinterpret_cast<TextFn>(hooks[2].trampoline);
    for(auto& hook:hooks){
        unsigned char bytes[6]={}; // displacement is relative to the target entry.
        bytes[0]=0xe9;*reinterpret_cast<int32_t*>(bytes+1)=static_cast<int32_t>(reinterpret_cast<uintptr_t>(hook.callback)-reinterpret_cast<uintptr_t>(base+hook.rva+5));bytes[5]=0x90;
        hook.site=base+hook.rva;
        if(!writeCode(hook.site,bytes,6)){removeNativeFont();return false;}
    }
    installed=module;return true;
#else
    (void)module;return true;
#endif
}
