#include "contact_audio_trace.h"
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
struct Vec {float x,y,z;};
using Contact=Vec*(__thiscall*)(void*,Vec*,void*,const Vec*,int,Vec,Vec*,Vec*,float,unsigned);
using Start=void(__thiscall*)(void*);
static BYTE* image;static BYTE scene[0x1748],actor[0x340],sound[0x13c],resource[8],manager[0x6c],slots[36];
static BYTE fades[4][0x1ac],boxes[4][0x1c8],movers[4][0x154];
static std::vector<std::wstring> lines;static int checks=0,contactCalls=0,soundCalls=0;
static bool allocationFails=false;
void require(bool ok,const char* why){++checks;if(!ok){std::fprintf(stderr,"CONTACT_AUDIO_TRACE FAIL %s\n",why);ExitProcess(1);}}
void logger(const wchar_t* s){lines.emplace_back(s);SetLastError(0xdead);}
unsigned& word(void* p,unsigned o){return *reinterpret_cast<unsigned*>(static_cast<BYTE*>(p)+o);}
bool contains(const wchar_t* s){for(auto& l:lines)if(l.find(s)!=std::wstring::npos)return true;return false;}
int count(const wchar_t* prefix){int n=0;for(auto& l:lines)if(l.find(prefix)==0)++n;return n;}
Vec* __fastcall nativeContact(void* value,void*,Vec* out,void* a,const Vec* offsets,int n,Vec p,Vec* bounce,Vec* v,float elasticity,unsigned extra){
 require(GetLastError()==0x2468,"incoming collision last error unchanged");
 ++contactCalls;require(value==scene&&a==actor&&offsets==nullptr&&n==0,"collision identity/offset ABI");
 require(p.x==1&&p.y==2&&p.z==3&&elasticity==.75f&&extra==0x31415926,"collision vector/scalar ABI");
 *out={v->x*.5f,v->y*.5f,v->z*.5f};*bounce={4,5,6};*v={7,8,9};SetLastError(0x1234);return out;
}
void __fastcall nativeStart(void* p,void*){require(GetLastError()==0x1357,"incoming sound last error unchanged");++soundCalls;require(p==sound,"sound thiscall ABI");word(p,0x128)=allocationFails?0:2;word(p,0x120)=allocationFails?0xffffffff:1;SetLastError(0x5678);}
void jmp(BYTE* p,void* to){p[0]=0xe9;word(p,1)=DWORD(to)-DWORD(p+5);}
void rw(unsigned r,const void* b,unsigned n){DWORD old;require(VirtualProtect(image+r,n,PAGE_EXECUTE_READWRITE,&old)!=0,"fixture writable");memcpy(image+r,b,n);DWORD ignored;require(VirtualProtect(image+r,n,old,&ignored)!=0,"fixture protection restored");FlushInstructionCache(GetCurrentProcess(),image+r,n);}
void callContact(){Vec out{},bounce{},v{10,20,30};auto f=reinterpret_cast<Contact>(word(image,0xc1304));
 DWORD stackBefore;__asm mov stackBefore,esp
 SetLastError(0x2468);
 auto result=f(scene,&out,actor,nullptr,0,{1,2,3},&bounce,&v,.75f,0x31415926);
 DWORD after;__asm mov after,esp
 require(stackBefore==after,"collision stack exact");require(result==&out&&out.x==5&&out.y==10&&out.z==15&&v.x==7&&v.z==9&&bounce.x==4&&bounce.z==6,"native output pointer and mutations unchanged");require(GetLastError()==0x1234,"contact last error unchanged");
}
void callSound(){word(sound,0x128)=0;word(sound,0x120)=0xffffffff;SetLastError(0x1357);reinterpret_cast<Start>(image+0x48e54)(sound);
 require(word(sound,0x128)==(allocationFails?0u:2u)&&word(sound,0x120)==(allocationFails?0xffffffff:1u),"native sound state unchanged");require(GetLastError()==0x5678,"sound last error unchanged");
}
int main(int argc,char** argv){
 bool baseline=argc==2&&!strcmp(argv[1],"--baseline");bool blockers=argc==2&&!strcmp(argv[1],"--blocker");
 if(blockers)SetEnvironmentVariableW(L"MC_BLOCKER_TRACE",L"1");
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));require(image!=nullptr,"owned image");
 auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(image);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->FileHeader.TimeDateStamp=0x3ed73966;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 BYTE contact[]={0x55,0x8b,0xec,0x81,0xec,0xf0,0,0,0,0x89,0x8d,0x10,0xff,0xff,0xff};memcpy(image+0x6ed4e,contact,sizeof(contact));memcpy(image+0x6ed4e+15,"\x89\xec\x5d",3);jmp(image+0x6ed4e+18,&nativeContact);
 BYTE start[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc};memcpy(image+0x48e54,start,7);memcpy(image+0x48e54+7,"\x89\xec\x5d",3);jmp(image+0x48e54+10,&nativeStart);
 word(image,0xc1304)=DWORD(image+0x6ed4e);word(scene,0)=DWORD(image+0xc12bc);word(scene,0x1564)=DWORD(actor);word(scene,0x10cc)=614;word(scene,0x10d0)=73;
 word(sound,0x124)=DWORD(resource);word(resource,4)=123;word(image,0xf2204)=DWORD(manager);word(manager,0x64)=DWORD(slots);word(manager,0x68)=3;word(slots,0)=word(slots,12)=1;
 for(unsigned i=0;i<4;++i){unsigned off[]={0x1098,0x109c,0x10a4,0x10a8};word(scene,off[i])=DWORD(fades[i]);word(fades[i],0x194)=DWORD(boxes[i]);word(fades[i],0x198)=DWORD(movers[i]);word(boxes[i],0x1b8)=3;word(boxes[i],0x1bc)=i==1?100:0;word(fades[i],0xd4)=i==1?0xffffffff:0;}
 DWORD old;require(VirtualProtect(image,0x10b000,PAGE_EXECUTE_READ,&old)!=0,"RX owned image");auto before=std::vector<BYTE>(image,image+0x10b000);auto m=reinterpret_cast<HMODULE>(image);
 callContact();callSound();require(lines.empty(),"disabled trace has no side effects");
 if(baseline){std::puts("CONTACT_AUDIO_TRACE BASELINE observation=absent physics_audio_passthrough=true game_started=false");VirtualFree(image,0,MEM_RELEASE);return 1;}
 require(installContactAudioTrace(m,logger),"installation");require(installContactAudioTrace(m,logger),"idempotent installation");callContact();callSound();
 require(contains(L"CONTACT_AUDIO_READY ")&&contains(L"field=614 map=73")&&contains(L"velocity_in=10,20,30")&&contains(L"result=5,10,15"),"contact snapshots match native values");
 if(blockers){require(contains(L"BLOCKER_TRACE_READY ")&&contains(L"BLOCKER_STATE "),"blocker state observed");require(contains(L"kind=curtain_out")&&contains(L"pause=-1")&&contains(L"percentage=100"),"held curtain native fields observed");require(count(L"BLOCKER_FADE ")==4,"four fade snapshots");}
 require(contains(L"state_before=0 channel_before=-1 state_after=2 channel_after=1")&&contains(L"slots_busy=2 slots_capacity=3"),"audio allocation snapshots");
 allocationFails=true;word(slots,24)=1;callSound();require(contains(L"state_after=0 channel_after=-1")&&contains(L"slots_busy=3 slots_capacity=3"),"allocation failure observed without forcing sound");allocationFails=false;word(slots,24)=0;
 for(int i=0;i<128;++i)callContact();require(count(L"CONTACT_AUDIO_CONTACT ")<=96,"bounded diagnostic correction rate");
 Sleep(1050);callContact();require(contains(L"CONTACT_AUDIO_DROPPED "),"dropped samples explicit and later window continues");
 MEMORY_BASIC_INFORMATION code{},slot{};VirtualQuery(image+0x48e54,&code,sizeof(code));VirtualQuery(image+0xc1304,&slot,sizeof(slot));require(code.Protect==PAGE_EXECUTE_READ&&slot.Protect==PAGE_EXECUTE_READ,"native page protections preserved");
 require(removeContactAudioTrace(m),"remove");require(removeContactAudioTrace(m),"idempotent remove");require(!memcmp(image,before.data(),before.size()),"whole image byte exact rollback");
 int prior=count(L"CONTACT_AUDIO_CONTACT ");callContact();callSound();require(count(L"CONTACT_AUDIO_CONTACT ")==prior,"restored calls not traced");
 BYTE bad=0xcc;rw(0x48e54,&bad,1);auto damaged=std::vector<BYTE>(image,image+0x10b000);require(!installContactAudioTrace(m,logger),"unknown audio prefix rejected");require(!memcmp(image,damaged.data(),damaged.size()),"guard failure zero writes");rw(0x48e54,start,7);
 DWORD wrong=DWORD(image+0x6ed4e+1);rw(0xc1304,&wrong,4);require(!installContactAudioTrace(m,logger),"foreign collision hook rejected");DWORD expected=DWORD(image+0x6ed4e);rw(0xc1304,&expected,4);
 require(!memcmp(image,before.data(),before.size()),"final baseline exact");VirtualFree(image,0,MEM_RELEASE);
 std::printf("CONTACT_AUDIO_TRACE PASS checks=%d contact_calls=%d sound_calls=%d abi=exact results=unchanged last_error=preserved rollback=byte_exact game_started=false commercial_code_executed=false\n",checks,contactCalls,soundCalls);return 0;
}
