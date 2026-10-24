#include "sample_clock.h"
#include <map>
#include <cstring>
namespace {
struct Clock {uint64_t started=0,elapsed=0,generation=0;bool running=false;};
std::map<void*,Clock> clocks;SRWLOCK lock=SRWLOCK_INIT;uint64_t generation=0;
using Event=void(WINAPI*)(void*);
BYTE* engine=nullptr;Event originals[4]{};
constexpr unsigned slots[]={0xbd4a4,0xbd4ac,0xbd4a8,0xbd474};
constexpr const char* names[]={"_AIL_start_3D_sample@4","_AIL_stop_3D_sample@4","_AIL_end_3D_sample@4","_AIL_release_3D_sample_handle@4"};
#ifdef SAMPLE_CLOCK_TEST
uint64_t fixtureTime=0;
#endif
uint64_t now(){
#ifdef SAMPLE_CLOCK_TEST
 return fixtureTime;
#else
 return GetTickCount64();
#endif
}
void event(void* h,unsigned kind){if(!h)return;AcquireSRWLockExclusive(&lock);auto time=now();
 if(kind==0){if(clocks.size()<4096||clocks.count(h))clocks[h]={time,0,++generation,true};}
 else if(kind==1){auto i=clocks.find(h);if(i!=clocks.end()&&i->second.running){i->second.elapsed+=time-i->second.started;i->second.running=false;}}
 else clocks.erase(h);
 ReleaseSRWLockExclusive(&lock);
}
void WINAPI start(void* h){DWORD error=GetLastError();event(h,0);SetLastError(error);originals[0](h);}
void WINAPI stop(void* h){DWORD error=GetLastError();event(h,1);SetLastError(error);originals[1](h);}
void WINAPI end(void* h){DWORD error=GetLastError();event(h,2);SetLastError(error);originals[2](h);}
void WINAPI release(void* h){DWORD error=GetLastError();event(h,3);SetLastError(error);originals[3](h);}
Event hooks[]={&start,&stop,&end,&release};
bool write(DWORD* p,DWORD from,DWORD to){if(*p!=from)return false;DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;*p=to;DWORD ignored;return VirtualProtect(p,4,old,&ignored)!=0;}
}
bool sampleCursor(void* h,SampleCursor& out){AcquireSRWLockShared(&lock);auto i=clocks.find(h);bool found=i!=clocks.end();if(found){const auto& c=i->second;out={c.elapsed+(c.running?now()-c.started:0),c.generation,c.running};}ReleaseSRWLockShared(&lock);return found;}
bool installSampleClock(HMODULE module,void(*trace)(const wchar_t*)){
 auto p=reinterpret_cast<BYTE*>(module);auto m=GetModuleHandleW(L"Mss32.dll");if(!p||!m)return false;
 if(engine)return engine==p;
 auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<64||d->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+d->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.TimeDateStamp!=0x3ed73966||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 for(unsigned i=0;i<4;++i){originals[i]=reinterpret_cast<Event>(GetProcAddress(m,names[i]));if(!originals[i]||*reinterpret_cast<Event*>(p+slots[i])!=originals[i])return false;}
 for(unsigned i=0;i<4;++i)if(!write(reinterpret_cast<DWORD*>(p+slots[i]),DWORD(originals[i]),DWORD(hooks[i]))){for(unsigned j=0;j<i;++j)write(reinterpret_cast<DWORD*>(p+slots[j]),DWORD(hooks[j]),DWORD(originals[j]));return false;}
 engine=p;if(trace)trace(L"SAMPLE_CLOCK_READY source=actual_3d_start_stop_end_release restart=new_generation render_delta=false");return true;
}
bool sampleClockOwned(HMODULE module){if(engine!=reinterpret_cast<BYTE*>(module))return false;for(unsigned i=0;i<4;++i)if(*reinterpret_cast<Event*>(engine+slots[i])!=hooks[i])return false;return true;}
bool removeSampleClock(HMODULE module){if(!sampleClockOwned(module))return false;
 for(unsigned i=0;i<4;++i)if(!write(reinterpret_cast<DWORD*>(engine+slots[i]),DWORD(hooks[i]),DWORD(originals[i])))return false;
 engine=nullptr;AcquireSRWLockExclusive(&lock);clocks.clear();ReleaseSRWLockExclusive(&lock);return true;
}
#ifdef SAMPLE_CLOCK_TEST
void sampleClockFixtureTime(uint64_t t){fixtureTime=t;}
void sampleClockFixtureEvent(void* h,unsigned e){event(h,e);}
#endif
