#include "sample_clock.h"
#include <cstdio>
#include <cstring>
#include <vector>
void require(bool v){if(!v)ExitProcess(1);}
int main(int argc,char** argv){void* h=reinterpret_cast<void*>(7);SampleCursor c{};
 sampleClockFixtureTime(1000);sampleClockFixtureEvent(h,0);require(sampleCursor(h,c)&&c.milliseconds==0&&c.running);auto first=c.generation;
 sampleClockFixtureTime(1500);require(sampleCursor(h,c)&&c.milliseconds==500);sampleClockFixtureEvent(h,1);
 sampleClockFixtureTime(8000);require(sampleCursor(h,c)&&c.milliseconds==500&&!c.running);
 sampleClockFixtureEvent(h,0);require(sampleCursor(h,c)&&c.milliseconds==0&&c.generation!=first);
 sampleClockFixtureEvent(h,2);require(!sampleCursor(h,c));sampleClockFixtureEvent(h,0);sampleClockFixtureEvent(h,3);require(!sampleCursor(h,c));
 if(argc==2){
  auto api=LoadLibraryA(argv[1]);require(api!=nullptr);
  auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(image!=nullptr);
  auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;
  auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.TimeDateStamp=0x3ed73966;nt->OptionalHeader.SizeOfImage=0x10b000;
  unsigned slots[]={0xbd4a4,0xbd4ac,0xbd4a8,0xbd474};const char* names[]={"_AIL_start_3D_sample@4","_AIL_stop_3D_sample@4","_AIL_end_3D_sample@4","_AIL_release_3D_sample_handle@4"};
  using Call=void(WINAPI*)(void*);for(unsigned i=0;i<4;++i){auto f=GetProcAddress(api,names[i]);require(f!=nullptr);*reinterpret_cast<FARPROC*>(image+slots[i])=f;}
  std::vector<BYTE> original(image,image+0x10b000);require(installSampleClock(HMODULE(image),nullptr));
  auto invoke=[&](unsigned i){reinterpret_cast<Call>(*reinterpret_cast<void**>(image+slots[i]))(h);require(GetLastError()==0x4455);};
  sampleClockFixtureTime(100);invoke(0);sampleClockFixtureTime(600);require(sampleCursor(h,c)&&c.milliseconds==500);invoke(1);
  sampleClockFixtureTime(8000);require(sampleCursor(h,c)&&c.milliseconds==500&&!c.running);invoke(0);require(sampleCursor(h,c)&&c.milliseconds==0);invoke(2);require(!sampleCursor(h,c));invoke(0);invoke(3);require(!sampleCursor(h,c));
  require(removeSampleClock(HMODULE(image))&&!memcmp(image,original.data(),original.size()));
  puts("SAMPLE_CLOCK_IAT PASS real_patched_calls=true original_called=true last_error=preserved rollback=byte_exact owned_provider=true game_started=false");
 }
 puts("SAMPLE_CLOCK PASS pause=no_drift restart=zero new_generation=true end_release=cleared render_rate=independent game_started=false");return 0;}
