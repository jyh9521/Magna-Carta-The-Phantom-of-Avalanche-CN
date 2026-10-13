#include "mouse_view.h"
#include "camera_input_view.h"
#include "mouse_view_transform.h"
#include <cstdio>
#include <cstring>
static BYTE* image=nullptr;static int checks=0;static bool active=true;static BYTE cameraData[0xc0]{};
struct Point{int x,y;};bool worldExplorationActive(){return active;}
void require(bool b,const char* s){++checks;if(!b){fprintf(stderr,"FAIL %s\n",s);ExitProcess(1);}}
Point* __cdecl mouse(Point* p){p->x=*reinterpret_cast<int*>(image+0xf20b0);p->y=*reinterpret_cast<int*>(image+0xf20a8);return p;}
Point* __cdecl center(Point* p){p->x=*reinterpret_cast<int*>(image+0xf1b48)/2;p->y=*reinterpret_cast<int*>(image+0xf1b4c)/2;return p;}
void jump(unsigned rva,void* p){image[rva]=0xe9;*reinterpret_cast<int32_t*>(image+rva+1)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(p)-reinterpret_cast<ULONG_PTR>(image+rva+5));}
int main(int argc,char** argv){
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image!=nullptr,"owned image");auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 jump(0x2e02,reinterpret_cast<void*>(&mouse));jump(0xd7bc,reinterpret_cast<void*>(&center));
 BYTE caller[]={0xff,0x74,0x24,0x04,0x90,0xe8,0,0,0,0,0x83,0xc4,0x04,0xc3};memcpy(image+0x6e927,caller,sizeof(caller));*reinterpret_cast<int32_t*>(image+0x6e92d)=0x2e02-0x6e931;
 *reinterpret_cast<int*>(image+0xf1b48)=800;*reinterpret_cast<int*>(image+0xf1b4c)=600;*reinterpret_cast<int*>(image+0xf20b0)=500;*reinterpret_cast<int*>(image+0xf20a8)=300;*reinterpret_cast<BYTE**>(image+0xf2290)=cameraData;
 float* source=reinterpret_cast<float*>(cameraData+0x80);source[0]=source[15]=1;source[5]=source[10]=.70710678f;source[6]=-.70710678f;source[9]=.70710678f;
 float displayed[16];memcpy(displayed,source,sizeof(displayed));displayed[0]=0;displayed[4]=1;displayed[1]=-.70710678f;displayed[5]=0;displayed[2]=.70710678f;displayed[6]=0;
 render_input::inputView.publish(displayed,reinterpret_cast<uintptr_t>(cameraData),GetTickCount(),true);
 using Call=Point*(__cdecl*)(Point*);auto fn=reinterpret_cast<Call>(image+0x6e927);Point p{};require(fn(&p)==&p&&p.x==500&&p.y==300,"baseline original point and return pointer");
 if(argc==2&&!strcmp(argv[1],"--baseline-check")){require(p.x==400&&p.y==159,"mouse ray follows rotated displayed view rather than source view");return 1;}
 if(argc==2&&!strcmp(argv[1],"--baseline-only")){printf("MOUSE_VIEW_BASELINE PASS point=500,300 source_camera=true game_started=false\n");return 0;}
 BYTE original[5];memcpy(original,image+0x6e92c,5);require(installMouseView(reinterpret_cast<HMODULE>(image),nullptr),"install guarded call");require(installMouseView(reinterpret_cast<HMODULE>(image),nullptr),"idempotence");
 require(fn(&p)==&p&&p.x==400&&p.y==159,"rotated local point and original return pointer");
 require(*reinterpret_cast<int*>(image+0xf20b0)==500&&*reinterpret_cast<int*>(image+0xf20a8)==300,"global UI cursor never changed");require(source[0]==1&&source[4]==0,"engine camera never changed");
 active=false;fn(&p);require(p.x==500&&p.y==300,"menus bypass");active=true;
 render_input::inputView.reset();fn(&p);require(p.x==500&&p.y==300,"orbit off bypass");
 render_input::inputView.publish(displayed,reinterpret_cast<uintptr_t>(cameraData)+1,GetTickCount(),true);fn(&p);require(p.x==500&&p.y==300,"wrong camera identity bypass");
 render_input::inputView.publish(displayed,reinterpret_cast<uintptr_t>(cameraData),GetTickCount()-251,true);fn(&p);require(p.x==500&&p.y==300,"stale view bypass");
 render_input::inputView.publish(displayed,reinterpret_cast<uintptr_t>(cameraData),GetTickCount(),true);source[6]=0;fn(&p);require(p.x==500&&p.y==300,"singular source ground basis bypass");source[6]=-.70710678f;
 auto saved=image[0x6e92c];image[0x6e92c]^=1;require(!removeMouseView(),"foreign code blocks restore");image[0x6e92c]=saved;
 require(removeMouseView()&&!memcmp(original,image+0x6e92c,5),"exact five-byte rollback");fn(&p);require(p.x==500&&p.y==300,"original mouse behavior restored");
 image[0x6e92d]^=1;require(!installMouseView(reinterpret_cast<HMODULE>(image),nullptr),"unknown source call rejects before mutation");
 int x=0,y=0;require(render_input::mouseViewPoint(source,source,400,300,500,300,x,y)&&x==500&&y==300,"identical views leave position unchanged");
 const int resolutions[]={800,1920,3840};for(int resolution:resolutions)for(int angle=0;angle<12;++angle)for(int direction=0;direction<4;++direction){
  float view[16];memcpy(view,source,sizeof(view));float a=angle*.52359878f,cs=std::cos(a),sn=std::sin(a),pitch=.3f+angle*.04f,sp=std::sin(pitch),cp=std::cos(pitch);view[0]=cs;view[4]=sn;view[1]=-cp*sn;view[5]=cp*cs;view[9]=sp;view[10]=cp;view[2]=sp*sn;view[6]=-sp*cs;
  int cx=resolution/2,cy=resolution*9/32,dx=(direction==0?400:direction==2?-400:0),dy=(direction==1?400:direction==3?-400:0);
  require(render_input::mouseViewPoint(source,view,cx,cy,cx+dx,cy+dy,x,y),"all orbit headings produce finite native point");
  double actualX=source[0]*(x-cx)+source[2]*(y-cy),actualY=source[4]*(x-cx)+source[6]*(y-cy);
  double wantedX=view[0]*dx+view[2]*dy,wantedY=view[4]*dx+view[6]*dy;
  require(std::abs(actualX-wantedX)<1&&std::abs(actualY-wantedY)<1,"native ground ray matches displayed ray within integer rounding");
 }
 displayed[0]=std::nanf("");require(!render_input::mouseViewPoint(source,displayed,400,300,500,300,x,y),"nonfinite view bypass");
 VirtualFree(image,0,MEM_RELEASE);printf("MOUSE_VIEW_FIXTURE PASS checks=%d scope=mouse_movement ui_cursor=unchanged camera=unchanged identity_age=guarded rollback=exact game_started=false\n",checks);
 if(argc==2&&!strcmp(argv[1],"--rollback-check"))printf("MOUSE_VIEW_ROLLBACK PASS original_point=500,300 original_call=exact active_runtime=unchanged game_started=false\n");
}
