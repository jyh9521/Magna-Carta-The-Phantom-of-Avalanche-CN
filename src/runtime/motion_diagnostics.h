#pragma once
#include <cstdint>
#include "render_timeline.h"

namespace motion {
// Aggregate scalar evidence only. Never retain poses, actor addresses or game data.
struct DiagnosticWindow {
 uint64_t clocks=0,updates=0,owners=0,generations=0,invalid=0;
 uint64_t draws=0,midpoints=0,resets=0,resource=0,phase=0,sameFrame=0,jumps=0;
 uint64_t bones=0,unsupported=0,nearStretch=0,compatibleSwitches=0;
 uint64_t worldDraws=0,worldInitial=0,worldPhase=0,worldCuts=0,worldUnstable=0,worldSkipped=0;
 uint64_t cameraDraws=0,cameraInitial=0,cameraPhase=0,cameraCuts=0,cameraUnstable=0,cameraSkipped=0;
 float worldMaxStep=0,cameraMaxStep=0;
 unsigned jobVtableRva=0;
};
class Diagnostics {
 uintptr_t owner_=0;
 uint32_t start_=0;
 unsigned reports_=0;
 bool started_=false;
 DiagnosticWindow window_{};
public:
 bool enabled() const {return reports_<120;}
 void reset(){owner_=0;start_=0;reports_=0;started_=false;window_={};}
 void clock(uintptr_t owner,unsigned updates,bool generationChanged,bool valid,uint32_t now,unsigned jobRva){
  if(!started_){start_=now;started_=true;}
  ++window_.clocks;window_.updates+=updates;
  if(owner_&&owner_!=owner)++window_.owners;
  owner_=owner;window_.generations+=generationChanged;window_.invalid+=!valid;window_.jobVtableRva=jobRva;
 }
 void draw(float alpha,bool reset,bool resource,bool phase,bool sameFrame,bool jump,bool compatible=false){
  ++window_.draws;window_.midpoints+=alpha>0&&alpha<1;
  window_.resets+=reset;window_.resource+=resource;window_.phase+=phase;
  window_.sameFrame+=sameFrame;window_.jumps+=jump;window_.compatibleSwitches+=compatible;
 }
 void bone(bool accepted,bool stretch){++window_.bones;window_.unsupported+=!accepted;window_.nearStretch+=accepted&&stretch;}
 void transform(bool camera,const TransformObservation& o){
  if(camera){++window_.cameraDraws;window_.cameraInitial+=o.initial;window_.cameraPhase+=o.phaseReset;window_.cameraCuts+=o.cut;window_.cameraUnstable+=o.unstable;window_.cameraSkipped+=o.unsupported;
   if(o.translationStep>window_.cameraMaxStep)window_.cameraMaxStep=o.translationStep;
  }else{++window_.worldDraws;window_.worldInitial+=o.initial;window_.worldPhase+=o.phaseReset;window_.worldCuts+=o.cut;window_.worldUnstable+=o.unstable;window_.worldSkipped+=o.unsupported;
   if(o.translationStep>window_.worldMaxStep)window_.worldMaxStep=o.translationStep;
  }
 }
 void skippedWorld(){++window_.worldSkipped;}
 bool take(uint32_t now,DiagnosticWindow& out){
  if(!started_||reports_>=120||uint32_t(now-start_)<1000)return false;
  out=window_;window_={};start_=now;++reports_;return true;
 }
};
}
