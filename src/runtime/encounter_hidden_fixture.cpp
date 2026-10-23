// Hidden-window integration probe; never starts the game or changes display mode.
#include "encounter_control.h"
#include <ddraw.h>
#include <cstdio>
#include "encounter_control.cpp"
int wmain(int argc,wchar_t** argv){
 HINSTANCE instance=GetModuleHandleW(nullptr);WNDCLASSW cls{};cls.lpfnWndProc=DefWindowProcW;cls.hInstance=instance;cls.lpszClassName=L"EncounterHiddenProbe";
 RegisterClassW(&cls);HWND w=CreateWindowExW(WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,cls.lpszClassName,L"",WS_POPUP,0,0,320,40,nullptr,nullptr,instance,nullptr);
 IDirectDraw7* dd=nullptr;
 if(argc>1){auto lib=LoadLibraryW(argv[1]);auto create=lib?reinterpret_cast<HRESULT(WINAPI*)(GUID*,void**,REFIID,IUnknown*)>(GetProcAddress(lib,"DirectDrawCreateEx")):nullptr;
  HRESULT hr=create?create(nullptr,reinterpret_cast<void**>(&dd),IID_IDirectDraw7,nullptr):E_FAIL;
  printf("DDRAW_PROBE create=%08lx\n",hr);if(FAILED(hr))return 2;
  hr=dd->SetCooperativeLevel(w,DDSCL_NORMAL);printf("DDRAW_PROBE cooperative_normal=%08lx\n",hr);if(FAILED(hr))return 3;
 }
 IDirectDrawSurface7* primary=nullptr;
 if(dd){DDSURFACEDESC2 desc{};desc.dwSize=sizeof(desc);desc.dwFlags=DDSD_CAPS;desc.ddsCaps.dwCaps=DDSCAPS_PRIMARYSURFACE;
  auto hr=dd->CreateSurface(&desc,&primary,nullptr);printf("DDRAW_PROBE primary=%08lx\n",hr);if(FAILED(hr))return 4;}
 SetLastError(0);bool ok=present(w,RECT{100,100,2020,1180},1);auto error=ok?0:GetLastError();RECT bounds{};GetWindowRect(w,&bounds);
 bool positioned=bounds.left==1704&&bounds.top==1126&&bounds.right==2004&&bounds.bottom==1156;
 printf("HUD_REAL_API %s present=%d error=%lu positioned=%d window_visible=%d\n",ok&&positioned?"PASS":"FAIL",ok,error,positioned,IsWindowVisible(w));
 if(primary)primary->Release();DestroyWindow(w);if(dd)dd->Release();return ok&&positioned?0:1;
}
