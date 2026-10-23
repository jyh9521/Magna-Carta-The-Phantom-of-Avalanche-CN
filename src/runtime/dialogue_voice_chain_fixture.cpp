// Real Miles playback joined to the production voice guard. The game image is
// mapped without imports/entry execution; only bounded native methods run.
#include "dialogue_reveal.h"
#include <mmsystem.h>
#include <wincrypt.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <vector>
#include <cstring>
namespace fs=std::filesystem;
using Tick=void(__thiscall*)(void*);
using Playing=int(__thiscall*)(void*,int);
using Event=int(__thiscall*)(void*,void*,int,int,int);
static Tick completion=nullptr;
static unsigned tickCalls=0,waitBegins=0,waitEnds=0;
static DWORD& word(BYTE* p,unsigned n){return *reinterpret_cast<DWORD*>(p+n);}
static void require(bool condition,const char* message){if(!condition)throw std::runtime_error(message);}
static std::vector<BYTE> read(const fs::path& path){std::ifstream in(path,std::ios::binary);require(bool(in),"source open");return {std::istreambuf_iterator<char>(in),std::istreambuf_iterator<char>()};}
static std::string digest(const std::vector<BYTE>& bytes){
 HCRYPTPROV provider=0;HCRYPTHASH h=0;
 require(CryptAcquireContextW(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)!=FALSE,"SHA provider");
 require(CryptCreateHash(provider,CALG_SHA_256,0,0,&h)!=FALSE,"SHA init");
 require(CryptHashData(h,bytes.data(),DWORD(bytes.size()),0)!=FALSE,"SHA update");
 BYTE value[32];DWORD count=32;require(CryptGetHashParam(h,HP_HASHVAL,value,&count,0)!=FALSE,"SHA final");CryptDestroyHash(h);CryptReleaseContext(provider,0);
 std::ostringstream out;for(auto b:value)out<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);return out.str();
}
static std::string hash(const fs::path& path){return digest(read(path));}
template<class T>static T api(HMODULE module,const char* name){auto p=GetProcAddress(module,name);if(!p)throw std::runtime_error(std::string("missing export ")+name);return reinterpret_cast<T>(p);}
static void __fastcall nativeTick(BYTE* p,void*){++tickCalls;completion(p);}
static void __fastcall noReveal(void*,void*){throw std::runtime_error("unexpected reveal callback");}
static int __fastcall noEvent(void*,void*,void*,int,int,int){throw std::runtime_error("unexpected input callback");}
static void capture(const wchar_t* line){if(wcsstr(line,L"DIALOGUE_VOICE_WAIT")){if(wcsstr(line,L"stage=begin"))++waitBegins;if(wcsstr(line,L"stage=end"))++waitEnds;}}
static DWORD dword(const std::vector<BYTE>& b,size_t p){require(p+4<=b.size(),"truncated FPB DWORD");DWORD v;memcpy(&v,b.data()+p,4);return v;}
static std::vector<BYTE> text(const std::vector<BYTE>& b,DWORD selected){
 DWORD count=dword(b,0);require(count&&count<100000,"FPB record count");size_t base=8+size_t(count)*12;require(base<=b.size(),"FPB table size");DWORD total=dword(b,4+size_t(count)*12);require(base+total==b.size(),"FPB payload total");
 size_t expected=0;std::vector<BYTE> result;bool found=false;
 for(DWORD i=0;i<count;++i){size_t pos=4+size_t(i)*12;DWORD tag=dword(b,pos),offset=dword(b,pos+4),length=dword(b,pos+8);require(length&&offset==expected&&size_t(offset)+length<=total,"FPB record range");require(b[base+offset+length-1]==0,"FPB terminator");require(!memchr(b.data()+base+offset,0,length-1),"FPB embedded zero");if(tag==selected){require(!found,"FPB duplicate selected tag");found=true;result.assign(b.begin()+base+offset,b.begin()+base+offset+length);}expected=size_t(offset)+length;}
 require(expected==total&&found&&result.size()>1,"FPB selected text");return result;
}
static void writeWord(BYTE* p,DWORD value){DWORD old=0;require(VirtualProtect(p,4,PAGE_READWRITE,&old)!=FALSE,"image slot protect");*reinterpret_cast<DWORD*>(p)=value;DWORD ignored=0;require(VirtualProtect(p,4,old,&ignored)!=FALSE,"image slot restore");}
int wmain(int argc,wchar_t** argv){
 try{
  fs::path dll,audio,engine,fpb,tracePath;std::string expectedAudio,expectedFpb;DWORD tag=0;int tail=1400;bool unguarded=false;
  for(int i=1;i<argc;++i){std::wstring option=argv[i];if(option==L"--unguarded"){unguarded=true;continue;}require(i+1<argc,"missing option value");std::wstring value=argv[++i];
   if(option==L"--dll")dll=value;else if(option==L"--audio")audio=value;else if(option==L"--native-engine")engine=value;else if(option==L"--fpb")fpb=value;else if(option==L"--tag")tag=std::stoul(value);else if(option==L"--tail-ms")tail=std::stoi(value);else if(option==L"--trace")tracePath=value;else if(option==L"--expected-audio-sha256")expectedAudio=fs::path(value).string();else if(option==L"--expected-fpb-sha256")expectedFpb=fs::path(value).string();else throw std::runtime_error("unknown option");}
  require(dll.is_absolute()&&audio.is_absolute()&&engine.is_absolute()&&fpb.is_absolute(),"absolute source paths required");require(expectedAudio.size()==64&&expectedFpb.size()==64&&tail>=1100&&tail<=10000,"expected digests and bounded tail required");
  dll=fs::canonical(dll);audio=fs::canonical(audio);engine=fs::canonical(engine);fpb=fs::canonical(fpb);
  const auto dllHash=hash(dll),audioHash=hash(audio),engineHash=hash(engine),fpbHash=hash(fpb);
  require(dllHash=="d0db426ebac97dc410b5130c9c74d19bc04151236df85b012823d6cb3d7fb87c","unsupported Miles source");require(engineHash=="7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e"||engineHash=="5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427","unsupported game image");require(audioHash==expectedAudio&&fpbHash==expectedFpb,"audio or FPB source mismatch");
  auto sourceText=text(read(fpb),tag);auto content=sourceText;content.pop_back();
  std::ofstream trace;
  if(!tracePath.empty()){require(tracePath.is_absolute(),"absolute trace path");tracePath=fs::weakly_canonical(tracePath);require(tracePath!=dll&&tracePath!=audio&&tracePath!=engine&&tracePath!=fpb&&!fs::exists(tracePath),"new trace path outside inputs required");trace.open(tracePath,std::ios::out|std::ios::binary);require(bool(trace),"trace create");trace<<"wall_ms,position_ms,total_ms,miles_status,native_playing,phase,automatic_remaining\n";}
  require(SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32|LOAD_LIBRARY_SEARCH_USER_DIRS)!=FALSE,"DLL search policy");auto redist=dll.parent_path()/L"redist";auto cookie=AddDllDirectory(redist.c_str());require(cookie!=nullptr,"redist path");
  HMODULE miles=LoadLibraryExW(dll.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32|LOAD_LIBRARY_SEARCH_USER_DIRS);require(miles!=nullptr,"Miles load");
  auto startup=api<int(__stdcall*)()>(miles,"_AIL_startup@0");auto shutdown=api<void(__stdcall*)()>(miles,"_AIL_shutdown@0");auto redistDir=api<const char*(__stdcall*)(const char*)>(miles,"_AIL_set_redist_directory@4");auto error=api<const char*(__stdcall*)()>(miles,"_AIL_last_error@0");
  auto waveOpen=api<int(__stdcall*)(void**,HWAVEOUT*,unsigned,WAVEFORMATEX*)>(miles,"_AIL_waveOutOpen@16");auto waveClose=api<void(__stdcall*)(void*)>(miles,"_AIL_waveOutClose@4");auto open=api<void*(__stdcall*)(void*,const char*,int)>(miles,"_AIL_open_stream@12");auto close=api<void(__stdcall*)(void*)>(miles,"_AIL_close_stream@4");auto status=api<int(__stdcall*)(void*)>(miles,"_AIL_stream_status@4");auto position=api<void(__stdcall*)(void*,int*,int*)>(miles,"_AIL_stream_ms_position@12");auto seek=api<void(__stdcall*)(void*,int)>(miles,"_AIL_set_stream_ms_position@8");auto volume=api<void(__stdcall*)(void*,int)>(miles,"_AIL_set_stream_volume@8");
  redistDir(redist.string().c_str());require(startup()!=0,"Miles startup");WAVEFORMATEX format{};format.wFormatTag=WAVE_FORMAT_PCM;format.nChannels=2;format.nSamplesPerSec=44100;format.wBitsPerSample=16;format.nBlockAlign=4;format.nAvgBytesPerSec=176400;void* driver=nullptr;HWAVEOUT wave=nullptr;if(waveOpen(&driver,&wave,WAVE_MAPPER,&format))throw std::runtime_error(std::string("waveOutOpen ")+error());void* stream=open(driver,audio.string().c_str(),0);if(!stream)throw std::runtime_error(std::string("open stream ")+error());
  int total=0,current=0;position(stream,&total,&current);require(total>=tail+1000&&total<1800000,"long original voice duration");volume(stream,0);
  HMODULE mapped=LoadLibraryExW(engine.c_str(),nullptr,DONT_RESOLVE_DLL_REFERENCES);require(mapped!=nullptr,"image map without entry");auto base=reinterpret_cast<BYTE*>(mapped);require(base==reinterpret_cast<BYTE*>(0x52000000),"preferred native image base");
  struct Saved {BYTE* slot;DWORD value;};std::vector<Saved> imports;
  for(const auto& binding:std::vector<std::pair<unsigned,const char*>>{{0xbd4d0,"_AIL_auto_service_stream@8"},{0xbd4d4,"_AIL_start_stream@4"},{0xbd4d8,"_AIL_set_stream_loop_count@8"},{0xbd4e4,"_AIL_set_stream_processor@12"},{0xbd4f4,"_AIL_stream_status@4"}}){auto slot=base+binding.first;imports.push_back({slot,*reinterpret_cast<DWORD*>(slot)});writeWord(slot,reinterpret_cast<DWORD>(api<void*>(miles,binding.second)));}
  BYTE manager[0x470]{};DWORD slots[3]{};slots[1]=reinterpret_cast<DWORD>(stream);word(manager,0x54)=reinterpret_cast<DWORD>(slots);word(manager,0x58)=1;word(manager,0x46c)=18;DWORD priorManager=word(base,0xf2204);writeWord(base+0xf2204,reinterpret_cast<DWORD>(manager));
  BYTE resource[0x38]{},voice[0x134]{},dialogue[0x200]{},baseline[0x200]{};word(resource,4)=0;word(resource,0xc)=18;word(voice,0)=reinterpret_cast<DWORD>(base+0xbe620);word(voice,0x120)=reinterpret_cast<DWORD>(resource);word(voice,0x12c)=1;word(dialogue,0x190)=3;word(dialogue,0x194)=1;word(dialogue,0x1e0)=reinterpret_cast<DWORD>(sourceText.data());word(dialogue,0x1d0)=0;word(baseline,0x190)=3;word(baseline,0x194)=1;
  completion=reinterpret_cast<Tick>(base+0x5c13e);auto nativeVoice=reinterpret_cast<Tick>(base+0x49ecb);auto nativePlaying=reinterpret_cast<Playing>(base+0x6329);DWORD originalSlots[]={word(base,0xbfcf0),word(base,0xbfd10),word(base,0xbfee8),word(base,0xbff08)};BYTE originalCall[5];memcpy(originalCall,base+0x5afee,5);configureDialogueRevealFixture(reinterpret_cast<Event>(&noEvent),reinterpret_cast<Tick>(&nativeTick),reinterpret_cast<Tick>(&noReveal));configureDialogueVoiceFixture(nativeVoice,nativePlaying,manager);require(installDialogueReveal(mapped,capture),"production hook install");auto guardedTick=reinterpret_cast<Tick>(word(base,0xbfcf0));startDialogueVoiceFixture(voice,dialogue,(total/1000)*30);require(word(voice,0x124)==2&&nativePlaying(manager,0)==1&&status(stream)==4,"native start must play real stream");seek(stream,total-tail);
  completion(baseline);require(word(baseline,0x190)==6&&status(stream)==4,"baseline should expire while original audio plays");std::cout<<"BASELINE native5c13e_phase=6 miles_status=4 voice_still_playing=true\n"<<std::flush;
  if(unguarded){completion(dialogue);std::cout<<"UNGUARDED phase="<<word(dialogue,0x190)<<" miles_status="<<status(stream)<<std::endl;require(word(dialogue,0x190)==3,"autoplay must wait for actual original Miles stream");}
  const auto begin=GetTickCount64();unsigned held=0,progress=0;int previous=-1;
  while(GetTickCount64()-begin<ULONGLONG(tail)+12000){int before=status(stream);int playing=nativePlaying(manager,0);guardedTick(dialogue);position(stream,&total,&current);int after=status(stream);if(trace)trace<<(GetTickCount64()-begin)<<','<<current<<','<<total<<','<<after<<','<<playing<<','<<word(dialogue,0x190)<<','<<word(dialogue,0x1d0)<<'\n';if(before==4&&after==4){require(word(dialogue,0x190)==3&&word(dialogue,0x1d0)==0,"production guard advanced while actual voice playing");++held;if(current>previous)++progress;previous=current;}if(word(dialogue,0x190)==6){require(after==2,"dialogue must end at actual stream completion");break;}require(after==4||after==2,"unexpected Miles stream status");Sleep(20);}
  const auto wall=GetTickCount64()-begin;require(word(dialogue,0x190)==6&&status(stream)==2&&held>20&&progress>10&&wall>=700&&waitBegins==1&&waitEnds==1,"actual playback wait/completion assertion");require(removeDialogueReveal(mapped),"production hook rollback");require(word(base,0xbfcf0)==originalSlots[0]&&word(base,0xbfd10)==originalSlots[1]&&word(base,0xbfee8)==originalSlots[2]&&word(base,0xbff08)==originalSlots[3]&&!memcmp(base+0x5afee,originalCall,5),"exact production code and slot rollback");writeWord(base+0xf2204,priorManager);for(const auto& saved:imports){writeWord(saved.slot,saved.value);require(*reinterpret_cast<DWORD*>(saved.slot)==saved.value,"exact IAT rollback");}require(word(base,0xf2204)==priorManager,"exact manager rollback");FreeLibrary(mapped);close(stream);waveClose(driver);shutdown();FreeLibrary(miles);RemoveDllDirectory(cookie);if(trace){trace.flush();require(bool(trace),"trace flush");trace.close();std::cout<<"TRACE_SHA256 "<<hash(tracePath)<<'\n';}require(hash(dll)==dllHash&&hash(audio)==audioHash&&hash(engine)==engineHash&&hash(fpb)==fpbHash,"source hashes unchanged");std::cout<<"MILES_SHA256 "<<dllHash<<"\nENGINE_SHA256 "<<engineHash<<"\nAUDIO_SHA256 "<<audioHash<<"\nFPB_SHA256 "<<fpbHash<<"\nTEXT_SHA256 "<<digest(content)<<'\n';std::cout<<"DIALOGUE_VOICE_CHAIN PASS native49ecb=start native6329=status production_hook=held native5c13e=completion status=4_to_2 phase=3_to_6 held_ticks="<<held<<" tick_calls="<<tickCalls<<" progress_samples="<<progress<<" wall_ms="<<wall<<" total_ms="<<total<<" tail_ms="<<tail<<" voice_wait_logs=begin_end rollback=exact source_unchanged=true volume=0 game_entry_executed=false game_started=false"<<std::endl;return 0;
 }catch(const std::exception& error){std::cerr<<"DIALOGUE_VOICE_CHAIN FAIL "<<error.what()<<std::endl;return 1;}
}
