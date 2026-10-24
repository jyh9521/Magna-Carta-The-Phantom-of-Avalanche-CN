// Bounded native audio initialization and allocation, real shipped Miles.
// MCAlpha is mapped without imports/entry execution. Filter enumeration alone
// and the WinMM digital-driver bootstrap are explicit owned boundaries. No game process, resource or sound plays.
#include "audio_provider_policy.h"
#include <wincrypt.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <iostream>
#include <vector>
#include <stdexcept>
#include <cstring>
#include <mmsystem.h>
namespace fs=std::filesystem;
static const char* phase="start";
static LONG WINAPI fault(EXCEPTION_POINTERS* e){DWORD stack[4]{};SIZE_T n=0;ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(e->ContextRecord->Esp),stack,sizeof(stack),&n);fprintf(stderr,"POOL_FAULT address=%p stage=%s stack=%08lx,%08lx,%08lx,%08lx\n",e->ExceptionRecord->ExceptionAddress,phase,stack[0],stack[1],stack[2],stack[3]);fflush(stderr);return EXCEPTION_EXECUTE_HANDLER;}

static void require(bool yes,const char* what){if(!yes)throw std::runtime_error(what);}
static std::string digest(const fs::path& path){
 HCRYPTPROV p=0;HCRYPTHASH h=0;require(CryptAcquireContextW(&p,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(p,CALG_SHA_256,0,0,&h),"hash init");
 std::ifstream in(path,std::ios::binary);require(bool(in),"input open");char b[65536];while(in.read(b,sizeof(b))||in.gcount())require(CryptHashData(h,reinterpret_cast<BYTE*>(b),DWORD(in.gcount()),0),"hash update");
 BYTE out[32];DWORD n=32;require(CryptGetHashParam(h,HP_HASHVAL,out,&n,0),"hash final");CryptDestroyHash(h);CryptReleaseContext(p,0);
 std::ostringstream s;for(BYTE c:out)s<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c);return s.str();
}
template<class T>T api(HMODULE m,const char* name){auto p=GetProcAddress(m,name);require(p!=nullptr,name);return reinterpret_cast<T>(p);}
static DWORD& word(void* p,size_t n){return *reinterpret_cast<DWORD*>(static_cast<BYTE*>(p)+n);}
static int __stdcall noFilters(void*,void*,void*){return 0;}
static bool policyFallback=false;
static void trace(const wchar_t* s){if(wcsstr(s,L"AUDIO_PROVIDER_POLICY_FALLBACK"))policyFallback=true;std::wcout<<s<<L'\n';}
using Open=int(__stdcall*)(DWORD);
using WaveOpen=int(__stdcall*)(void**,HWAVEOUT*,unsigned,WAVEFORMATEX*);
static WaveOpen waveOpen=nullptr;static int(__stdcall* preference)(unsigned,int)=nullptr;
static void* __stdcall ownedDigitalBootstrap(unsigned rate,int bits,int channels,unsigned flags){
 // No game HWND exists in this bounded replay. Use the real SDK's WinMM
 // digital driver rather than its window-dependent DirectSound bootstrap.
 if(rate!=44100||bits!=16||channels!=2||flags!=0)ExitProcess(7);
 preference(15,1);WAVEFORMATEX f{};f.wFormatTag=WAVE_FORMAT_PCM;f.nChannels=WORD(channels);f.nSamplesPerSec=rate;f.wBitsPerSample=WORD(bits);f.nBlockAlign=WORD(channels*bits/8);f.nAvgBytesPerSec=rate*f.nBlockAlign;
 void* driver=nullptr;HWAVEOUT out=nullptr;if(waveOpen(&driver,&out,WAVE_MAPPER,&f)!=0)return nullptr;return driver;
}
static Open realOpen=nullptr;static DWORD preferred=0;static unsigned rejected=0;
static int __stdcall rejectPreferred(DWORD p){if(p==preferred){++rejected;return 8;}return realOpen(p);}
static void bind(BYTE* image,HMODULE miles,bool fallback){
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+reinterpret_cast<IMAGE_DOS_HEADER*>(image)->e_lfanew);
 auto d=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(image+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
 for(;d->Name;++d){auto name=reinterpret_cast<const char*>(image+d->Name);HMODULE module=nullptr;
  if(!_stricmp(name,"mss32.dll"))module=miles;
  else if(!_stricmp(name,"MSVCRT.dll")||!_stricmp(name,"KERNEL32.dll"))module=LoadLibraryExA(name,nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
  if(!module)continue;
  auto names=reinterpret_cast<IMAGE_THUNK_DATA32*>(image+d->OriginalFirstThunk),slots=reinterpret_cast<IMAGE_THUNK_DATA32*>(image+d->FirstThunk);
  for(;names->u1.AddressOfData;++names,++slots){require(!IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal),"ordinal import");auto symbol=reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(image+names->u1.AddressOfData)->Name;
   auto target=GetProcAddress(module,reinterpret_cast<char*>(symbol));require(target!=nullptr,"native import");
   if(!strcmp(reinterpret_cast<char*>(symbol),"_AIL_open_digital_driver@16"))target=reinterpret_cast<FARPROC>(&ownedDigitalBootstrap);
   if(!strcmp(reinterpret_cast<char*>(symbol),"_AIL_enumerate_filters@12"))target=reinterpret_cast<FARPROC>(&noFilters);
   if(fallback&&!strcmp(reinterpret_cast<char*>(symbol),"_AIL_open_3D_provider@4"))target=reinterpret_cast<FARPROC>(&rejectPreferred);
   DWORD old;require(VirtualProtect(slots,4,PAGE_READWRITE,&old),"IAT protection");slots->u1.Function=DWORD(target);DWORD unused;require(VirtualProtect(slots,4,old,&unused),"IAT restore");
  }
 }
}
int wmain(int argc,wchar_t** argv){
 SetUnhandledExceptionFilter(&fault);
 try{
  require(argc==4,"usage: native_audio_pool_fixture engine.dll mss32.dll --baseline|--modified|--rollback|--fallback");
  auto enginePath=fs::canonical(argv[1]),milesPath=fs::canonical(argv[2]);std::wstring mode=argv[3];
  require(mode==L"--baseline"||mode==L"--modified"||mode==L"--rollback"||mode==L"--fallback","mode");
  require(digest(enginePath)=="7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e","engine source hash");
  require(digest(milesPath)=="d0db426ebac97dc410b5130c9c74d19bc04151236df85b012823d6cb3d7fb87c","Miles source hash");
  require(SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32|LOAD_LIBRARY_SEARCH_USER_DIRS),"search policy");
  auto redist=milesPath.parent_path()/L"redist";require(AddDllDirectory(redist.c_str())!=nullptr,"redist path");
  auto miles=LoadLibraryExW(milesPath.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_USER_DIRS|LOAD_LIBRARY_SEARCH_SYSTEM32);require(miles!=nullptr,"Miles load");
  auto image=reinterpret_cast<BYTE*>(LoadLibraryExW(enginePath.c_str(),nullptr,DONT_RESOLVE_DLL_REFERENCES));require(image!=nullptr,"native no-entry mapping");
  waveOpen=api<WaveOpen>(miles,"_AIL_waveOutOpen@16");preference=api<int(__stdcall*)(unsigned,int)>(miles,"_AIL_set_preference@8");realOpen=api<Open>(miles,"_AIL_open_3D_provider@4");bind(image,miles,mode==L"--fallback");
  const std::string redistPath=redist.string();api<const char*(__stdcall*)(const char*)>(miles,"_AIL_set_redist_directory@4")(redistPath.c_str());
  require(api<int(__stdcall*)()>(miles,"_AIL_startup@0")()!=0,"Miles startup");
  // Keep offline 2D driver initialization on WinMM; 3D provider policy below stays native.
  api<int(__stdcall*)(unsigned,int)>(miles,"_AIL_set_preference@8")(15,1);
  int cursor=0;DWORD provider;const char* name;
  while(api<int(__stdcall*)(int*,DWORD*,const char**)>(miles,"_AIL_enumerate_3D_providers@12")(&cursor,&provider,&name))
   if(!strcmp(name,"DirectSound3D 7+ Software - Pan and Volume"))preferred=provider;
  BYTE original[6];memcpy(original,image+0x6875,6);
  require(!installAudioProviderPolicy(nullptr,trace),"null image rejected");
  DWORD guardProtect=0,unusedProtect=0;
  require(VirtualProtect(image+0x6875,6,PAGE_EXECUTE_READWRITE,&guardProtect),"guard test protection");
  image[0x6875]=0xcc;
  require(!installAudioProviderPolicy(reinterpret_cast<HMODULE>(image),trace)&&image[0x6875]==0xcc,"unknown call site rejected unchanged");
  memcpy(image+0x6875,original,6);
  require(VirtualProtect(image+0x6875,6,guardProtect,&unusedProtect),"guard restore");
  if(mode!=L"--baseline"){
   require(installAudioProviderPolicy(reinterpret_cast<HMODULE>(image),trace),"install");
   require(installAudioProviderPolicy(reinterpret_cast<HMODULE>(image),trace),"idempotence");
   if(mode==L"--rollback")require(removeAudioProviderPolicy(reinterpret_cast<HMODULE>(image))&&!memcmp(original,image+0x6875,6),"isolated byte rollback");
  }
  std::vector<BYTE> manager(0x400874);
  word(manager.data(),0x40)=16;word(manager.data(),0x44)=2;word(manager.data(),0x48)=44100;
  using Init=void(__thiscall*)(void*);using Allocate=int(__thiscall*)(void*);using Release=void(__thiscall*)(void*,int);
  phase="native_6685";reinterpret_cast<Init>(image+0x6685)(manager.data());phase="native_pools";
  reinterpret_cast<Init>(image+0x52ae)(manager.data());
  reinterpret_cast<Init>(image+0x509a)(manager.data());
  reinterpret_cast<Init>(image+0x51de)(manager.data());
  // Real non-playing streams coexist with the native positional/2D pools.
  wchar_t tempDir[MAX_PATH]{},tempName[MAX_PATH]{};
  require(GetTempPathW(MAX_PATH,tempDir)&&GetTempFileNameW(tempDir,L"map",0,tempName),"owned WAV path");
  std::vector<BYTE> wave(44+8192);
  memcpy(wave.data(),"RIFF",4);word(wave.data(),4)=DWORD(wave.size()-8);memcpy(wave.data()+8,"WAVEfmt ",8);
  word(wave.data(),16)=16;*reinterpret_cast<WORD*>(wave.data()+20)=1;*reinterpret_cast<WORD*>(wave.data()+22)=1;
  word(wave.data(),24)=44100;word(wave.data(),28)=88200;*reinterpret_cast<WORD*>(wave.data()+32)=2;*reinterpret_cast<WORD*>(wave.data()+34)=16;
  memcpy(wave.data()+36,"data",4);word(wave.data(),40)=8192;
  {std::ofstream out(fs::path(tempName),std::ios::binary);out.write(reinterpret_cast<const char*>(wave.data()),wave.size());require(bool(out),"owned WAV write");}
  auto openStream=api<void*(__stdcall*)(void*,const char*,int)>(miles,"_AIL_open_stream@12");
  auto closeStream=api<void(__stdcall*)(void*)>(miles,"_AIL_close_stream@4");
  auto driver=reinterpret_cast<void*>(word(manager.data(),0x24));auto ownedPath=fs::path(tempName).string();
  void* stream1=openStream(driver,ownedPath.c_str(),0);void* stream2=openStream(driver,ownedPath.c_str(),0);
  require(stream1&&stream2,"two owned silent streams coexist");
  unsigned capacity=word(manager.data(),0x68),requests=16,accepted=0;
  for(unsigned i=0;i<requests;++i)if(reinterpret_cast<Allocate>(image+0x5498)(manager.data())>=0)++accepted;
  for(unsigned i=0;i<accepted;++i)reinterpret_cast<Release>(image+0x54f9)(manager.data(),i);
  unsigned full=0;while(full<=capacity&&reinterpret_cast<Allocate>(image+0x5498)(manager.data())>=0)++full;
  require(full==capacity,"native exhaustion bound");
  auto release3D=api<void(__stdcall*)(void*)>(miles,"_AIL_release_3D_sample_handle@4");
  closeStream(stream1);closeStream(stream2);require(DeleteFileW(tempName),"owned WAV cleanup");
  auto release2D=api<void(__stdcall*)(void*)>(miles,"_AIL_release_sample_handle@4");
  for(unsigned i=0;i<capacity;++i)release3D(reinterpret_cast<void*>(word(reinterpret_cast<void*>(word(manager.data(),0x64)),i*12+8)));
  for(unsigned i=0;i<word(manager.data(),0x60);++i)release2D(reinterpret_cast<void*>(word(reinterpret_cast<void*>(word(manager.data(),0x5c)),i*12+8)));
  auto nativeDelete=reinterpret_cast<void(__cdecl*)(void*)>(image+0xb8a86);
  for(unsigned offset:{0x64,0x5c,0x54})nativeDelete(reinterpret_cast<void*>(word(manager.data(),offset)));
  api<void(__stdcall*)(DWORD)>(miles,"_AIL_close_3D_provider@4")(word(manager.data(),0x400870));
  api<void(__stdcall*)(void*)>(miles,"_AIL_close_digital_driver@4")(reinterpret_cast<void*>(word(manager.data(),0x24)));
  api<void(__stdcall*)()>(miles,"_AIL_shutdown@0")();
  if(mode!=L"--baseline"&&mode!=L"--rollback")require(removeAudioProviderPolicy(reinterpret_cast<HMODULE>(image)),"remove");
  require(!memcmp(original,image+0x6875,6),"final byte rollback");
  bool modified=mode==L"--modified";
  require(modified&&!policyFallback?(capacity==56&&accepted==16):(capacity==8&&accepted==8),"unexpected backend or native allocation result");
  if(mode==L"--fallback")require(rejected==1,"fallback attempted once");
  std::wcout<<L"NATIVE_AUDIO_POOL "<<(mode==L"--baseline"?L"FAIL":L"PASS")<<L" mode="<<mode<<L" capacity="<<capacity<<L" requests="<<requests<<L" accepted="<<accepted<<L" dropped="<<requests-accepted
   <<L" preferred_available="<<(modified&&!policyFallback?L"true":L"false")<<L" digital_bootstrap=owned_winmm exhaustion=bounded release=reusable streams=2 guards=pass rollback=byte_exact filters=owned_boundary playback_started=false game_started=false\n";
  FreeLibrary(reinterpret_cast<HMODULE>(image));FreeLibrary(miles);return mode==L"--baseline"?1:0;
 }catch(const std::exception& e){std::cerr<<"NATIVE_AUDIO_POOL ERROR "<<e.what()<<'\n';return 2;}
}
