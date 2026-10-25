#include "story_captions.h"
#include "sample_clock.h"
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <vector>
void setFramePanel(unsigned,FramePanelSource){}
static BYTE* image;static BYTE scene[0x1740],dealer[0x80],slots[80],sound[0x138],audio[0x80],channels[12];static int parameters[14]={476,1};
static unsigned state=4;
unsigned& word(void* p,unsigned o){return *reinterpret_cast<unsigned*>(static_cast<BYTE*>(p)+o);}
unsigned WINAPI status(void*){return state;}
void require(bool v,const char* message){if(!v){printf("STORY_CAPTIONS FAIL %s\n",message);fflush(stdout);ExitProcess(1);}}
bool paint(){FramePanel p{};bool ok=storyCaptionPanel(1280,720,p);if(ok){require(p.pixels&&p.width>0&&p.height>0,"owned caption panel");unsigned lit=0;for(int i=0;i<p.width*p.height;++i)if((p.pixels[i]&0xffffff)>0x404040)++lit;require(lit>10,"visible glyphs not empty box");}return ok;}
static unsigned draws=0;
void __fastcall nativeDraw(void*,void*){++draws;}
void* __fastcall nativeDestroy(void* p,void*,unsigned){return p;}
int __fastcall nativeDispatch(void*,void*,int){return 777;}
void jump(BYTE* p,void* to){p[0]=0xe9;*reinterpret_cast<DWORD*>(p+1)=DWORD(to)-DWORD(p+5);}
int matrix(const char* path){
 FILE* f=nullptr;require(fopen_s(&f,path,"rb")==0&&f,"matrix input");unsigned magic=0,count=0;require(fread(&magic,4,1,f)==1&&magic==0x314d4353&&fread(&count,4,1,f)==1&&count<=10000,"matrix header");
 BYTE box[0x200]{},fade[0x1a0]{},rectangle[0x1c0]{},gui[0x1a8]{},root[0xd4]{};unsigned cases=0;word(scene,0x10c8)=DWORD(gui);word(gui,0x19c)=DWORD(root);word(scene,0)=DWORD(image+0xc12bc);word(scene,0x3c)=DWORD(dealer);word(dealer,0)=DWORD(image+0xc1320);word(dealer,0x54)=DWORD(scene);word(dealer,0x34)=DWORD(slots);word(dealer,0x38)=1;storyCaptionFixture(image,scene,status);
 for(unsigned row=0;row<count;++row){unsigned record[16];require(fread(record,sizeof(record),1,f)==1,"matrix row");unsigned bytes=0;require(fread(&bytes,4,1,f)==1&&bytes<100000&&!(bytes&1),"matrix text bounds");std::vector<wchar_t> expected(bytes/2+1);require(fread(expected.data(),bytes,1,f)==1,"matrix complete text");word(scene,0x10cc)=record[0];word(slots,0)=record[1];word(slots,4)=1;word(slots,0x14)=DWORD(record+2);word(slots,record[1]==704?0x1c:0x18)=DWORD(box);
  for(unsigned table:{0xbfcecu,0xbfee4u})for(unsigned phase:{2u,3u,4u})for(unsigned hide:{0u,1u}){word(box,0)=DWORD(image+table);word(box,0x190)=phase;word(box,0xd0)=hide;auto text=storyCaptionFixtureText();require(hide?(text&&!wcscmp(text,expected.data())):!text,"all-binding native visibility and complete text matrix");++cases;}
  word(box,0xd0)=0;word(gui,0xd0)=1;require(storyCaptionFixtureText(),"all-binding hidden GUI retains voice");word(gui,0xd0)=0;word(root,0xd0)=1;require(storyCaptionFixtureText(),"all-binding hidden root retains voice");word(root,0xd0)=0;cases+=2;
  word(box,0x190)=3;for(unsigned offset:{0x1098u,0x109cu,0x10a4u,0x10a8u})for(unsigned opacity:{0u,94u,95u,100u}){word(scene,offset)=DWORD(fade);word(fade,0x194)=DWORD(rectangle);word(rectangle,0x1bc)=opacity;word(box,0xd0)=0;require(!storyCaptionFixtureText(),"all-binding curtain cannot imply hidden");word(box,0xd0)=1;require(storyCaptionFixtureText(),"all-binding hidden voice remains covered");word(scene,offset)=0;cases+=2;}
 }
 require(fgetc(f)==EOF,"matrix trailing bytes");fclose(f);printf("SUBTITLE_MATRIX PASS bindings=%u cases=%u op700_704=covered native_vtables=2 phases2_4=covered curtain_slots=4\n",count,cases);return 0;
}
int voiceMatrix(const char* path){
 FILE* f=nullptr;require(fopen_s(&f,path,"rb")==0&&f,"voice matrix input");unsigned magic=0,count=0;require(fread(&magic,4,1,f)==1&&magic==0x31564353&&fread(&count,4,1,f)==1&&count<=10000,"voice matrix header");
 word(scene,0)=DWORD(image+0xc12bc);word(scene,0x3c)=DWORD(dealer);word(dealer,0)=DWORD(image+0xc1320);word(dealer,0x54)=DWORD(scene);word(dealer,0x34)=DWORD(slots);word(dealer,0x38)=1;
 word(sound,0)=DWORD(image+0xbe540);word(sound,0x128)=2;word(image,0xf2204)=DWORD(audio);word(audio,0x64)=DWORD(channels);word(audio,0x68)=1;void* handle=reinterpret_cast<void*>(0x1234);word(channels,8)=DWORD(handle);storyCaptionFixture(image,scene,status);unsigned cues=0;
 for(unsigned row=0;row<count;++row){unsigned record[16],size=0;require(fread(record,sizeof(record),1,f)==1&&fread(&size,4,1,f)==1&&size>0&&size<100,"voice matrix row");word(scene,0x10cc)=record[0];word(slots,0)=603;word(slots,4)=1;word(slots,0x14)=DWORD(record+2);word(slots,0x18)=DWORD(sound);state=4;unsigned base=(row+1)*1000000;sampleClockFixtureTime(base);sampleClockFixtureEvent(handle,0);
  for(unsigned cue=0;cue<size;++cue){unsigned times[3];require(fread(times,sizeof(times),1,f)==1&&times[0]<times[1]&&times[2]<100000&&!(times[2]&1),"voice cue bounds");std::vector<wchar_t> expected(times[2]/2+1);require(fread(expected.data(),times[2],1,f)==1,"voice cue text");
   for(unsigned ms:{times[0],(times[0]+times[1])/2,times[1]-1}){sampleClockFixtureTime(base+ms);auto text=storyCaptionFixtureText();require(text&&!wcscmp(text,expected.data()),"every speech cue includes full phrase at start middle and tail");}
   word(dealer,0x4c)=1;require(!storyCaptionFixtureText(),"every cue clears while skipped");word(dealer,0x4c)=0;require(storyCaptionFixtureText(),"cue source retained after skip reset");
   ++word(image,0xf1b5c);require(!storyCaptionFixtureText(),"every cue clears on stale Field frame");storyCaptionFixtureFrame();
   word(scene,0x10cc)=record[0]+10000;require(!storyCaptionFixtureText(),"every cue excludes another Field");word(scene,0x10cc)=record[0];
   word(slots,0)=0xffffffff;require(!storyCaptionFixtureText(),"every cue clears on event release");word(slots,0)=603;
   if(cue+1==size){sampleClockFixtureEvent(handle,1);state=8;sampleClockFixtureTime(base+times[1]+90000);auto text=storyCaptionFixtureText();require(text&&!wcscmp(text,expected.data()),"every final phrase survives pause");}
   ++cues;
  }
  sampleClockFixtureEvent(handle,2);require(!storyCaptionFixtureText(),"voice matrix end clears caption");word(dealer,0x4c)=1;require(!storyCaptionFixtureText(),"voice matrix skip clears caption");word(dealer,0x4c)=0;
 }
 require(fgetc(f)==EOF,"voice matrix trailing bytes");fclose(f);printf("VOICE_CUE_MATRIX PASS bindings=%u cues=%u start_mid_tail=exact final_pause=held end_skip=cleared\n",count,cues);return 0;
}
int main(int argc,char** argv){
 image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image,"owned image");
 if(argc==3&&!strcmp(argv[1],"--voice-matrix"))return voiceMatrix(argv[2]);
 if(argc==3&&!strcmp(argv[1],"--matrix"))return matrix(argv[2]);
 word(scene,0)=DWORD(image+0xc12bc);word(scene,0x10cc)=346;word(scene,0x156c)=4;word(scene,0x3c)=DWORD(dealer);
 word(dealer,0)=DWORD(image+0xc1320);word(dealer,0x54)=DWORD(scene);word(dealer,0x34)=DWORD(slots);word(dealer,0x38)=2;
 word(slots,0)=603;word(slots,4)=1;word(slots,0x14)=DWORD(parameters);word(slots,0x18)=DWORD(sound);
 word(sound,0)=DWORD(image+0xbe540);word(sound,0x128)=2;word(sound,0x120)=0;
 word(image,0xf2204)=DWORD(audio);word(audio,0x64)=DWORD(channels);word(audio,0x68)=1;void* handle=reinterpret_cast<void*>(0x1234);word(channels,8)=DWORD(handle);
 sampleClockFixtureTime(1000);sampleClockFixtureEvent(handle,0);storyCaptionFixture(image,scene,status);
 require(!paint(),"pre-speech silence remains empty");sampleClockFixtureTime(1500);require(paint(),"voice-only caption follows sample start");
 BYTE priorityBox[0x200]{},priorityGui[0x1a8]{},priorityRoot[0xd4]{},choice[0x1e4]{};
 word(scene,0x10c8)=DWORD(priorityGui);word(priorityGui,0x19c)=DWORD(priorityRoot);
 for(unsigned op:{700u,701u,704u,705u})for(unsigned table:{0xbfcecu,0xbfee4u}){
  memset(slots+40,0,40);word(slots+40,0)=op;word(slots+40,4)=1;word(slots+40,op==704?0x1c:0x18)=DWORD(priorityBox);word(priorityBox,0)=DWORD(image+table);
  for(unsigned phase=1;phase<=5;++phase){word(priorityBox,0x190)=phase;require(!paint(),"visible native dialogue takes priority over standalone603 caption");word(priorityBox,0xd0)=1;require(paint(),"standalone voice retained when native box hidden");word(priorityBox,0xd0)=0;}
  word(priorityGui,0xd0)=1;require(paint(),"hidden full GUI retains standalone voice");word(priorityGui,0xd0)=0;
  word(priorityRoot,0xd0)=1;require(paint(),"hidden native root does not suppress narration");word(priorityRoot,0xd0)=0;
 }
 memset(slots+40,0,40);word(choice,0)=DWORD(image+0xc04e8);word(choice,0x1dc)=DWORD(priorityBox);word(priorityBox,0x190)=3;word(priorityGui,0x1a4)=DWORD(choice);
 require(!paint(),"visible native choice question owns the subtitle area");word(choice,0xd0)=1;require(paint(),"hidden choice allows standalone voice");word(choice,0xd0)=0;word(priorityGui,0xd0)=1;require(paint(),"hidden GUI does not suppress standalone voice");word(priorityGui,0xd0)=0;word(priorityGui,0x1a4)=0;
 require(paint(),"standalone603 resumes when native dialogue is gone");word(scene,0x10c8)=0;
 puts("SUBTITLE_ARBITRATION PASS native700_701_704_705=priority choices=priority both_vtables=covered phases1_5=covered hidden=retained");
 sampleClockFixtureEvent(handle,1);state=8;sampleClockFixtureTime(90000);require(paint(),"paused caption holds real sample time, not wall-clock duration");state=2;require(paint(),"paused provider may report DONE while explicit stop clock remains frozen");
 sampleClockFixtureEvent(handle,0);state=4;require(!paint(),"restart resets to source silence");sampleClockFixtureTime(90500);require(paint(),"restart resumes first source cue");
 word(dealer,0x4c)=1;require(!paint(),"skip clears caption immediately");word(dealer,0x4c)=0;require(paint(),"source restored after skip fixture");
 ++word(image,0xf1b5c);require(!paint(),"new non-Field frame cannot reuse previous scene subtitle");storyCaptionFixtureFrame();require(paint(),"current Field draw reestablishes same-frame identity");
 word(scene,0x10cc)=740;require(!paint(),"new scene cannot inherit prior binding");word(scene,0x10cc)=346;
 word(channels,8)=0x5678;require(!paint(),"channel handle reuse without new clock excluded");word(channels,8)=DWORD(handle);
 word(slots,0)=0xffffffff;require(!paint(),"released event clears subtitle");word(slots,0)=603;
 sampleClockFixtureEvent(handle,2);require(!paint(),"audio end clears subtitle before object update");
 BYTE box[0x200]{},fade[0x1a0]{},rectangle[0x1c0]{};int dialogueParameters[14]={10002,101,0,100,0,3,5,1342,80};
 word(scene,0x10cc)=258;word(slots,0)=700;word(slots,0x14)=DWORD(dialogueParameters);word(slots,0x18)=DWORD(box);word(box,0)=DWORD(image+0xbfcec);word(box,0x190)=3;
 require(!paint(),"visible ordinary box does not get duplicate subtitle");word(box,0xd0)=1;require(paint(),"hidden ordinary voice box gets fallback");word(box,0xd0)=0;
 for(unsigned offset:{0x1098u,0x109cu,0x10a4u,0x10a8u}){
  word(scene,offset)=DWORD(fade);word(fade,0x194)=DWORD(rectangle);
  for(unsigned opacity:{0u,94u,95u,100u}){
   word(rectangle,0x1bc)=opacity;word(box,0xd0)=0;require(!paint(),"visible ordinary box above full curtain must not duplicate subtitle");
   word(box,0xd0)=1;require(paint(),"hidden ordinary box still gets fallback regardless of curtain");
   word(box,0xd0)=0;require(!paint(),"native box becoming visible immediately suppresses fallback");
  }
  word(scene,offset)=0;
 }
 BYTE gui[0x1a8]{},parent[0xd4]{};word(scene,0x10c8)=DWORD(gui);word(gui,0x19c)=DWORD(parent);word(parent,0xd0)=1;require(paint(),"hidden dialogue root retains fallback");word(parent,0xd0)=0;require(!paint(),"visible dialogue root suppresses fallback");word(box,0xd0)=1;
 puts("SUBTITLE_DEDUP PASS visible_native=priority curtain_slots=4 opacity_cases=4 hidden_box=retained visibility_transition=immediate");
 word(slots+40,0)=705;word(slots+40,4)=1;word(slots+40,0x18)=DWORD(priorityBox);word(priorityBox,0x190)=3;require(!paint(),"visible silent705 suppresses hidden700 fallback");word(slots+40,0)=0;
 word(box,0x190)=4;require(paint(),"paused ordinary text remains visible");word(box,0x190)=6;require(!paint(),"confirmed/skipped ordinary box clears caption");
 word(dealer,0x38)=0x100000;require(!paint(),"foreign table size guarded");
 if(argc==2){
  require(LoadLibraryA(argv[1])!=nullptr,"owned provider load");storyCaptionFixtureReset();word(dealer,0x38)=2;
  auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.TimeDateStamp=0x3ed73966;nt->OptionalHeader.SizeOfImage=0x10b000;
  word(image,0xc12bc)=DWORD(image+0x71270);word(image,0xc12c8)=DWORD(image+0x6b3bc);word(image,0xc1364)=DWORD(image+0x71b9b);
  jump(image+0x71270,reinterpret_cast<void*>(&nativeDestroy));jump(image+0x6b3bc,reinterpret_cast<void*>(&nativeDraw));jump(image+0x71b9b,reinterpret_cast<void*>(&nativeDispatch));
  auto m=GetModuleHandleW(L"Mss32.dll");unsigned sites[]={0xbd4a4,0xbd4ac,0xbd4a8,0xbd474};const char* names[]={"_AIL_start_3D_sample@4","_AIL_stop_3D_sample@4","_AIL_end_3D_sample@4","_AIL_release_3D_sample_handle@4"};
  for(unsigned i=0;i<4;++i)word(image,sites[i])=DWORD(GetProcAddress(m,names[i]));
  std::vector<BYTE> original(image,image+0x10b000);require(installStoryCaptions(HMODULE(image),nullptr),"install actual production slots");
  using Draw=void(__thiscall*)(void*);using Dispatch=int(__thiscall*)(void*,int);using Delete=void*(__thiscall*)(void*,unsigned);
  reinterpret_cast<Draw>(word(image,0xc12c8))(scene);require(draws==1,"original field draw retained");word(box,0x190)=3;require(paint(),"real draw callback captures current frame");
  auto dispatch=reinterpret_cast<Dispatch>(word(image,0xc1364));word(slots,0)=501;word(slots,4)=0;require(dispatch(dealer,0)==777&&storyCaptionFixtureCuts()==1,"native immediate camera command resets render history once");
  word(slots,0)=500;dialogueParameters[1]=30;require(dispatch(dealer,0)==777&&storyCaptionFixtureCuts()==1,"smooth camera path not reset each tick");dialogueParameters[1]=1;dispatch(dealer,0);require(storyCaptionFixtureCuts()==2,"single-frame shot is a cut");word(slots,4)=1;dispatch(dealer,0);require(storyCaptionFixtureCuts()==2,"held camera command not reset every frame");
  require(reinterpret_cast<Delete>(word(image,0xc12bc))(scene,0)==scene&&!paint(),"native scene destroy clears subtitle lifetime");
  auto saved=word(image,0xc1364);word(image,0xc1364)=0x12345678;std::vector<BYTE> foreign(image,image+0x10b000);require(!removeStoryCaptions(HMODULE(image))&&!memcmp(image,foreign.data(),foreign.size()),"foreign callback preserved without partial rollback");word(image,0xc1364)=saved;
  require(removeStoryCaptions(HMODULE(image))&&!memcmp(image,original.data(),original.size()),"all scene dispatcher and audio slots rollback byte exact");
  puts("STORY_CAPTIONS_SLOTS PASS field_draw=retained camera_cut=guarded smooth_camera=retained scene_destroy=cleared rollback=byte_exact owned_provider=true game_started=false");
 }
 puts("STORY_CAPTIONS PASS actual_panel=visible pause=held restart=reset skip=cleared scene_frame=guarded handle_reuse=excluded event_end=cleared game_started=false");return 0;
}
