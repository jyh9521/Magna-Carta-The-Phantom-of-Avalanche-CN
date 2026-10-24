#pragma once
#include <windows.h>
// Memory DC only; the driver DC receives pixels, never fonts or text commands.
struct PanelCanvas {
 HDC dc=nullptr;HBITMAP bitmap=nullptr;HGDIOBJ old=nullptr;DWORD* pixels=nullptr;int width=0,height=0;
 ~PanelCanvas(){clear();}
 void clear(){if(dc){if(old)SelectObject(dc,old);if(bitmap)DeleteObject(bitmap);DeleteDC(dc);}dc=nullptr;bitmap=nullptr;old=nullptr;pixels=nullptr;width=height=0;}
 bool resize(int w,int h){if(dc&&width==w&&height==h)return true;if(w<1||h<1||w>8192||h>512)return false;clear();
  BITMAPINFO i{};i.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);i.bmiHeader.biWidth=w;i.bmiHeader.biHeight=-h;i.bmiHeader.biPlanes=1;i.bmiHeader.biBitCount=32;i.bmiHeader.biCompression=BI_RGB;
  dc=CreateCompatibleDC(nullptr);if(!dc)return false;bitmap=CreateDIBSection(dc,&i,DIB_RGB_COLORS,reinterpret_cast<void**>(&pixels),nullptr,0);if(!bitmap){clear();return false;}old=SelectObject(dc,bitmap);width=w;height=h;return true;
 }
};
