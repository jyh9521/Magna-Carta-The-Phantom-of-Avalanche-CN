// Standalone source-locked Miles playback. Optional native query maps MCAlpha
// with DONT_RESOLVE_DLL_REFERENCES; no game entry point executes.
// WIN32_LEAN_AND_MEAN is defined by the runtime build.
#include <windows.h>
#include <mmsystem.h>
#include <wincrypt.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <stdexcept>
#include <string>
namespace fs=std::filesystem;
static std::string hash(const fs::path& p){
 HCRYPTPROV provider=0;HCRYPTHASH h=0;
 if(!CryptAcquireContextW(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)||!CryptCreateHash(provider,CALG_SHA_256,0,0,&h))throw std::runtime_error("SHA256 init");
 std::ifstream in(p,std::ios::binary);if(!in)throw std::runtime_error("file open");char buffer[65536];
 while(in.read(buffer,sizeof(buffer))||in.gcount())if(!CryptHashData(h,reinterpret_cast<BYTE*>(buffer),DWORD(in.gcount()),0))throw std::runtime_error("SHA256 update");
 BYTE bytes[32];DWORD count=32;if(!CryptGetHashParam(h,HP_HASHVAL,bytes,&count,0))throw std::runtime_error("SHA256 final");
 CryptDestroyHash(h);CryptReleaseContext(provider,0);std::ostringstream out;for(BYTE b:bytes)out<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);return out.str();
}
template<class T>static T api(HMODULE m,const char* name){auto p=GetProcAddress(m,name);if(!p)throw std::runtime_error(std::string("export missing ")+name);return reinterpret_cast<T>(p);}
struct TraceFile {
 HANDLE handle=INVALID_HANDLE_VALUE;
 ~TraceFile(){if(handle!=INVALID_HANDLE_VALUE)CloseHandle(handle);}
 void write(const std::string& data){DWORD written=0;if(!WriteFile(handle,data.data(),DWORD(data.size()),&written,nullptr)||written!=data.size())throw std::runtime_error("trace write");}
 void close(){if(handle!=INVALID_HANDLE_VALUE){if(!FlushFileBuffers(handle))throw std::runtime_error("trace flush");CloseHandle(handle);handle=INVALID_HANDLE_VALUE;}}
};
int wmain(int argc,wchar_t** argv){
 try{
  fs::path dll,audio,nativeEngine,tracePath;TraceFile trace;int seek=0;std::string expected;
  for(int i=1;i<argc;++i){std::wstring a=argv[i];if(i+1>=argc)throw std::runtime_error("missing option value");std::wstring v=argv[++i];
   if(a==L"--trace")tracePath=v;else if(a==L"--native-engine")nativeEngine=v;else if(a==L"--dll")dll=v;else if(a==L"--audio")audio=v;else if(a==L"--seek-ms")seek=std::stoi(v);else if(a==L"--expected-audio-sha256")expected=fs::path(v).string();else throw std::runtime_error("unknown option");}
  if(!dll.is_absolute()||!audio.is_absolute()||expected.size()!=64||seek<0)throw std::runtime_error("require absolute --dll/--audio and --expected-audio-sha256; optional --seek-ms");
  dll=fs::canonical(dll);audio=fs::canonical(audio);
  const auto dllHash=hash(dll),audioHash=hash(audio);
  if(dllHash!="d0db426ebac97dc410b5130c9c74d19bc04151236df85b012823d6cb3d7fb87c")throw std::runtime_error("unsupported Mss32 SHA256");
  if(audioHash!=expected)throw std::runtime_error("audio SHA256 mismatch");
  wchar_t own[MAX_PATH];if(!GetModuleFileNameW(nullptr,own,MAX_PATH))throw std::runtime_error("caller path");
  if(!tracePath.empty()){
   if(!tracePath.is_absolute())throw std::runtime_error("trace requires absolute path");
   tracePath=fs::weakly_canonical(tracePath);
   if(tracePath==dll||tracePath==audio||tracePath==fs::canonical(own)||(!nativeEngine.empty()&&tracePath==fs::weakly_canonical(nativeEngine)))throw std::runtime_error("trace conflicts with input");
   trace.handle=CreateFileW(tracePath.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
   if(trace.handle==INVALID_HANDLE_VALUE)throw std::runtime_error("trace create-new failed; existing paths are preserved");
   trace.write("wall_ms,position_ms,total_ms,status,native_playing\n");
  }
  std::cout<<"CALLER_SHA256 "<<hash(own)<<"\nMILES_SHA256 "<<dllHash<<"\nAUDIO_SHA256 "<<audioHash<<std::endl;
  if(!SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32|LOAD_LIBRARY_SEARCH_USER_DIRS))throw std::runtime_error("DLL search policy");
  auto redist=dll.parent_path()/L"redist";auto cookie=AddDllDirectory(redist.c_str());if(!cookie)throw std::runtime_error("redist search path");
  HMODULE module=LoadLibraryExW(dll.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32|LOAD_LIBRARY_SEARCH_USER_DIRS);if(!module)throw std::runtime_error("Miles load");
  auto startup=api<int(__stdcall*)()>(module,"_AIL_startup@0");auto shutdown=api<void(__stdcall*)()>(module,"_AIL_shutdown@0");
  auto redistDir=api<const char*(__stdcall*)(const char*)>(module,"_AIL_set_redist_directory@4");
  auto error=api<const char*(__stdcall*)()>(module,"_AIL_last_error@0");
  auto waveOpen=api<int(__stdcall*)(void**,HWAVEOUT*,unsigned,WAVEFORMATEX*)>(module,"_AIL_waveOutOpen@16");
  auto waveClose=api<void(__stdcall*)(void*)>(module,"_AIL_waveOutClose@4");
  auto open=api<void*(__stdcall*)(void*,const char*,int)>(module,"_AIL_open_stream@12");auto close=api<void(__stdcall*)(void*)>(module,"_AIL_close_stream@4");
  auto start=api<void(__stdcall*)(void*)>(module,"_AIL_start_stream@4");auto status=api<int(__stdcall*)(void*)>(module,"_AIL_stream_status@4");
  auto position=api<void(__stdcall*)(void*,int*,int*)>(module,"_AIL_stream_ms_position@12");
  auto setPosition=api<void(__stdcall*)(void*,int)>(module,"_AIL_set_stream_ms_position@8");
  auto volume=api<void(__stdcall*)(void*,int)>(module,"_AIL_set_stream_volume@8");
  const std::string redistPath=redist.string();redistDir(redistPath.c_str());
  if(!startup())throw std::runtime_error(std::string("Miles startup ")+error());
  WAVEFORMATEX format{};format.wFormatTag=WAVE_FORMAT_PCM;format.nChannels=2;format.nSamplesPerSec=44100;format.wBitsPerSample=16;format.nBlockAlign=4;format.nAvgBytesPerSec=176400;
  void* driver=nullptr;HWAVEOUT wave=nullptr;if(waveOpen(&driver,&wave,WAVE_MAPPER,&format)!=0)throw std::runtime_error(std::string("waveOutOpen ")+error());
  const std::string audioPath=audio.string();void* stream=open(driver,audioPath.c_str(),0);if(!stream)throw std::runtime_error(std::string("open_stream ")+error());
  int total=0,current=0;position(stream,&total,&current);if(total<1200||total>1800000||seek>total-1100)throw std::runtime_error("invalid duration or seek; require >=1100ms remaining");
  HMODULE native=nullptr;bool(__thiscall* nativePlaying)(void*,int)=nullptr;BYTE manager[0x5c]{};DWORD slots[3]{};unsigned nativeChecks=0;
  if(!nativeEngine.empty()){
   if(!nativeEngine.is_absolute())throw std::runtime_error("native engine requires absolute path");
   const auto digest=hash(nativeEngine);if(digest!="5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427"&&digest!="7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e")throw std::runtime_error("unsupported native engine SHA256");
   native=LoadLibraryExW(nativeEngine.c_str(),nullptr,DONT_RESOLVE_DLL_REFERENCES);if(!native)throw std::runtime_error("read-only native image mapping");
   auto base=reinterpret_cast<BYTE*>(native);if(base!=reinterpret_cast<BYTE*>(0x52000000))throw std::runtime_error("native preferred base unavailable");
   DWORD protect=0;if(!VirtualProtect(base+0xbd4f4,4,PAGE_READWRITE,&protect))throw std::runtime_error("native status IAT protect");
   *reinterpret_cast<DWORD*>(base+0xbd4f4)=reinterpret_cast<DWORD>(status);DWORD ignored=0;VirtualProtect(base+0xbd4f4,4,protect,&ignored);
   slots[1]=reinterpret_cast<DWORD>(stream);*reinterpret_cast<DWORD*>(manager+0x54)=reinterpret_cast<DWORD>(slots);*reinterpret_cast<DWORD*>(manager+0x58)=1;
   nativePlaying=reinterpret_cast<bool(__thiscall*)(void*,int)>(base+0x6329);
   std::cout<<"NATIVE_ENGINE_SHA256 "<<digest<<" entry_executed=false imports_bound=AIL_stream_status slot_handle_matches=true"<<std::endl;
  }
  volume(stream,0);start(stream);if(seek)setPosition(stream,seek);
  bool playing=false,done=false;int first=-1,last=-1,lastStatus=-1,advances=0;const auto begin=GetTickCount64();
  while(GetTickCount64()-begin<ULONGLONG(total-seek)+15000){
   const int state=status(stream);position(stream,&total,&current);
   int observed=-1;if(nativePlaying){observed=nativePlaying(manager,0)?1:0;++nativeChecks;if(observed!=(state==4)&&observed!=(status(stream)==4))throw std::runtime_error("native6329/direct stream status disagreement");}
   if(trace.handle!=INVALID_HANDLE_VALUE){std::ostringstream row;row<<(GetTickCount64()-begin)<<','<<current<<','<<total<<','<<state<<','<<observed<<'\n';trace.write(row.str());}
   if(state!=lastStatus){std::cout<<"STATUS "<<state<<" total_ms="<<total<<" current_ms="<<current<<" wall_ms="<<(GetTickCount64()-begin)<<std::endl;lastStatus=state;}
   if(state==4){playing=true;if(first<0)first=current;if(current>last)++advances;last=current;}
   if(playing&&state==2){done=true;break;}if(state!=4&&state!=2)throw std::runtime_error("unexpected stream status");Sleep(20);
  }
  if(!native&&GetModuleHandleW(L"MCAlpha.dll"))throw std::runtime_error("unexpected game module loaded");
  const auto wall=GetTickCount64()-begin;if(native)FreeLibrary(native);close(stream);waveClose(driver);shutdown();FreeLibrary(module);RemoveDllDirectory(cookie);
  trace.close();if(!tracePath.empty())std::cout<<"TRACE_SHA256 "<<hash(tracePath)<<std::endl;
  if(!playing||!done||wall<900||last-first<800||advances<10)throw std::runtime_error("natural playback completion/progress assertion");
  std::cout<<"DIALOGUE_AUDIO PASS status=4_to_2 natural_end=true first_ms="<<first<<" last_playing_ms="<<last<<" advances="<<advances<<" wall_ms="<<wall<<" seek_ms="<<seek<<" native6329_checks="<<nativeChecks<<" volume=0 game_started=false"<<std::endl;return 0;
 }catch(const std::exception& e){std::cerr<<"DIALOGUE_AUDIO FAIL "<<e.what()<<std::endl;return 1;}
}
