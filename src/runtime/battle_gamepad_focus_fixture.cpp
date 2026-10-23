#include "gamepad_ui.cpp"
#include <iostream>
#include <memory>
#include <stdexcept>
#include <cstring>
// Owned-memory adapter around the exact production navigate() implementation.
// The native-PE replay supplies source-derived GUI fields and hit rectangles.
static std::vector<BYTE*> cancellationNodes;
static std::vector<unsigned> cancellationCalls;
static void __fastcall recordNativeClear(void* value,void*){
 for(unsigned i=0;i<cancellationNodes.size();++i)if(value==cancellationNodes[i])cancellationCalls.push_back(i);
}
int main(int argc,char** argv){
 bool events=argc>1&&!strcmp(argv[1],"--events");
 try{
  auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));if(!image)throw std::runtime_error("allocation");
  engine=image;
  // Record the native clear-method boundary. The PE replay invokes its actual
  // 5718F implementation for these indices, preserving resource/visual effects.
  DWORD old;VirtualProtect(image+0x57000,0x1000,PAGE_EXECUTE_READWRITE,&old);
  image[0x5718f]=0xe9;*reinterpret_cast<int32_t*>(image+0x57190)=static_cast<int32_t>(reinterpret_cast<BYTE*>(&recordNativeClear)-(image+0x57194));
  unsigned frames=0;
  while(true){
   unsigned count,active,held,pressed,serial,time;int w,h,x,y,modal;
   if(!(std::cin>>count))break;
   if(!(std::cin>>active>>held>>pressed>>serial>>time>>w>>h>>x>>y>>modal)||!count||count>128)throw std::runtime_error("frame header");
   unsigned cancel=0;if(events&&!(std::cin>>cancel))throw std::runtime_error("cancel flag");
   std::vector<std::array<BYTE,0x220>> nodes(count);std::vector<std::array<int,4>> rectangles;rectangles.reserve(count*32);
   std::vector<std::array<BYTE,8>> lists;lists.reserve(count*32);
   std::vector<int> children(count),siblings(count);std::vector<unsigned> rectStart(count),rectCount(count);
   for(unsigned i=0;i<count;++i){
    unsigned vt,id,visible,enabled,mode,listener,nrect,arrows[4];float ox,oy;
    if(!(std::cin>>vt>>id>>children[i]>>siblings[i]>>visible>>enabled>>mode>>listener>>ox>>oy>>nrect>>arrows[0]>>arrows[1]>>arrows[2]>>arrows[3])||vt>0x10ac00||nrect>32)throw std::runtime_error("node");
    BYTE* p=nodes[i].data();*reinterpret_cast<BYTE**>(p)=image+vt;*reinterpret_cast<unsigned*>(p+4)=id;
    *reinterpret_cast<int*>(p+0xe8)=visible;*reinterpret_cast<int*>(p+0x160)=enabled;*reinterpret_cast<int*>(p+0x164)=mode;
    *reinterpret_cast<void**>(p+0x17c)=listener?nodes[0].data():nullptr;*reinterpret_cast<float*>(p+0x24)=ox;*reinterpret_cast<float*>(p+0x28)=oy;
    for(unsigned a=0;a<4;++a)*reinterpret_cast<BYTE**>(image+vt+0xc8+a*4)=image+arrows[a];
    if(events){unsigned press;if(!(std::cin>>press))throw std::runtime_error("press field");*reinterpret_cast<unsigned*>(p+0x19c)=press;}
    rectStart[i]=unsigned(rectangles.size());rectCount[i]=nrect;
    for(unsigned n=0;n<nrect;++n){std::array<int,4> r{};if(!(std::cin>>r[0]>>r[1]>>r[2]>>r[3]))throw std::runtime_error("rect");rectangles.push_back(r);lists.push_back({});}
   }
   for(unsigned i=0;i<count;++i){
    BYTE* p=nodes[i].data();auto valid=[&](int j){return j>=0&&unsigned(j)<count;};
    if(valid(children[i]))*reinterpret_cast<BYTE**>(p+0x18)=nodes[children[i]].data();
    if(valid(siblings[i]))*reinterpret_cast<BYTE**>(p+0x10)=nodes[siblings[i]].data();
    *reinterpret_cast<unsigned*>(p+0xf8)=rectCount[i];
    if(rectCount[i])*reinterpret_cast<BYTE**>(p+0x100)=lists[rectStart[i]].data();
    for(unsigned n=0;n<rectCount[i];++n){unsigned k=rectStart[i]+n;*reinterpret_cast<void**>(lists[k].data())=rectangles[k].data();if(n+1<rectCount[i])*reinterpret_cast<void**>(lists[k].data()+4)=lists[k+1].data();}
   }
   BYTE manager[0x40]{},exclusive[8]{};if(modal>=0&&unsigned(modal)<count){*reinterpret_cast<unsigned*>(manager+0x38)=1;*reinterpret_cast<void**>(manager+0x3c)=exclusive;*reinterpret_cast<void**>(exclusive)=nodes[modal].data();}
   *reinterpret_cast<void**>(image+0xf220c)=manager;*reinterpret_cast<int*>(image+0xf1b48)=w;*reinterpret_cast<int*>(image+0xf1b4c)=h;
   *reinterpret_cast<int*>(image+0xf20b0)=x;*reinterpret_cast<int*>(image+0xf20a8)=y;
   configureModernNavigationFixture(image,{held,pressed,serial,time,active!=0});
   cancellationNodes.clear();cancellationCalls.clear();for(auto& node:nodes)cancellationNodes.push_back(node.data());
   if(cancel)cancelMenuRoot(nodes[0].data());
   navigate(nodes[0].data());
   if(events){std::cout<<"{\"cursor\":["<<*reinterpret_cast<int*>(image+0xf20b0)<<","<<*reinterpret_cast<int*>(image+0xf20a8)<<"],\"native_clear_indices\":[";for(unsigned i=0;i<cancellationCalls.size();++i){if(i)std::cout<<",";std::cout<<cancellationCalls[i];}std::cout<<"]}"<<std::endl;}
   else std::cout<<*reinterpret_cast<int*>(image+0xf20b0)<<' '<<*reinterpret_cast<int*>(image+0xf20a8)<<std::endl;++frames;
  }
  VirtualFree(image,0,MEM_RELEASE);return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
