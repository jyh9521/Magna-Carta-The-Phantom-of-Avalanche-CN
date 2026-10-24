#include "story_captions.h"
#include "sample_clock.h"
#include "dialogue_reveal.h"
#include "motion60.h"
#include "panel_canvas.h"
#include <cstdint>
#include <cstring>
#include <cwchar>
#include <initializer_list>
#include "story_caption_data.h"
namespace {
#ifdef STORY_CAPTIONS_TEST
unsigned fixtureCuts=0;
#endif
BYTE* engine=nullptr;BYTE* scene=nullptr;unsigned frame=~0u;
using Draw=void(__thiscall*)(void*);using Destroy=void*(__thiscall*)(void*,unsigned);
using Status=unsigned(WINAPI*)(void*);using Milliseconds=void(WINAPI*)(void*,int*,int*);
using Dispatch=int(__thiscall*)(void*,int);Dispatch originalDispatch=nullptr;
Draw originalDraw=nullptr;Destroy originalDestroy=nullptr;Status status=nullptr;Milliseconds position=nullptr;
bool readable(const void* v,size_t n){auto p=reinterpret_cast<uintptr_t>(v);if(!p||!n||p+n<p)return false;auto end=p+n;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<uintptr_t>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;}
unsigned word(const BYTE* p,unsigned o){return *reinterpret_cast<const unsigned*>(p+o);}
BYTE* ptr(const BYTE* p,unsigned o){return *reinterpret_cast<BYTE*const*>(p+o);}
unsigned hash(const BYTE* p){unsigned h=2166136261u;for(unsigned i=0;i<56;++i)h=(h^p[i])*16777619u;return h;}
void capture(BYTE* p){scene=p;frame=word(engine,0xf1b5c);
#ifndef STORY_CAPTIONS_TEST
 motion60SceneBoundary(scene,word(scene,0x10cc),word(scene,0x156c));
#endif
}
void __fastcall draw(void* p,void*){DWORD error=GetLastError();capture(static_cast<BYTE*>(p));SetLastError(error);originalDraw(p);}
void* __fastcall destroy(void* p,void*,unsigned flags){if(p==scene){scene=nullptr;frame=~0u;}
#ifndef STORY_CAPTIONS_TEST
 motion60SceneBoundary(nullptr,~0u,~0u);
#endif
 return originalDestroy(p,flags);
}
int __fastcall dispatch(void* value,void*,int index){
 bool cut=false;auto dealer=static_cast<BYTE*>(value);
 if(readable(dealer,0x58)&&index>=0&&unsigned(index)<word(dealer,0x38)&&word(dealer,0x38)<=256){
  auto slots=ptr(dealer,0x34);if(readable(slots,size_t(word(dealer,0x38))*40)){
   auto slot=slots+unsigned(index)*40;auto parameters=ptr(slot,0x14);unsigned op=word(slot,0);
   if(!word(slot,4)&&readable(parameters,56))cut=op==501||(op==500&&int(word(parameters,4))<=1);
  }
 }
 int result=originalDispatch(value,index);DWORD error=GetLastError();
#ifndef STORY_CAPTIONS_TEST
 if(cut)motion60SceneCut();
#else
 if(cut)++fixtureCuts;
#endif
 SetLastError(error);return result;
}
bool hidden(BYTE* box){if(word(box,0xd0))return true;auto gui=ptr(scene,0x10c8);if(readable(gui,0x1a0)){auto parent=ptr(gui,0x19c);if(readable(parent,0xd4)&&word(parent,0xd0))return true;}
 // A full curtain can be behind a visible dialogue box; opacity is not visibility evidence.
 return false;}
const wchar_t* text(){
 if(!engine||frame!=word(engine,0xf1b5c)||!readable(scene,0x1738)||ptr(scene,0)!=engine+0xc12bc)return nullptr;
 auto dealer=ptr(scene,0x3c);if(!readable(dealer,0x58)||ptr(dealer,0)!=engine+0xc1320||ptr(dealer,0x54)!=scene||word(dealer,0x4c))return nullptr;
 unsigned n=word(dealer,0x38);auto slots=ptr(dealer,0x34);if(n<1||n>256||!readable(slots,size_t(n)*40))return nullptr;
 const wchar_t* ordinary=nullptr;const wchar_t* narration=nullptr;uint64_t latest=0;
 for(unsigned i=0;i<n;++i){auto slot=slots+i*40;unsigned op=word(slot,0);if((op!=603&&op!=700&&op!=704)||!word(slot,4))continue;
  auto parameters=ptr(slot,0x14);if(!readable(parameters,56))continue;unsigned signature=hash(parameters);
  const StoryBinding* binding=nullptr;for(const auto& b:storyBindings)if(b.field==word(scene,0x10cc)&&b.opcode==op&&b.parameters==signature){binding=&b;break;}if(!binding)continue;
  if(op==603){auto sound=ptr(slot,0x18);if(!readable(sound,0x134)||ptr(sound,0)!=engine+0xbe540||word(sound,0x128)!=2)continue;
   auto audio=ptr(engine,0xf2204);int channel=int(word(sound,0x120));if(!readable(audio,0x6c)||channel<0||unsigned(channel)>=word(audio,0x68)||word(audio,0x68)>4096)continue;
   auto channels=ptr(audio,0x64);if(!readable(channels,size_t(word(audio,0x68))*12))continue;auto handle=ptr(channels,unsigned(channel)*12+8);if(!handle||!status)continue;
   unsigned state=status(handle);SampleCursor cursor{};if(!sampleCursor(handle,cursor))continue;
   if(state!=4&&!(!cursor.running&&(state==8||state==2)))continue;
   for(const auto& cue:storyCues)if(cue.resource==binding->resource&&cue.start<=cursor.milliseconds&&cursor.milliseconds<cue.end&&cursor.generation>=latest){latest=cursor.generation;narration=cue.text;break;}
  }else{
   auto box=ptr(slot,op==704?0x1c:0x18);if(!readable(box,0x200)||(ptr(box,0)!=engine+0xbfcec&&ptr(box,0)!=engine+0xbfee4)||word(box,0x190)<2||word(box,0x190)>4||!hidden(box))continue;
#ifndef STORY_CAPTIONS_TEST
   auto stream=dialogueCaptionStream(box);if(!stream||!position)continue;int total=0,current=0;position(stream,&total,&current);if(total<=0||current<0||current>=total)continue;
#endif
   ordinary=binding->text;
  }
 }
 return narration?narration:ordinary;
}
bool replace(DWORD* p,DWORD from,DWORD to){if(*p!=from)return false;DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;*p=to;DWORD ignored;return VirtualProtect(p,4,old,&ignored)!=0;}
}
bool storyCaptionPanel(int w,int h,FramePanel& out){const auto caption=text();if(!caption||!*caption||w<160||h<120)return false;
 static PanelCanvas canvas;static const wchar_t* previous=nullptr;static int usedHeight=0;
 int width=w*4/5,limit=h/3;if(limit>480)limit=480;bool changed=canvas.width!=width||canvas.height!=limit;
 if(!canvas.resize(width,limit))return false;
 if(changed||previous!=caption){
  int size=h/40;if(size<12)size=12;RECT measure{};HFONT font=nullptr;HGDIOBJ old=nullptr;
  for(;;){font=CreateFontW(-size,0,0,0,FW_MEDIUM,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,storyCaptionFont);if(!font)return false;old=SelectObject(canvas.dc,font);measure={12,8,width-12,limit-8};DrawTextW(canvas.dc,caption,-1,&measure,DT_WORDBREAK|DT_NOPREFIX|DT_CALCRECT);
   if(measure.bottom-measure.top<=limit-16||size<=8)break;SelectObject(canvas.dc,old);DeleteObject(font);--size;
  }
  usedHeight=measure.bottom-measure.top+16;if(usedHeight>limit){SelectObject(canvas.dc,old);DeleteObject(font);return false;}
  RECT area{0,0,width,usedHeight};HBRUSH brush=CreateSolidBrush(RGB(12,16,22));FillRect(canvas.dc,&area,brush);DeleteObject(brush);SetBkMode(canvas.dc,TRANSPARENT);SetTextColor(canvas.dc,RGB(245,245,245));area={12,8,width-12,usedHeight-8};DrawTextW(canvas.dc,caption,-1,&area,DT_WORDBREAK|DT_NOPREFIX);SelectObject(canvas.dc,old);DeleteObject(font);GdiFlush();previous=caption;
 }
 out={(w-width)/2,h-h/12-usedHeight,width,usedHeight,canvas.pixels};return true;
}
bool installStoryCaptions(HMODULE module,void(*logger)(const wchar_t*)){
 auto p=reinterpret_cast<BYTE*>(module);if(engine)return engine==p;
 if(!readable(p+0xc12bc,16)||word(p,0xc12bc)!=DWORD(p+0x71270)||word(p,0xc12c8)!=DWORD(p+0x6b3bc)||word(p,0xc1364)!=DWORD(p+0x71b9b))return false;
 auto m=GetModuleHandleW(L"Mss32.dll");status=reinterpret_cast<Status>(GetProcAddress(m,"_AIL_3D_sample_status@4"));position=reinterpret_cast<Milliseconds>(GetProcAddress(m,"_AIL_stream_ms_position@12"));if(!status||!position||!installSampleClock(module,logger))return false;
 originalDraw=reinterpret_cast<Draw>(p+0x6b3bc);originalDestroy=reinterpret_cast<Destroy>(p+0x71270);
 if(!replace(reinterpret_cast<DWORD*>(p+0xc12c8),DWORD(originalDraw),DWORD(&draw))){removeSampleClock(module);return false;}
 if(!replace(reinterpret_cast<DWORD*>(p+0xc12bc),DWORD(originalDestroy),DWORD(&destroy))){replace(reinterpret_cast<DWORD*>(p+0xc12c8),DWORD(&draw),DWORD(originalDraw));removeSampleClock(module);return false;}
 originalDispatch=reinterpret_cast<Dispatch>(p+0x71b9b);
 if(!replace(reinterpret_cast<DWORD*>(p+0xc1364),DWORD(originalDispatch),DWORD(&dispatch))){replace(reinterpret_cast<DWORD*>(p+0xc12bc),DWORD(&destroy),DWORD(originalDestroy));replace(reinterpret_cast<DWORD*>(p+0xc12c8),DWORD(&draw),DWORD(originalDraw));removeSampleClock(module);return false;}
 engine=p;setFramePanel(0,&storyCaptionPanel);if(logger)logger(L"STORY_CAPTIONS_READY standalone=all_catalogued_field_voices ordinary_hidden=fallback clock=audio_lifetime curtain=unchanged scene_frame=guarded");return true;
}
bool removeStoryCaptions(HMODULE m){if(engine!=reinterpret_cast<BYTE*>(m)||word(engine,0xc12c8)!=DWORD(&draw)||word(engine,0xc12bc)!=DWORD(&destroy)||word(engine,0xc1364)!=DWORD(&dispatch)||!sampleClockOwned(m))return false;setFramePanel(0,nullptr);
 if(!replace(reinterpret_cast<DWORD*>(engine+0xc12c8),DWORD(&draw),DWORD(originalDraw))||!replace(reinterpret_cast<DWORD*>(engine+0xc12bc),DWORD(&destroy),DWORD(originalDestroy))||!replace(reinterpret_cast<DWORD*>(engine+0xc1364),DWORD(&dispatch),DWORD(originalDispatch))||!removeSampleClock(m))return false;engine=scene=nullptr;frame=~0u;return true;}
#ifdef STORY_CAPTIONS_TEST
void storyCaptionFixture(BYTE* p,BYTE* s,Status sampleStatus){engine=p;status=sampleStatus;capture(s);}
void storyCaptionFixtureFrame(){if(scene)capture(scene);}
void storyCaptionFixtureReset(){engine=scene=nullptr;frame=~0u;fixtureCuts=0;}
unsigned storyCaptionFixtureCuts(){return fixtureCuts;}
#endif
