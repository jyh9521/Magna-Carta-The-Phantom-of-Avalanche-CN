#pragma once
#include <windows.h>
#include "map_collectibles.h"
struct MapLandmark {int id=0,kind=0;float x=0,y=0,z=0;MapCollectibleState collectible=MapCollectibleState::Unknown;};
struct MapTrailPoint {float x=0,y=0;};
struct MapSnapshot {int identifier=-1,fieldIdentifier=-1,actorIdentifier=-1;float x=0,y=0,z=0,directionX=0,directionY=0;DWORD timestamp=0;bool valid=false,landmarksTruncated=false;unsigned landmarkCount=0,trailCount=0;MapLandmark landmarks[64]{};MapTrailPoint trail[128]{};};
bool installMapOverlay(HMODULE,void(*logger)(const wchar_t*));
void stopMapOverlay();
void observeMapWorld(BYTE*,bool);
MapSnapshot readMapSnapshot();
struct MapMetadata {char magic[4];unsigned width,height;float bounds[4],origin[2],scale;};
bool mapMetadataValid(const MapMetadata&);
bool mapPixel(const MapMetadata&,float x,float y,float& px,float& py);
struct MapView {float left=0,top=0,span=0;};
bool mapView(const MapMetadata&,float playerX,float playerY,bool mini,MapView&);
bool mapViewPoint(const MapMetadata&,const MapView&,float x,float y,float size,float& px,float& py);
bool mapPlayerHeading(float worldX,float worldY,float& screenX,float& screenY);
struct MapPointHeader {char magic[4];unsigned fieldIdentifier,mapIdentifier,count;};
struct MapExitPoint {int eventIndex,regionId,targetField,targetMap,triggerActor;unsigned flags;float x,y,z;};
bool mapPointAssetValid(const MapPointHeader&,const MapExitPoint*,size_t bytes,int fieldIdentifier,int mapIdentifier);
bool mapExitApplies(const MapExitPoint&,const MapSnapshot&);
enum class MapDisplayMode {Off,Mini,Full};
struct MapDisplayState {MapDisplayMode mode=MapDisplayMode::Off;bool held=true;};
// Inactive frames hide the window and require a release before the next cycle.
MapDisplayMode mapDisplayStep(MapDisplayState&,bool active,bool pressed);
MapDisplayMode mapDisplayCycle(MapDisplayState&);
struct MapOverlayLayout {int x=0,y=0,width=0,height=0;float scale=1;};
bool mapOverlayLayout(int clientWidth,int clientHeight,MapDisplayMode,MapOverlayLayout&);
BYTE mapOverlayOpacity(MapDisplayMode);
#ifdef MAP_OVERLAY_TEST
void mapOverlayTestInitialize(BYTE*);
bool mapOverlayTestHiddenWindow();
bool mapOverlayTestWait();
bool mapOverlayTestClickThrough();
bool mapOverlayTestWindowAppearance(MapDisplayMode);
bool mapOverlayTestResetState();
unsigned mapOverlayTestLoadPoints(const wchar_t* assets,int fieldIdentifier,int mapIdentifier);
MapExitPoint mapOverlayTestPoint(unsigned index);
bool mapOverlayTestRender(const wchar_t*,const wchar_t*,bool mini=false);
bool mapOverlayTestRenderMode(const wchar_t*,const wchar_t*,MapDisplayMode,int width,int height,bool encodeTransparency=true);
#endif
