#include "gamepad_ui.h"
#include "modern_gamepad.h"
#include "ui_focus.h"
#include <array>
#include <vector>
#include <set>
#include <cmath>
#include <cstring>
#include <cwchar>
namespace {
constexpr unsigned slots[]={0xbee50,0xbf048,0xbf240,0xbf438,0xbf630,0xbf828,0xbfa20,0xbfc18,0xbfeb4,0xc00ac,0xc02a4,0xc049c,0xc06b0,0xc08c4,0xc0adc,0xc0cf0,0xc1560,0xc1da8,0xc1fa0,0xc2204,0xc2508};
constexpr BYTE prefix[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xf8};
constexpr BYTE cancelPrefix[]={0x55,0x8b,0xec,0x51,0x89,0x4d,0xfc};
using Draw=void(__thiscall*)(void*);Draw originalCursorDraw=nullptr;
using Dispatch=int(__thiscall*)(void*);Dispatch original=nullptr;BYTE* engine=nullptr;
thread_local unsigned depth=0;DWORD consumed=0,lastRepeat=0,maskedSerial=0,lastDirectionSerial=0;unsigned maskedDirections=0,previousVirtualDirections=0;unsigned previousHeld=0,traceEvents=0;bool traceLimited=false;void(*trace)(const wchar_t*)=nullptr;
struct CursorObservation {int x,y,inputHidden,nativeBlock,nativeOrder;float spriteX,spriteY;int finite;};
CursorObservation lastCursorObservation{};void* lastCursorObject=nullptr;unsigned cursorTraceEvents=0;bool cursorTraceLimited=false,cursorTraceKnown=false;
bool readable(const void* a,size_t n){auto p=reinterpret_cast<ULONG_PTR>(a),end=p+n;if(!p||end<p)return false;while(p<end){MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m))||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;auto next=reinterpret_cast<ULONG_PTR>(m.BaseAddress)+m.RegionSize;if(next<=p)return false;p=next;}return true;}
bool gui(BYTE* p){if(!readable(p,0x190))return false;auto vt=*reinterpret_cast<ULONG_PTR*>(p);for(auto slot:slots)if(vt==reinterpret_cast<ULONG_PTR>(engine+slot-0x1c8))return true;return false;}
bool defaultArrows(BYTE* p){
 auto vt=*reinterpret_cast<BYTE**>(p);
 // Base GUI pressed-arrow methods forward generic events 3/7/11/15.
 // The older fixture confused them with unrelated no-op virtual methods.
 constexpr unsigned forward[]={0x55f0a,0x55f23,0x55f3c,0x55f55};
 constexpr unsigned noop[]={0x55b97,0x55b8c,0x55b81,0x55ba2};
 bool generic=true,empty=true;for(unsigned i=0;i<4;++i){auto f=*reinterpret_cast<ULONG_PTR*>(vt+0xc8+i*4);generic&=f==reinterpret_cast<ULONG_PTR>(engine+forward[i]);empty&=f==reinterpret_cast<ULONG_PTR>(engine+noop[i]);}
 return generic||empty;
}
bool admittedMouseTarget(BYTE* p){
 if(!*reinterpret_cast<int*>(p+0xe8)||!*reinterpret_cast<int*>(p+0x160))return false;
 auto manager=*reinterpret_cast<BYTE**>(engine+0xf220c);
 if(readable(manager,0x40)&&*reinterpret_cast<int*>(manager+0x38)>0){
  auto node=*reinterpret_cast<BYTE**>(manager+0x3c);
  return readable(node,4)&&*reinterpret_cast<BYTE**>(node)==p;
 }
 int mode=*reinterpret_cast<int*>(p+0x164);return mode==0||mode==1;
}
bool collect(BYTE* p,std::vector<modern_input::FocusTarget>& out,std::set<BYTE*>& visited,float x,float y,int w,int h,bool& nativeArrowControl){
 if(!gui(p)||visited.size()>=256||!visited.insert(p).second)return false;
 auto child=*reinterpret_cast<BYTE**>(p+0x18);bool eligibleChild=false;std::set<BYTE*> chain;
 for(;child&&chain.size()<128&&readable(child,0x14)&&chain.insert(child).second;child=*reinterpret_cast<BYTE**>(child+0x10))if(gui(child)){
  // Native eligibility requires visible+enabled. Inactive decoration must not
  // hide the parent; every eligible child keeps the existing dispatch priority.
  bool eligible=collect(child,out,visited,x,y,w,h,nativeArrowControl);eligibleChild=eligibleChild||eligible;
 }
 // Native 55134 dispatches children before checking the parent's own eligibility.
 if(eligibleChild)return true;
 if(!admittedMouseTarget(p))return false;
 if(!*reinterpret_cast<void**>(p+0x17c))return true;
 // +f8 is the list object. GetFirst (RVA 02014) reads its +8 head;
 // dereferencing the container itself mistakes its count for a pointer.
 auto node=*reinterpret_cast<BYTE**>(p+0x100);float ox=*reinterpret_cast<float*>(p+0x24),oy=*reinterpret_cast<float*>(p+0x28);
 if(!std::isfinite(ox)||!std::isfinite(oy)||std::abs(ox)>100000||std::abs(oy)>100000)return true;
 chain.clear();for(;node&&chain.size()<32&&readable(node,8)&&chain.insert(node).second;node=*reinterpret_cast<BYTE**>(node+4)){
  auto rect=*reinterpret_cast<int**>(node);if(!readable(rect,16))break;
  modern_input::FocusTarget r{reinterpret_cast<uintptr_t>(p),float(rect[0])+ox,float(rect[1])+oy,float(rect[2])+ox,float(rect[3])+oy};
  if(r.right-r.left<4||r.bottom-r.top<4||r.right-r.left>w*.8f||r.bottom-r.top>h*.8f||r.left<0||r.top<0||r.right>w||r.bottom>h)continue;
  if(!defaultArrows(p)&&x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom)nativeArrowControl=true;
  if(out.size()<128)out.push_back(r);
 }
 return true;
}
bool traceSlot(){
 if(!trace)return false;
 if(traceEvents<256){++traceEvents;return true;}
 if(!traceLimited){traceLimited=true;trace(L"INPUT_UI_TRACE_LIMIT events=256 further_menu_events=omitted");}
 return false;
}
void traceFocus(BYTE* root,const modern_input::FocusTarget& target,float fromX,float fromY){
 auto widget=reinterpret_cast<BYTE*>(target.identity);
 if(!gui(root)||!gui(widget)||!traceSlot())return;
 wchar_t message[384];
 swprintf_s(message,L"INPUT_UI_FOCUS serial=%lu root_class=%x root_id=%x target_class=%x target_id=%x from=%d,%d to=%d,%d rect=%d,%d,%d,%d observation=virtual_selection",
 modernGamepadNavigation().serial,unsigned(*reinterpret_cast<ULONG_PTR*>(root)-reinterpret_cast<ULONG_PTR>(engine)),*reinterpret_cast<unsigned*>(root+4),
 unsigned(*reinterpret_cast<ULONG_PTR*>(widget)-reinterpret_cast<ULONG_PTR>(engine)),*reinterpret_cast<unsigned*>(widget+4),
 int(fromX),int(fromY),int((target.left+target.right)*.5f),int((target.top+target.bottom)*.5f),int(target.left),int(target.top),int(target.right),int(target.bottom));trace(message);
}
void traceClick(BYTE* root,DWORD serial){
 if(!trace||!gui(root))return;
 int left=*reinterpret_cast<int*>(engine+0xf1c9c+VK_LBUTTON*4),right=*reinterpret_cast<int*>(engine+0xf1c9c+VK_RBUTTON*4);
 if((left!=1&&left!=-1&&right!=1&&right!=-1)||!traceSlot())return;
 wchar_t message[256];swprintf_s(message,L"INPUT_UI_CLICK serial=%lu root_class=%x root_id=%x x=%d y=%d left=%d right=%d phase=before_mouse source=merged_input",
 serial,unsigned(*reinterpret_cast<ULONG_PTR*>(root)-reinterpret_cast<ULONG_PTR>(engine)),*reinterpret_cast<unsigned*>(root+4),
 *reinterpret_cast<int*>(engine+0xf20b0),*reinterpret_cast<int*>(engine+0xf20a8),left,right);trace(message);
}
void navigate(BYTE* root){
 auto n=modernGamepadNavigation();if(!n.active||n.serial==consumed)return;
 unsigned held=n.held&15;bool fresh=(n.pressed&15)!=0;
 if(!held){previousHeld=0;consumed=n.serial;return;}
 if(held!=previousHeld)fresh=true;
 if(!fresh&&DWORD(n.time-lastRepeat)<400)return;
 if(!gui(root))return;
 // The exclusive stack selects the actual modal, not widgets hidden behind it.
 auto manager=*reinterpret_cast<BYTE**>(engine+0xf220c);
 if(readable(manager,0x40)&&*reinterpret_cast<int*>(manager+0x38)>0){auto node=*reinterpret_cast<BYTE**>(manager+0x3c);if(!readable(node,4))return;root=*reinterpret_cast<BYTE**>(node);if(!gui(root))return;}
 if(*reinterpret_cast<ULONG_PTR*>(root)==reinterpret_cast<ULONG_PTR>(engine+0xc2340)){
  auto title=*reinterpret_cast<BYTE**>(root+0x1a8);if(!readable(title,0x74)||*reinterpret_cast<int*>(title+0x70)!=4)return;
 }
 int w=*reinterpret_cast<int*>(engine+0xf1b48),h=*reinterpret_cast<int*>(engine+0xf1b4c);if(w<=0||h<=0)return;
 float x=float(*reinterpret_cast<int*>(engine+0xf20b0)),y=float(*reinterpret_cast<int*>(engine+0xf20a8));
 std::vector<modern_input::FocusTarget> targets;std::set<BYTE*> seen;bool native=false;collect(root,targets,seen,x,y,w,h,native);
 // An ineligible/empty root must not consume the serial or mutate repeat state:
 // the native GUI manager may dispatch another root for this same input frame.
 if(native)return; // Original dispatch result, not our classifier, decides consumption.
 int dx=(held&4)?-1:(held&8)?1:0,dy=(held&1)?-1:(held&2)?1:0;if(dy)dx=0;
 int index=modern_input::chooseFocus(targets,x,y,dx,dy);if(index<0)return;const auto& r=targets[index];
 modernGamepadFocusCursor((r.left+r.right)*.5f,(r.top+r.bottom)*.5f);
 traceFocus(root,r,x,y);
 consumed=n.serial;previousHeld=held;lastRepeat=fresh?n.time:n.time-250;
 static LONG calls=0;if(InterlockedIncrement(&calls)==1&&trace)trace(L"GAMEPAD_UI_FOCUS_APPLIED native_hit_rects=true click_dispatch=original modal_scope=retained");
}
bool virtualDirectionScope(BYTE* root){
 if(!gui(root))return false;
 auto manager=*reinterpret_cast<BYTE**>(engine+0xf220c);
 if(readable(manager,0x40)&&*reinterpret_cast<int*>(manager+0x38)>0){auto node=*reinterpret_cast<BYTE**>(manager+0x3c);if(!readable(node,4))return false;root=*reinterpret_cast<BYTE**>(node);if(!gui(root))return false;}
 if(*reinterpret_cast<ULONG_PTR*>(root)==reinterpret_cast<ULONG_PTR>(engine+0xc2340)){
  auto title=*reinterpret_cast<BYTE**>(root+0x1a8);if(!readable(title,0x74)||*reinterpret_cast<int*>(title+0x70)!=4)return false;
 }
 int w=*reinterpret_cast<int*>(engine+0xf1b48),h=*reinterpret_cast<int*>(engine+0xf1b4c);if(w<=0||h<=0)return false;
 float x=float(*reinterpret_cast<int*>(engine+0xf20b0)),y=float(*reinterpret_cast<int*>(engine+0xf20a8));
 std::vector<modern_input::FocusTarget> targets;std::set<BYTE*> seen;bool native=false;collect(root,targets,seen,x,y,w,h,native);
 return !native&&!targets.empty();
}
void cancelPressedButtons(BYTE* p,std::set<BYTE*>& seen){
 if(!gui(p)||seen.size()>=256||!seen.insert(p).second)return;
 std::set<BYTE*> chain;auto child=*reinterpret_cast<BYTE**>(p+0x18);
 for(;child&&chain.size()<128&&readable(child,0x14)&&chain.insert(child).second;child=*reinterpret_cast<BYTE**>(child+0x10))cancelPressedButtons(child,seen);
 // Only the verified native button layout. The helper clears visual press state
 // without calling the release listener or requesting a menu action.
 if(*reinterpret_cast<ULONG_PTR*>(p)==reinterpret_cast<ULONG_PTR>(engine+0xbee80)&&readable(p,0x1a8)&&*reinterpret_cast<int*>(p+0x19c)){
  reinterpret_cast<void(__thiscall*)(void*)>(engine+0x5718f)(p);
 }
}
void cancelMenuRoot(void* root){std::set<BYTE*> seen;cancelPressedButtons(static_cast<BYTE*>(root),seen);}
int __fastcall dispatchHook(void* root,void*){
 bool outer=depth++==0;int result=0;
 auto input=outer?modernGamepadNavigation():GamepadNavigation{};
 bool mask=false;unsigned directions=0;
 const int arrows[]={VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT};int savedCounters[4]{};BYTE savedKeys[4]{};
 __try {if(outer){
   bool owns=input.active&&(maskedSerial==input.serial||virtualDirectionScope(static_cast<BYTE*>(root)));
   directions=owns?(input.held|previousVirtualDirections|(maskedSerial==input.serial?maskedDirections:0)):0;
   if(input.serial!=lastDirectionSerial){lastDirectionSerial=input.serial;previousVirtualDirections=owns?input.held:0;}
   mask=directions!=0;
  }
  if(mask){maskedSerial=input.serial;maskedDirections=directions;for(unsigned i=0;i<4;++i){if(!(directions&(1u<<i)))continue;int k=arrows[i];savedCounters[i]=*reinterpret_cast<int*>(engine+0xf1c9c+k*4);savedKeys[i]=engine[0xf1b94+k];*reinterpret_cast<int*>(engine+0xf1c9c+k*4)=0;engine[0xf1b94+k]&=0x7f;}}
  if(outer&&modernGamepadMenuCancellation())cancelMenuRoot(root);
  if(outer){traceClick(static_cast<BYTE*>(root),input.serial);navigate(static_cast<BYTE*>(root));}result=original(root);
  // Original return 1 means native input consumed, including keyboard-only roots
  // with no directional hit target. Do not navigate a second root for that serial.
  if(outer&&result==1&&input.active)consumed=input.serial;
 }
 __finally {if(mask)for(unsigned i=0;i<4;++i){if(!(directions&(1u<<i)))continue;int k=arrows[i];*reinterpret_cast<int*>(engine+0xf1c9c+k*4)=savedCounters[i];engine[0xf1b94+k]=savedKeys[i];}--depth;}
 return result;
}
void traceCursorDraw(void* value,bool skip){
 if(!trace||!readable(value,0x11c))return;
 auto p=static_cast<BYTE*>(value);CursorObservation o{};
 o.x=*reinterpret_cast<int*>(engine+0xf20b0);o.y=*reinterpret_cast<int*>(engine+0xf20a8);o.inputHidden=skip;
 o.nativeBlock=*reinterpret_cast<int*>(p+0x114);o.nativeOrder=*reinterpret_cast<int*>(p+0x118);
 o.spriteX=*reinterpret_cast<float*>(p+0x24);o.spriteY=*reinterpret_cast<float*>(p+0x28);
 o.finite=std::isfinite(o.spriteX)&&std::isfinite(o.spriteY);if(!o.finite)o.spriteX=o.spriteY=0;
 if(cursorTraceKnown&&lastCursorObject==value&&!memcmp(&o,&lastCursorObservation,sizeof(o)))return;
 cursorTraceKnown=true;lastCursorObject=value;lastCursorObservation=o;
 if(cursorTraceEvents>=64){if(!cursorTraceLimited){cursorTraceLimited=true;trace(L"INPUT_CURSOR_TRACE_LIMIT events=64 further_cursor_events=omitted");}return;}
 ++cursorTraceEvents;wchar_t line[384];
 swprintf_s(line,L"INPUT_CURSOR_DRAW decision=%ls x=%d y=%d sprite_x=%.3f sprite_y=%.3f sprite_finite=%d native_block=%d native_order=%d native_blocked=%d observation=draw_entry pixels=not_observed",
 skip?L"skip":L"original",o.x,o.y,double(o.spriteX),double(o.spriteY),o.finite,o.nativeBlock,o.nativeOrder,o.nativeBlock!=0||o.nativeOrder!=0);trace(line);
}
void __fastcall cursorDrawHook(void* value,void*){
 // Suppress only actual sprite submission (+0xc), never position preparation (+0x18).
 // Other instances of the shared sprite class keep their original drawing.
 if(value==*reinterpret_cast<void**>(engine+0xf2388)){
  bool skip=modernGamepadCursorHidden();traceCursorDraw(value,skip);if(skip)return;
 }
 originalCursorDraw(value);
}
bool write(DWORD* p,DWORD from,DWORD to){if(*p!=from)return false;DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;bool good=InterlockedCompareExchange(reinterpret_cast<LONG*>(p),to,from)==static_cast<LONG>(from);DWORD ignored;if(!VirtualProtect(p,4,old,&ignored)){if(good)InterlockedCompareExchange(reinterpret_cast<LONG*>(p),from,to);VirtualProtect(p,4,old,&ignored);return false;}return good;}
bool set(BYTE* p,bool enabled,void(*logger)(const wchar_t*),bool dry=false){
 if(!readable(p,0x10b000)||memcmp(p+0x55134,prefix,sizeof(prefix))||memcmp(p+0x5718f,cancelPrefix,sizeof(cancelPrefix)))return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 if(memcmp(p+0x38c24,prefix,sizeof(prefix))||memcmp(p+0x48774,cancelPrefix,sizeof(cancelPrefix)))return false;
 if(*reinterpret_cast<DWORD*>(p+0xbe38c)!=reinterpret_cast<DWORD>(p+0x38c24))return false;
 for(auto r:slots)if(*reinterpret_cast<DWORD*>(p+r+0x14)!=reinterpret_cast<DWORD>(p+0x5663f))return false;
 DWORD drawBase=reinterpret_cast<DWORD>(p+0x48774),drawHook=reinterpret_cast<DWORD>(&cursorDrawHook);
 DWORD base=reinterpret_cast<DWORD>(p+0x55134),hook=reinterpret_cast<DWORD>(&dispatchHook);
 bool allBase=true,allHook=true;for(auto r:slots){auto v=*reinterpret_cast<DWORD*>(p+r);allBase&=v==base;allHook&=v==hook;}
 allBase&=*reinterpret_cast<DWORD*>(p+0xbe380)==drawBase;allHook&=*reinterpret_cast<DWORD*>(p+0xbe380)==drawHook;
 if(!allBase&&!(allHook&&engine==p))return false;if(enabled&&allHook)return true;if(!enabled&&allBase)return true;
 if(dry)return true;
 if(enabled){engine=p;original=reinterpret_cast<Dispatch>(base);originalCursorDraw=reinterpret_cast<Draw>(drawBase);trace=logger;traceEvents=0;traceLimited=false;cursorTraceEvents=0;cursorTraceKnown=cursorTraceLimited=false;lastCursorObject=nullptr;}
 unsigned done=0;for(auto r:slots){if(!write(reinterpret_cast<DWORD*>(p+r),enabled?base:hook,enabled?hook:base)){for(unsigned i=0;i<done;++i)write(reinterpret_cast<DWORD*>(p+slots[i]),enabled?hook:base,enabled?base:hook);return false;}++done;}
 if(!write(reinterpret_cast<DWORD*>(p+0xbe380),enabled?drawBase:drawHook,enabled?drawHook:drawBase)){
  for(auto r:slots)write(reinterpret_cast<DWORD*>(p+r),enabled?hook:base,enabled?base:hook);return false;
 }
 if(enabled&&logger)logger(L"GAMEPAD_UI_READY source_classes=21 focus=directional native_arrow_controls=preserved cursor=virtual");return true;
}
}
bool installGamepadUi(HMODULE m,void(*logger)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(m),true,logger);}
bool removeGamepadUi(HMODULE m){return set(reinterpret_cast<BYTE*>(m),false,nullptr);}
bool canSetGamepadUi(HMODULE m,bool enabled){return set(reinterpret_cast<BYTE*>(m),enabled,nullptr,true);}
#ifdef MODERN_INPUT_TEST
void initializeGamepadUiFixture(BYTE* p){memcpy(p+0x38c24,prefix,sizeof(prefix));memcpy(p+0x48774,cancelPrefix,sizeof(cancelPrefix));*reinterpret_cast<DWORD*>(p+0xbe380)=reinterpret_cast<DWORD>(p+0x48774);*reinterpret_cast<DWORD*>(p+0xbe38c)=reinterpret_cast<DWORD>(p+0x38c24);memcpy(p+0x5718f,cancelPrefix,sizeof(cancelPrefix));memcpy(p+0x55134,prefix,sizeof(prefix));for(auto s:slots){*reinterpret_cast<DWORD*>(p+s)=reinterpret_cast<DWORD>(p+0x55134);*reinterpret_cast<DWORD*>(p+s+0x14)=reinterpret_cast<DWORD>(p+0x5663f);}}
#endif
