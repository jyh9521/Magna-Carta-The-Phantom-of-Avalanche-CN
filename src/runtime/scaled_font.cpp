#include "scaled_font.h"
#include "native_font.h"
#include <algorithm>
#include <fstream>
#include <limits>
#include <cstring>

namespace {
unsigned integer(const unsigned char* p) {
    return unsigned(p[0]) | unsigned(p[1])<<8 | unsigned(p[2])<<16 | unsigned(p[3])<<24;
}
}

bool ScaledGlyphCache::load(const char* path, std::string& error) {
    *this=ScaledGlyphCache{};error.clear();
    std::ifstream input(path,std::ios::binary|std::ios::ate);
    if(!input){error="missing cache";return false;}
    const auto length=input.tellg();
    if(length<20 || length>64*1024*1024){error="cache length";return false;}
    input.seekg(0);unsigned char header[20]{};
    if(!input.read(reinterpret_cast<char*>(header),20)){error="truncated header";return false;}
    const unsigned h=integer(header+8),s=integer(header+12),n=integer(header+16);
    if(memcmp(header,"SGC1",4)||integer(header+4)!=1||(h!=14&&h!=22)||s<1||s>4||!n||n>4096){error="unsupported cache contract";return false;}
    const uint64_t edge=uint64_t(h)*s,bytes=uint64_t(n)*edge*edge;
    if(uint64_t(length)!=20+2*uint64_t(n)+bytes){error="cache dimensions";return false;}
    ScaledGlyphCache next;next.logicalHeight=h;next.rasterScale=s;next.pairs.reserve(n);
    for(unsigned i=0;i<n;++i){unsigned char b[2]{};input.read(reinterpret_cast<char*>(b),2);unsigned short p=static_cast<unsigned short>(b[0]|unsigned(b[1])<<8);
        if(!p||(!next.pairs.empty()&&next.pairs.back()>=p)){error="unsorted or duplicate pair";return false;}next.pairs.push_back(p);}
    next.coverage.resize(static_cast<size_t>(bytes));
    if(!input.read(reinterpret_cast<char*>(next.coverage.data()),static_cast<std::streamsize>(bytes))){error="truncated coverage";return false;}
    *this=std::move(next);return true;
}

bool ScaledGlyphCache::draw(unsigned short pair,int x,int y,int& advance,unsigned color,
                            unsigned* pixels,size_t count,int pitch) const {
    if(!logicalHeight||!rasterScale||!pixels||pitch<1||pitch>32768||pitch%rasterScale||
       count!=size_t(logicalHeight)*rasterScale*pitch||advance>std::numeric_limits<int>::max()-int(logicalHeight))return false;
    auto it=std::lower_bound(pairs.begin(),pairs.end(),pair);if(it==pairs.end()||*it!=pair)return false;
    const unsigned edge=logicalHeight*rasterScale;const auto* mask=coverage.data()+(it-pairs.begin())*edge*edge;
    const int64_t uiPitch=pitch/rasterScale,origin=advance,total=int64_t(logicalHeight)*uiPitch;
    for(unsigned row=0;row<edge;++row)for(unsigned col=0;col<edge;++col){
        const unsigned a=mask[row*edge+col];if(!a)continue;
        const int64_t ry=int64_t(row/rasterScale)+y;
        const int64_t position=ry*uiPitch+col/rasterScale+int64_t(x)+origin;
        // Project the exact original logical clipping mask, not newly fitted glyph bounds.
        if(position<0||position>=total||position<=(ry-1)*uiPitch+logicalHeight+origin||position>=(ry+1)*uiPitch+origin)continue;
        const int64_t py=int64_t(y)*rasterScale+row,px=(int64_t(x)+origin)*rasterScale+col;
        if(py<0||py>=edge||px<0||px>=pitch)continue;
        const size_t index=static_cast<size_t>(py*pitch+px);
        pixels[index]=blendNativePixel(pixels[index],color,a);
    }
    advance+=logicalHeight;return true;
}
