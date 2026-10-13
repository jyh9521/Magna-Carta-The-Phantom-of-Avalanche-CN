#pragma once
#include <windows.h>
struct MapSnapshot {int identifier=-1;float x=0,y=0,z=0;DWORD timestamp=0;bool valid=false;};
bool installMapOverlay(HMODULE,void(*logger)(const wchar_t*));
void stopMapOverlay();
void observeMapWorld(BYTE*,bool);
MapSnapshot readMapSnapshot();
struct MapMetadata {char magic[4];unsigned width,height;float bounds[4],origin[2],scale;};
bool mapMetadataValid(const MapMetadata&);
bool mapPixel(const MapMetadata&,float x,float y,float& px,float& py);
#ifdef MAP_OVERLAY_TEST
void mapOverlayTestInitialize(BYTE*);
bool mapOverlayTestHiddenWindow();
bool mapOverlayTestWait();
bool mapOverlayTestClickThrough();
bool mapOverlayTestRender(const wchar_t*,const wchar_t*);
#endif
