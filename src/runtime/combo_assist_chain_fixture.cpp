// Owned interactive Win32 adapter for native-code replay. No game modules load.
#include "modern_gamepad.h"
#include <cstring>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
bool connected=true,keyboardOK=true,f10=false,space=false;
unsigned device=0,polls=0;WORD buttons=0;
struct Values {int interval,window,precision;} values{10,4,0};
std::vector<std::string> traces;
void logLine(const wchar_t* s){std::string out;while(*s)out.push_back(char(*s++));traces.push_back(out);}
void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
BOOL WINAPI keyboard(PBYTE keys){if(!keyboardOK)return FALSE;memset(keys,0,256);if(f10)keys[VK_F10]=0x80;if(space)keys[VK_SPACE]=0x80;return TRUE;}
DWORD WINAPI poll(DWORD slot,XINPUT_STATE* state){++polls;if(!connected||slot!=device)return ERROR_DEVICE_NOT_CONNECTED;*state={};state->Gamepad.wButtons=buttons;return ERROR_SUCCESS;}
int __fastcall getValue(Values* v,void*,int key){return key==0x23?v->interval:key==0x24?v->window:key==0x25?v->precision:0;}
std::string hexBytes(const BYTE* data,size_t size){std::ostringstream o;o<<std::hex<<std::setfill('0');for(size_t i=0;i<size;++i)o<<std::setw(2)<<unsigned(data[i]);return o.str();}
}
int main(int argc,char** argv){
 BYTE* image=nullptr;
 try {
  bool keyboardOnly=argc==2&&!strcmp(argv[1],"--keyboard-only");check(argc==1||keyboardOnly,"invalid argv");
  // Installation flags are explicit, independent of ambient profile settings.
  SetEnvironmentVariableW(L"MC_INPUT_PASSTHROUGH",nullptr);SetEnvironmentVariableW(L"MC_GAMEPAD_NATIVE",nullptr);SetEnvironmentVariableW(L"MC_MAP_OVERLAY",nullptr);
  image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));check(image!=nullptr,"alloc");
  auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
  auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
  image[0x2fca]=0x68;*reinterpret_cast<DWORD*>(image+0x2fcb)=reinterpret_cast<DWORD>(image+0xf1b94);
  image[0x2fcf]=0xff;image[0x2fd0]=0x15;*reinterpret_cast<DWORD*>(image+0x2fd1)=reinterpret_cast<DWORD>(image+0xbd3dc);image[0x2fd5]=0xc3;
  const BYTE battleCall[]={0xe8,0x03,0x24,0xf6,0xff,0x8b,0x45,0xfc};memcpy(image+0xa0b8d,battleCall,sizeof battleCall);
  const BYTE comboTimer[]={0x8b,0x88,0xe0,0x1d,0,0,0x83,0xc1,1};memcpy(image+0xa1711,comboTimer,sizeof comboTimer);
  *reinterpret_cast<BYTE**>(image+0xc1964)=image+0xa0b7e;
  image[0xae411]=0xc7;image[0xae412]=0x02;*reinterpret_cast<BYTE**>(image+0xae413)=image+0xc203c;
  image[0x9d424]=0xc7;image[0x9d425]=0;*reinterpret_cast<BYTE**>(image+0x9d426)=image+0xc1960;
  image[0xbdfb]=0xff;image[0xbdfc]=0x15;*reinterpret_cast<BYTE**>(image+0xbdfd)=image+0xbd42c;
  auto slot=reinterpret_cast<DWORD*>(image+0xbd3dc),messageSlot=reinterpret_cast<DWORD*>(image+0xbd42c);
  *slot=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetKeyboardState"));
  *messageSlot=reinterpret_cast<DWORD>(GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetMessageA"));
  BYTE originalKeyboard[4],originalMessage[4];memcpy(originalKeyboard,slot,4);memcpy(originalMessage,messageSlot,4);
  // __thiscall -> __fastcall jump keeps ECX=this and the callee's stack cleanup.
  image[0xb5b0e]=0xe9;*reinterpret_cast<DWORD*>(image+0xb5b0f)=reinterpret_cast<DWORD>(&getValue)-reinterpret_cast<DWORD>(image+0xb5b13);
  *reinterpret_cast<Values**>(image+0xf2428)=&values;
  DWORD old;check(VirtualProtect(image+0xb5000,0x1000,PAGE_EXECUTE_READ,&old)!=FALSE,"getter protection");
  check(VirtualProtect(image+0xbd000,0x1000,PAGE_READONLY,&old)!=FALSE,"iat protection");
  check(installModernGamepad(reinterpret_cast<HMODULE>(image),logLine,keyboardOnly),"install");
  check(memcmp(originalKeyboard,slot,4)!=0&&memcmp(originalMessage,messageSlot,4)!=0,"both IATs installed");
  BYTE scenes[2][0x1e04]{},guis[2][0x1c0]{};
  for(unsigned i=0;i<2;++i){*reinterpret_cast<BYTE**>(scenes[i])=*reinterpret_cast<BYTE**>(image+0x9d426);*reinterpret_cast<BYTE**>(scenes[i]+0x10fc)=guis[i];*reinterpret_cast<BYTE**>(guis[i])=*reinterpret_cast<BYTE**>(image+0xae413);*reinterpret_cast<BYTE**>(guis[i]+0x1bc)=scenes[i];}
  auto keys=image+0xf1b94;auto counter=reinterpret_cast<int*>(image+0xf1c9c+VK_SPACE*4);
  std::cout<<"{\"ready\":true,\"protocol\":1,\"nativeIdentityFields\":true,\"keyboardOnly\":"<<keyboardOnly<<",\"iatInstalled\":true,\"gameStarted\":false}"<<std::endl;
  std::string line;
  while(std::getline(std::cin,line)){
   if(line=="QUIT")break;
   unsigned seq,owner,mode,active,timed,tick,count,interval,window,focused,conn,dev,F10,but,phys,keyOK,nativePad;int before;unsigned precision=0;
   unsigned long long actorIdentity=0,actionIdentity=0;
   std::istringstream in(line);check(bool(in>>seq>>owner>>mode>>active>>timed>>tick>>count>>interval>>window>>focused>>conn>>dev>>F10>>but>>phys>>keyOK>>nativePad>>before),"invalid protocol fields");
   in>>std::ws;
   if(!in.eof()){
    check(bool(in>>precision),"invalid precision");in>>std::ws;
    if(!in.eof())check(bool(in>>actorIdentity>>actionIdentity),"identity fields require actor/action pair");
   }
   check(actorIdentity<=0xffffffffULL&&actionIdentity<=0xffffffffULL,"identity range");
   std::string excess;check(!(in>>excess),"excess fields");
   check(owner<=2&&active<=1&&timed<=1&&focused<=1&&conn<=1&&dev<=3&&F10<=1&&but<=65535&&phys<=1&&keyOK<=1&&nativePad<=1&&interval>=2&&interval<=300&&window>=1&&window<=interval&&precision<=window,"field range");
   BYTE* scene=owner?scenes[owner-1]:nullptr;
   if(scene){*reinterpret_cast<unsigned*>(guis[owner-1]+0x190)=mode;*reinterpret_cast<int*>(scene+0x1dc4)=active;*reinterpret_cast<int*>(scene+0x1dcc)=timed;*reinterpret_cast<unsigned*>(scene+0x1de0)=tick;*reinterpret_cast<unsigned*>(scene+0x1ddc)=count;
    // Native identities are opaque 32-bit values; this adapter never dereferences actor.
    *reinterpret_cast<DWORD*>(scene+0x40)=static_cast<DWORD>(actorIdentity);*reinterpret_cast<DWORD*>(scene+0x1744)=static_cast<DWORD>(actionIdentity);
   }
   values={int(interval),int(window),int(precision)};connected=conn!=0;device=dev;f10=F10!=0;buttons=WORD(but);space=phys!=0;keyboardOK=keyOK!=0;*counter=before;
   BYTE* outer[2]={scene,nullptr};BYTE* frame[2]={reinterpret_cast<BYTE*>(&outer[1]),image+0xa0b92};
   configureModernGamepadFixture(keyboard,poll,focused!=0);configureModernBattleFixture(nativePad!=0);
   unsigned pollsBefore=polls;size_t logStart=traces.size();BOOL ok=modernBattleKeyboardFixture(keys,frame);
   std::cout<<"{\"seq\":"<<seq<<",\"ok\":"<<(ok!=FALSE)<<",\"keysHex\":\""<<hexBytes(keys,256)<<"\",\"spaceCounterBefore\":"<<before<<",\"spaceCounterAfter\":"<<*counter<<",\"clearSpaceCounter\":"<<(before!=0&&*counter==0)<<",\"inputTraceCount\":"<<traces.size()<<",\"inputTraceDelta\":"<<(traces.size()-logStart)<<",\"polls\":"<<polls<<",\"pollsDelta\":"<<(polls-pollsBefore)<<",\"trace\":[";
   for(size_t i=logStart;i<traces.size();++i){if(i>logStart)std::cout<<',';std::cout<<'"'<<traces[i]<<'"';}std::cout<<"]}"<<std::endl;
  }
  configureModernBattleFixture(false);check(removeModernGamepad(reinterpret_cast<HMODULE>(image)),"remove");
  check(!memcmp(originalKeyboard,slot,4)&&!memcmp(originalMessage,messageSlot,4),"iat exact rollback");MEMORY_BASIC_INFORMATION info{};check(VirtualQuery(slot,&info,sizeof info)!=0&&info.Protect==PAGE_READONLY,"iat restored protection");
  std::cout<<"{\"quit\":true,\"rollback\":\"both_IATs_byte_exact\",\"iatBeforeHex\":\""<<hexBytes(originalKeyboard,4)<<hexBytes(originalMessage,4)<<"\",\"iatAfterHex\":\""<<hexBytes(reinterpret_cast<BYTE*>(slot),4)<<hexBytes(reinterpret_cast<BYTE*>(messageSlot),4)<<"\",\"pageProtection\":\"read_only\",\"gameStarted\":false}"<<std::endl;
  VirtualFree(image,0,MEM_RELEASE);return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;if(image)VirtualFree(image,0,MEM_RELEASE);return 1;}
}
