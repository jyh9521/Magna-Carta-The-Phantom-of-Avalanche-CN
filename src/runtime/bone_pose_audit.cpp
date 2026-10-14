#include "render_timeline.h"
#include <filesystem>
#include <fstream>
#include <vector>
#include <cstdio>
#include <stdexcept>
#include <cstring>
#include <chrono>
#include <cmath>
using namespace motion;
static bool negative(const Matrix& m){return double(m.v[0])*(double(m.v[5])*m.v[10]-double(m.v[6])*m.v[9])-double(m.v[1])*(double(m.v[4])*m.v[10]-double(m.v[6])*m.v[8])+double(m.v[2])*(double(m.v[4])*m.v[9]-double(m.v[5])*m.v[8])<0;}
static bool oldPose(const Matrix& m){if(rigid(m))return true;Matrix a=m;for(int row=0;row<3;++row)a.v[row]=-a.v[row];return rigid(a);}
int main(int argc,char** argv){try{
 if(argc!=2)throw std::runtime_error("Usage: bone_pose_audit ANI_DIRECTORY");
 unsigned files=0;uint64_t matrices=0,oldAccepted=0,newAccepted=0,pairs=0,parityChanges=0;auto start=std::chrono::steady_clock::now();
 for(const auto& entry:std::filesystem::directory_iterator(argv[1])){
  if(entry.path().extension()!=L".ani")continue;
  auto size=entry.file_size();if(size<20||size>512*1024*1024)throw std::runtime_error("Unsupported ANI size");
  std::vector<char> bytes(static_cast<size_t>(size));std::ifstream in(entry.path(),std::ios::binary);if(!in.read(bytes.data(),bytes.size()))throw std::runtime_error("ANI read failed");
  uint32_t header[5];memcpy(header,bytes.data(),20);auto frames=header[1],stride=header[2],samples=header[3],bones=header[4];
  if(!stride||frames>100000||samples>100000||bones>512||samples!=(uint64_t(frames)+stride-1)/stride)throw std::runtime_error("Unsupported ANI header");
  uint64_t needed=20+uint64_t(bones)*(samples+1)*64;if(needed>size)throw std::runtime_error("Truncated ANI pose data");
  size_t at=20;for(unsigned bone=0;bone<bones;++bone){Matrix previous{};
   for(unsigned sample=0;sample<=samples;++sample){Matrix current{};memcpy(&current,bytes.data()+at,64);at+=64;for(float v:current.v)if(!std::isfinite(v))throw std::runtime_error("Nonfinite ANI pose");
    if(sample){++matrices;oldAccepted+=oldPose(current);newAccepted+=poseInterpolatable(current);
     if(sample>1){Matrix mid{};blend(previous,current,.5f,mid);++pairs;parityChanges+=negative(previous)!=negative(current);for(float v:mid.v)if(!std::isfinite(v))throw std::runtime_error("Nonfinite midpoint");}
    }previous=current;
   }
  }
  for(unsigned bone=0;bone<bones;++bone){uint32_t metadata[2];if(at+8>size)throw std::runtime_error("Truncated ANI metadata");memcpy(metadata,bytes.data()+at,8);at+=8;
   auto count=metadata[1];if(count>bones||at+uint64_t(count)*4>size)throw std::runtime_error("Invalid ANI children");
   for(unsigned k=0;k<count;++k){uint32_t child;memcpy(&child,bytes.data()+at,4);at+=4;if(child>=bones)throw std::runtime_error("ANI child out of range");}
  }
  if(at!=size)throw std::runtime_error("ANI trailing bytes");++files;
 }
 if(!files)throw std::runtime_error("No ANI inputs");
 auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
 printf("BONE_POSE_AUDIT PASS files=%u matrices=%llu old_accepted=%llu new_accepted=%llu pairs=%llu parity_changes=%llu elapsed_ms=%lld source_modified=false live_render_verified=false\n",files,matrices,oldAccepted,newAccepted,pairs,parityChanges,ms);
 return 0;
}catch(const std::exception& e){fprintf(stderr,"BONE_POSE_AUDIT FAIL %s\n",e.what());return 1;}}
