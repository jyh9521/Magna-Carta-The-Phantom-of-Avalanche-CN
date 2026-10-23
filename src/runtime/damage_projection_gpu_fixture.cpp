// Owned offscreen Direct3D7 harness. No commercial DLL is mapped or loaded.
#include <windows.h>
#include <ddraw.h>
#include <d3d.h>
#include <cstdio>
#include <vector>
#include <fstream>
#include <stdexcept>
#include <cmath>
#include <algorithm>
struct V {float x,y,z;DWORD reserved,color,specular;float u,v;};
struct Input {DWORD magic,width,height,vx,vy,vw,vh;D3DMATRIX modelview,view,projection;DWORD primitive,count,tw,th,rcount,scount;};
static_assert(sizeof(V)==32);
void hr(HRESULT h,const char* stage){if(FAILED(h)){printf("GPU_FAIL stage=%s hr=%08lx\n",stage,(unsigned long)h);throw std::runtime_error(stage);}}
void require(bool b,const char* stage){if(!b)throw std::runtime_error(stage);}
int wmain(int argc,wchar_t** argv){
 if(argc<2||argc>3)return 2;
 HMODULE dd=nullptr;HWND window=nullptr;IDirectDraw7* draw=nullptr;IDirect3D7* d3d=nullptr;IDirectDrawSurface7* target=nullptr;IDirectDrawSurface7* texture=nullptr;IDirect3DDevice7* device=nullptr;int code=1;
 try{
  std::ifstream in(argv[1],std::ios::binary);Input s{};in.read(reinterpret_cast<char*>(&s),sizeof(s));
  require(bool(in)&&s.magic==0x33504744&&s.width>=64&&s.height>=64&&s.width<=4096&&s.height<=4096&&s.count>0&&s.count<65536,"owned input header");
  require(s.vw>0&&s.vh>0&&s.vx<=s.width&&s.vy<=s.height&&s.vw<=s.width-s.vx&&s.vh<=s.height-s.vy,"viewport bounds");
  require((s.tw==0)==(s.th==0)&&s.tw<=4096&&s.th<=4096,"texture bounds");require(s.rcount<=256&&s.scount<=256,"state counts");
  for(float value:*reinterpret_cast<const float(*)[48]>(&s.modelview))require(std::isfinite(value),"finite transforms");
  std::vector<V> vertices(s.count);in.read(reinterpret_cast<char*>(vertices.data()),vertices.size()*sizeof(V));require(bool(in),"owned vertices");
  for(const auto& v:vertices)require(std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z)&&std::isfinite(v.u)&&std::isfinite(v.v),"finite vertices");
  std::vector<DWORD> texels(size_t(s.tw)*s.th);if(s.tw&&s.th){in.read(reinterpret_cast<char*>(texels.data()),texels.size()*4);require(bool(in),"native texture pixels");}
  struct RS{DWORD state,value;};struct TS{DWORD stage,state,value;};std::vector<RS> renderstates(s.rcount);std::vector<TS> stagestates(s.scount);
  if(s.rcount){in.read(reinterpret_cast<char*>(renderstates.data()),renderstates.size()*sizeof(RS));require(bool(in),"render state capsule");}
  if(s.scount){in.read(reinterpret_cast<char*>(stagestates.data()),stagestates.size()*sizeof(TS));require(bool(in),"stage state capsule");}
  wchar_t system[32768]{};require(GetSystemDirectoryW(system,32768)>0,"system directory");std::wstring path=system;path+=L"\\ddraw.dll";
  dd=LoadLibraryW(path.c_str());require(dd!=nullptr,"system ddraw");
  using Create=HRESULT(WINAPI*)(GUID*,void**,REFIID,IUnknown*);auto create=reinterpret_cast<Create>(GetProcAddress(dd,"DirectDrawCreateEx"));require(create!=nullptr,"draw export");
  window=CreateWindowExW(0,L"STATIC",L"OwnedDamageOffscreen",WS_POPUP,0,0,64,64,nullptr,nullptr,nullptr,nullptr);require(window!=nullptr,"hidden window");
  hr(create(nullptr,reinterpret_cast<void**>(&draw),IID_IDirectDraw7,nullptr),"draw");hr(draw->SetCooperativeLevel(window,DDSCL_NORMAL),"normal cooperative");hr(draw->QueryInterface(IID_IDirect3D7,reinterpret_cast<void**>(&d3d)),"d3d7");
  DDSURFACEDESC2 desc{};desc.dwSize=sizeof(desc);desc.dwFlags=DDSD_CAPS|DDSD_WIDTH|DDSD_HEIGHT|DDSD_PIXELFORMAT;desc.dwWidth=s.width;desc.dwHeight=s.height;
  desc.ddsCaps.dwCaps=DDSCAPS_OFFSCREENPLAIN|DDSCAPS_3DDEVICE|DDSCAPS_VIDEOMEMORY;desc.ddpfPixelFormat.dwSize=sizeof(DDPIXELFORMAT);desc.ddpfPixelFormat.dwFlags=DDPF_RGB;desc.ddpfPixelFormat.dwRGBBitCount=32;desc.ddpfPixelFormat.dwRBitMask=0xff0000;desc.ddpfPixelFormat.dwGBitMask=0xff00;desc.ddpfPixelFormat.dwBBitMask=0xff;
  hr(draw->CreateSurface(&desc,&target,nullptr),"offscreen surface");hr(d3d->CreateDevice(IID_IDirect3DHALDevice,target,&device),"HAL device");
  D3DVIEWPORT7 vp{s.vx,s.vy,s.vw,s.vh,0,1};hr(device->SetViewport(&vp),"viewport");
  hr(device->SetTransform(D3DTRANSFORMSTATE_WORLD,&s.modelview),"native world/modelview");hr(device->SetTransform(D3DTRANSFORMSTATE_VIEW,&s.view),"identity view");hr(device->SetTransform(D3DTRANSFORMSTATE_PROJECTION,&s.projection),"native projection");
  hr(device->SetRenderState(D3DRENDERSTATE_ZENABLE,D3DZB_FALSE),"z off");hr(device->SetRenderState(D3DRENDERSTATE_LIGHTING,FALSE),"lighting off");hr(device->SetRenderState(D3DRENDERSTATE_CULLMODE,D3DCULL_NONE),"cull off");hr(device->SetRenderState(D3DRENDERSTATE_ALPHABLENDENABLE,FALSE),"alpha off");hr(device->SetTexture(0,nullptr),"texture none");
  hr(device->SetTextureStageState(0,D3DTSS_COLOROP,D3DTOP_SELECTARG1),"color select");hr(device->SetTextureStageState(0,D3DTSS_COLORARG1,D3DTA_DIFFUSE),"owned vertex color");
  if(s.tw&&s.th){
   DDSURFACEDESC2 td=desc;td.dwWidth=s.tw;td.dwHeight=s.th;td.ddsCaps.dwCaps=DDSCAPS_TEXTURE;td.ddsCaps.dwCaps2=DDSCAPS2_TEXTUREMANAGE;td.ddpfPixelFormat.dwFlags|=DDPF_ALPHAPIXELS;td.ddpfPixelFormat.dwRGBAlphaBitMask=0xff000000;
   hr(draw->CreateSurface(&td,&texture,nullptr),"native texture");DDSURFACEDESC2 tb{};tb.dwSize=sizeof(tb);hr(texture->Lock(nullptr,&tb,DDLOCK_WAIT,nullptr),"texture lock");
   for(unsigned y=0;y<s.th;++y)memcpy(static_cast<BYTE*>(tb.lpSurface)+y*tb.lPitch,texels.data()+y*s.tw,s.tw*4);hr(texture->Unlock(nullptr),"texture unlock");hr(device->SetTexture(0,texture),"native texture bind");
   hr(device->SetTextureStageState(0,D3DTSS_COLOROP,D3DTOP_MODULATE),"texture modulate");hr(device->SetTextureStageState(0,D3DTSS_COLORARG1,D3DTA_TEXTURE),"texture color");hr(device->SetTextureStageState(0,D3DTSS_COLORARG2,D3DTA_DIFFUSE),"native diffuse");
   hr(device->SetTextureStageState(0,D3DTSS_ALPHAOP,D3DTOP_SELECTARG1),"texture alpha");hr(device->SetTextureStageState(0,D3DTSS_ALPHAARG1,D3DTA_TEXTURE),"texture alpha1");hr(device->SetTextureStageState(0,D3DTSS_ALPHAARG2,D3DTA_DIFFUSE),"texture alpha2");
   hr(device->SetRenderState(D3DRENDERSTATE_ALPHABLENDENABLE,TRUE),"blend on");hr(device->SetRenderState(D3DRENDERSTATE_SRCBLEND,D3DBLEND_SRCALPHA),"src alpha");hr(device->SetRenderState(D3DRENDERSTATE_DESTBLEND,D3DBLEND_INVSRCALPHA),"dest alpha");
  }else for(auto& v:vertices){v.color=0xff00ff00;v.specular=0;}
  for(const auto& state:renderstates)hr(device->SetRenderState(D3DRENDERSTATETYPE(state.state),state.value),"captured native render state");
  for(const auto& state:stagestates)hr(device->SetTextureStageState(state.stage,D3DTEXTURESTAGESTATETYPE(state.state),state.value),"captured native stage state");
  hr(device->Clear(0,nullptr,D3DCLEAR_TARGET,0,1,0),"clear");hr(device->BeginScene(),"begin");hr(device->DrawPrimitive(D3DPRIMITIVETYPE(s.primitive),0x1e2,vertices.data(),s.count,0),"native-layout DrawPrimitive");hr(device->EndScene(),"end");
  DDSURFACEDESC2 bits{};bits.dwSize=sizeof(bits);hr(target->Lock(nullptr,&bits,DDLOCK_READONLY|DDLOCK_WAIT,nullptr),"readback");
  int minx=int(s.width),miny=int(s.height),maxx=-1,maxy=-1;unsigned pixels=0;
  for(unsigned y=0;y<s.height;++y)for(unsigned x=0;x<s.width;++x){DWORD v=*reinterpret_cast<DWORD*>(static_cast<BYTE*>(bits.lpSurface)+y*bits.lPitch+x*4);if((v&0xffffff)!=0){minx=(std::min)(minx,int(x));miny=(std::min)(miny,int(y));maxx=(std::max)(maxx,int(x));maxy=(std::max)(maxy,int(y));++pixels;}}
  if(argc==3){std::ofstream image(argv[2],std::ios::binary);BITMAPFILEHEADER fh{};BITMAPINFOHEADER ih{};fh.bfType=0x4d42;fh.bfOffBits=sizeof(fh)+sizeof(ih);fh.bfSize=fh.bfOffBits+s.width*s.height*4;ih.biSize=sizeof(ih);ih.biWidth=s.width;ih.biHeight=-LONG(s.height);ih.biPlanes=1;ih.biBitCount=32;ih.biCompression=BI_RGB;image.write(reinterpret_cast<const char*>(&fh),sizeof(fh));image.write(reinterpret_cast<const char*>(&ih),sizeof(ih));for(unsigned y=0;y<s.height;++y)image.write(static_cast<const char*>(bits.lpSurface)+y*bits.lPitch,s.width*4);require(bool(image),"BMP output write");}
  hr(target->Unlock(nullptr),"unlock");printf("DAMAGE_GPU_PIXELS target=%lux%lu viewport=%lu,%lu,%lu,%lu fvf=0x1e2 bbox=%d,%d,%d,%d pixels=%u device=HAL game_started=false commercial_dll_loaded=false display_mode_changed=false\n",s.width,s.height,s.vx,s.vy,s.vw,s.vh,minx,miny,maxx,maxy,pixels);code=0;
 }catch(const std::exception& e){printf("DAMAGE_GPU_ERROR %s\n",e.what());}
 if(device)device->Release();if(texture)texture->Release();if(target)target->Release();if(d3d)d3d->Release();if(draw)draw->Release();if(window)DestroyWindow(window);if(dd)FreeLibrary(dd);
 return code;
}
