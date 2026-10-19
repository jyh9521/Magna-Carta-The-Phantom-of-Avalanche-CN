#include "scaled_font.h"
#include "native_font.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <vector>
#include <limits>

namespace {
void require(bool v,const char* m){if(!v){std::printf("FAIL %s\n",m);std::exit(5);}}
void bitmap(const char* path,const std::vector<unsigned>& pixels,int w,int h){
    BITMAPFILEHEADER f{};BITMAPINFOHEADER i{};f.bfType=0x4d42;f.bfOffBits=sizeof(f)+sizeof(i);f.bfSize=f.bfOffBits+w*h*4;
    i.biSize=sizeof(i);i.biWidth=w;i.biHeight=-h;i.biPlanes=1;i.biBitCount=32;i.biCompression=BI_RGB;
    std::ofstream out(path,std::ios::binary);out.write(reinterpret_cast<char*>(&f),sizeof(f));out.write(reinterpret_cast<char*>(&i),sizeof(i));out.write(reinterpret_cast<const char*>(pixels.data()),pixels.size()*4);require(bool(out),"bitmap write");
}
}
int main(int argc,char** argv){
    if(argc!=6){std::puts("mode baseline-cache candidate-cache sequence output.bmp");return 2;}
    const bool baseline=!strcmp(argv[1],"baseline"),modified=!strcmp(argv[1],"modified"),rollback=!strcmp(argv[1],"rollback");
    if(!baseline&&!modified&&!rollback)return 2;
    ScaledGlyphCache low,high;std::string error;
    if(!low.load(argv[2],error)||!high.load(argv[3],error)){std::printf("REJECT %s\n",error.c_str());return 2;}
    require(low.scale()==1&&low.height()==high.height()&&low.ids()==high.ids(),"same native mapping and logical metrics");
    if(modified)require(high.scale()>1,"candidate must contain rerasterized high-resolution cells");
    // Compare the complete active low-resolution atlas with the production native compositor.
    unsigned char object[64]{},font[108]{};*reinterpret_cast<unsigned char**>(object+8)=font;
    *reinterpret_cast<unsigned short*>(font+0x58)=static_cast<unsigned short>(low.height());*reinterpret_cast<unsigned*>(object+0x2c)=0xffffffff;
    for(auto pair:low.ids()){
        const int pitch=64;std::vector<unsigned> native(low.height()*pitch,0),scaled(native.size(),0);
        const unsigned char text[]={static_cast<unsigned char>(pair>>8),static_cast<unsigned char>(pair),0};int a=0,b=0;
        require(drawNativeCoverage(object,0,1,text,&a,native.data(),pitch),"native baseline glyph");
        require(low.draw(pair,0,1,b,0xffffffff,scaled.data(),scaled.size(),pitch),"scale-one glyph");
        require(a==b&&a==int(low.height())&&native==scaled,"baseline pixels and advances must be exact");
    }
    const auto& cache=modified?high:low;
    for(int origin:{-20,0,63,256})for(int y:{-2,0,1,2,30}){
        const int pitch=64*cache.scale();std::vector<unsigned> guarded(cache.height()*cache.scale()*pitch+2,0);
        guarded.front()=guarded.back()=0xfedcba98;int a=origin;
        require(cache.draw(cache.ids().front(),-1,y,a,0xffffffff,guarded.data()+1,guarded.size()-2,pitch),"scaled clip path");
        require(a==origin+int(cache.height())&&guarded.front()==0xfedcba98&&guarded.back()==0xfedcba98,"clip guards and logical advance");
    }
    std::ifstream seq(argv[4],std::ios::binary|std::ios::ate);if(!seq)return 2;auto n=seq.tellg();if(n<2||n>128||n%2)return 2;
    seq.seekg(0);std::vector<unsigned short> line;
    for(int j=0;j<int(n)/2;++j){unsigned char b[2];seq.read(reinterpret_cast<char*>(b),2);line.push_back(static_cast<unsigned short>(b[0]|unsigned(b[1])<<8));}
    const int w=static_cast<int>(line.size()*cache.height()*cache.scale()),h=cache.height()*cache.scale();
    std::vector<unsigned> image(w*h,0xff17242a);
    for(int pass=0;pass<5;++pass){const int xs[]={-1,1,-1,1,0},ys[]={0,0,2,2,1};int a=0;
        for(auto pair:line)require(cache.draw(pair,xs[pass],ys[pass],a,pass==4?0xffffffff:0xff000000,image.data(),image.size(),w),"mapped sample glyph");
        require(a==int(line.size()*cache.height()),"line metrics unchanged");}
    int unchanged=0;require(!cache.draw(0,0,0,unchanged,0xffffffff,image.data(),image.size(),w)&&unchanged==0,"unknown pair rejects without advancing");
    bitmap(argv[5],image,w,h);
    std::printf("SCALED_FONT %s PASS logical_height=%u physical_cell=%u advance=%u native_baseline=exact clipping=guarded game_started=false runtime_installed=false\n",modified?"MODIFIED":rollback?"ROLLBACK":"BASELINE",cache.height(),cache.height()*cache.scale(),cache.height());return 0;
}
