#include "motion60.h"
#include <cstdio>
#include <cstring>
#include <cmath>
#include <initializer_list>
static BYTE* image;
static void* partObject=nullptr;
static BYTE bones[12]{};
static float offset=0,body=0,part=0,bodyHeight=0,partHeight=0;
static bool cutCase=false;
static bool throwing=false;
static bool affineSkin=false;
static float partScale=.5f;
static unsigned calls=0;
MotionMatrix identity(float x){MotionMatrix m{};m.v[0]=m.v[5]=m.v[10]=m.v[15]=1;m.v[12]=x;return m;}
void __cdecl absolute(void*,unsigned,MotionMatrix*,MotionMatrix*){++calls;}
void __fastcall draw(void* value,void*,int,MotionMatrix* parent,int,int,int,int,int){
 auto o=static_cast<BYTE*>(value);auto pose=*reinterpret_cast<MotionMatrix**>(o+0x8c);
 float scale=affineSkin&&value==partObject?partScale:1.f;
 pose[0]=identity(offset/scale);if(cutCase)pose[0].v[14]=offset/scale;
 *reinterpret_cast<MotionMatrix*>(o+0xc)=parent?*parent:identity(0);
 (*reinterpret_cast<MotionAbsoluteFn*>(image+0xbd0a4))(bones,0,pose,nullptr);
 auto w=reinterpret_cast<MotionMatrix*>(o+0xc);
 float x=pose[0].v[12]*w->v[0]+w->v[12];
 if(value==partObject){part=x;partHeight=pose[0].v[14]*w->v[10]+w->v[14];}else{body=x;bodyHeight=pose[0].v[14]*w->v[10]+w->v[14];}
 if(throwing)RaiseException(0xe0000101,0,0,nullptr);
}
void require(bool ok,const char* s){if(!ok){printf("RIGID_MOTION FAIL %s body=%.6f part=%.6f\n",s,body,part);fflush(stdout);ExitProcess(1);}}
void emit(unsigned rva,unsigned prefix){
 BYTE* p=image+rva+prefix;*p++=0x5f;*p++=0x5e;*p++=0x8b;*p++=0xe5;*p++=0x5d;*p++=0xe9;
 *reinterpret_cast<int*>(p)=int(reinterpret_cast<BYTE*>(&draw)-p-4);
}
bool seh(MotionRenderFn r,void* o,MotionMatrix* parent){__try{r(o,1,parent,0,0,0,0,0);}__except(EXCEPTION_EXECUTE_HANDLER){return true;}return false;}
int main(int argc,char** argv){
 bool sceneCut=argc==2&&(!strcmp(argv[1],"--scene-cut")||!strcmp(argv[1],"--scene-cut-baseline"));bool oldCut=argc==2&&!strcmp(argv[1],"--scene-cut-baseline");cutCase=sceneCut;
 affineSkin=argc==2&&(!strcmp(argv[1],"--affine-skin")||!strcmp(argv[1],"--reflected-skin"));
 if(argc==2&&!strcmp(argv[1],"--reflected-skin"))partScale=-.5f;
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image,"allocation");motion60TestInitialize(image,absolute);
 BYTE rigidPrefix[]={0x55,0x8b,0xec,0x81,0xec,0xec,0x01,0,0,0x56,0x57};memcpy(image+0x3d12f,rigidPrefix,sizeof(rigidPrefix));
 BYTE call[]={0xff,0x15,0,0,0,0,0x83,0xc4,0x10};*reinterpret_cast<DWORD*>(call+2)=reinterpret_cast<DWORD>(image+0xbd0a4);memcpy(image+0x3d52e,call,sizeof(call));
 *reinterpret_cast<DWORD*>(image+0xbda18)=reinterpret_cast<DWORD>(image+0x3d12f);
 emit(0x3b0c0,11);emit(0x3d12f,11);
 DWORD oldBody=*reinterpret_cast<DWORD*>(image+0xbd9f8),oldPart=*reinterpret_cast<DWORD*>(image+0xbda18),oldAbsolute=*reinterpret_cast<DWORD*>(image+0xbd0a4);
 require(motion60TestSetMapped(image,0x10b000,absolute,true),"install");
 motion60TestComplete(image,true);
 auto skin=*reinterpret_cast<MotionRenderFn*>(image+0xbd9f8),rigid=affineSkin?skin:*reinterpret_cast<MotionRenderFn*>(image+0xbda18);
 BYTE a[0x100]{},action[0x28]{},data[0x28]{},rec[8]{};
 auto allocation=static_cast<BYTE*>(VirtualAlloc(nullptr,0x2000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(allocation,"rigid_layout_guard_allocation");DWORD old;
 require(VirtualProtect(allocation+0x1000,0x1000,PAGE_NOACCESS,&old)!=FALSE,"rigid_layout_guard_page");
 BYTE* b=allocation+0x1000-(affineSkin?0x100:0xd8);partObject=b;BYTE* seq[]={rec,rec};MotionMatrix pa{},pb{};
 *reinterpret_cast<unsigned*>(action+4)=2;*reinterpret_cast<unsigned*>(action+8)=1;*reinterpret_cast<BYTE***>(action+0x18)=seq;
 *reinterpret_cast<BYTE**>(rec+4)=data;*reinterpret_cast<unsigned*>(data+0x14)=1;
 for(auto o:{static_cast<BYTE*>(a),b}){*reinterpret_cast<BYTE**>(o+0xa0)=action;*reinterpret_cast<MotionMatrix**>(o+0x8c)=o==a?&pa:&pb;*reinterpret_cast<void**>(o+8)=data;}
 auto parent=identity(0),partParent=identity(0);
 if(affineSkin){partParent.v[0]=partScale;partParent.v[5]=partParent.v[10]=.5f;}
 motion60TestTick(0,0,1000);skin(a,0,&parent,0,0,0,0,0);rigid(b,0,&partParent,0,0,0,0,0);
 offset=10;parent=identity(20);partParent.v[12]=20;if(cutCase)parent.v[14]=partParent.v[14]=20;motion60TestTick(1,0,1033);*reinterpret_cast<unsigned*>(a+0xf8)=1;
 if(affineSkin)*reinterpret_cast<unsigned*>(b+0xf8)=1;
 skin(a,1,&parent,0,0,0,0,0);rigid(b,1,&partParent,0,0,0,0,0);
 if(sceneCut){
  // Same model, action, pose allocation and logical tick; a new Field/CG must
  // not inherit the preceding scene's body height or camera/world history.
  if(!oldCut)motion60SceneBoundary(reinterpret_cast<void*>(1),346,4);
  skin(a,1,&parent,0,0,0,0,0);rigid(b,1,&partParent,0,0,0,0,0);
  require(std::abs(body-30)<.0001f&&std::abs(part-30)<.0001f&&std::abs(bodyHeight-30)<.0001f&&std::abs(partHeight-30)<.0001f,"CG_cut_must_not_replay_old_scene_position");
  if(!oldCut)motion60SceneBoundary(reinterpret_cast<void*>(1),346,4);
  motion60TestTick(0,16,1049);skin(a,1,&parent,0,0,0,0,0);rigid(b,1,&partParent,0,0,0,0,0);
  require(std::abs(body-30)<.0001f&&std::abs(part-30)<.0001f&&std::abs(bodyHeight-30)<.0001f&&std::abs(partHeight-30)<.0001f,"held_cut_frame_must_remain_at_new_position");
  require(pa.v[12]==10&&pb.v[12]==10,"native_pose_restored_after_cut");
  require(motion60TestSetMapped(image,0x10b000,absolute,false),"cut rollback");
  puts("CG_SCENE_CUT PASS reused_model=true old_position=discarded body_part_height=exact held_frame=stable render60=retained native_pose=restored game_started=false");return 0;
 }
 require(std::abs(body-part)<.0001f,"body_and_rigid_part_must_share_tick_start");
 for(unsigned r=1;r<33;++r){motion60TestTick(0,r,1033+r);skin(a,1,&parent,0,0,0,0,0);rigid(b,1,&partParent,0,0,0,0,0);
  require(std::abs(body-part)<.0001f&&std::abs(body-30.f*r/33)<.0001f,"body_and_rigid_part_must_share_all_midpoints");
  require(pa.v[12]==10&&pb.v[12]==(affineSkin?10/partScale:10)&&!memcmp(b+0xc,&partParent,64),"restore_native_pose_and_world");
 }
 throwing=true;require(seh(rigid,b,&partParent),"propagate_SEH");throwing=false;require(pb.v[12]==(affineSkin?10/partScale:10)&&!memcmp(b+0xc,&partParent,64),"SEH_restore");
 require(motion60TestSetMapped(image,0x10b000,absolute,false),"rollback");
 require(*reinterpret_cast<DWORD*>(image+0xbd9f8)==oldBody&&*reinterpret_cast<DWORD*>(image+0xbda18)==oldPart&&*reinterpret_cast<DWORD*>(image+0xbd0a4)==oldAbsolute,"exact_slots");
 image[0x3d12f]^=1;require(!motion60TestSetMapped(image,0x10b000,absolute,true),"reject_rigid_prefix_drift_before_writes");
 require(*reinterpret_cast<DWORD*>(image+0xbd9f8)==oldBody&&*reinterpret_cast<DWORD*>(image+0xbd0a4)==oldAbsolute,"failed_install_atomic");
 image[0x3d12f]^=1;image[0x3d52e]^=1;require(!motion60TestSetMapped(image,0x10b000,absolute,true),"reject_rigid_call_drift");image[0x3d52e]^=1;
 *reinterpret_cast<DWORD*>(image+0xbda18)=1;require(!motion60TestSetMapped(image,0x10b000,absolute,true),"reject_rigid_slot_drift");
 require(*reinterpret_cast<DWORD*>(image+0xbd9f8)==oldBody&&*reinterpret_cast<DWORD*>(image+0xbd0a4)==oldAbsolute,"unknown_rigid_slot_no_partial_writes");
 VirtualFree(allocation,0,MEM_RELEASE);
 if(affineSkin)printf("AFFINE_WORLD PASS scaled_skin_part_phase=equal native_scale=preserved pose_world_restore=exact guard_page=passed game_started=false\n");
 printf("RIGID_MOTION PASS remainders=33 body_part_phase=equal pose_world_restore=exact seh=restored slots_rollback=exact game_started=false\n");return 0;
}
