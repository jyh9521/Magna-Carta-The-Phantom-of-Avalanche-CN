#include "gamepad_ui.h"
#include "modern_gamepad.h"
#include "ui_focus.h"
#include <array>
#include <vector>
#include <set>
#include <cmath>
#include <cstring>
namespace {
constexpr unsigned slots[]={0xbee50,0xbf048,0xbf240,0xbf438,0xbf630,0xbf828,0xbfa20,0xbfc18,0xbfeb4,0xc00ac,0xc02a4,0xc049c,0xc06b0,0xc08c4,0xc0adc,0xc0cf0,0xc1560,0xc1da8,0xc1fa0,0xc2204,0xc2508};
constexpr BYTE prefix[]={0x55,0x8b,0xec,0x83,0xec,0x08,0x89,0x4d,0xf8};
using Dispatch=int(__thiscall*)(void*);Dispatch original=nullptr;BYTE* engine=nullptr;
thread_local unsigned depth=0;DWORD consumed=0,lastRepeat=0;unsigned previousHeld=0;void(*trace)(const wchar_t*)=nullptr;
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
bool collect(BYTE* p,std::vector<modern_input::FocusTarget>& out,std::set<BYTE*>& visited,float x,float y,int w,int h,bool& nativeArrowControl){
 if(!gui(p)||visited.size()>=256||!visited.insert(p).second||!*reinterpret_cast<int*>(p+0xe8)||!*reinterpret_cast<int*>(p+0x160))return false;
 auto child=*reinterpret_cast<BYTE**>(p+0x18);bool eligibleChild=false;std::set<BYTE*> chain;
 for(;child&&chain.size()<128&&readable(child,0x14)&&chain.insert(child).second;child=*reinterpret_cast<BYTE**>(child+0x10))if(gui(child)){
  // Native eligibility requires visible+enabled. Inactive decoration must not
  // hide the parent; every eligible child keeps the existing dispatch priority.
  bool eligible=collect(child,out,visited,x,y,w,h,nativeArrowControl);eligibleChild=eligibleChild||eligible;
 }
 if(eligibleChild||!*reinterpret_cast<void**>(p+0x17c))return true;
 // +f8 is the list object. GetFirst (RVA 02014) reads its +8 head;
 // dereferencing the container itself mistakes its count for a pointer.
 auto node=*reinterpret_cast<BYTE**>(p+0x100);float ox=*reinterpret_cast<float*>(p+0x24),oy=*reinterpret_cast<float*>(p+0x28);
 if(!std::isfinite(ox)||!std::isfinite(oy)||std::abs(ox)>100000||std::abs(oy)>100000)return true;
 chain.clear();for(;node&&chain.size()<32&&readable(node,8)&&chain.insert(node).second;node=*reinterpret_cast<BYTE**>(node+4)){
  auto rect=*reinterpret_cast<int**>(node);if(!readable(rect,16))break;
  modern_input::FocusTarget r{reinterpret_cast<uintptr_t>(p),float(rect[0])+ox,float(rect[1])+oy,float(rect[2])+ox,float(rect[3])+oy};
  if(r.right-r.left<4||r.bottom-r.top<4||r.right-r.left>w*.8f||r.bottom-r.top>h*.8f||r.left<0||r.top<0||r.right>w||r.bottom>h)continue;
  if(!defaultArrows(p)){if(x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom)nativeArrowControl=true;continue;}
  if(out.size()<128)out.push_back(r);
 }
 return true;
}
void navigate(BYTE* root){
 auto n=modernGamepadNavigation();if(!n.active||n.serial==consumed)return;consumed=n.serial;
 unsigned held=n.held&15;bool fresh=(n.pressed&15)!=0;
 if(!held){previousHeld=0;return;}
 if(held!=previousHeld){fresh=true;previousHeld=held;lastRepeat=n.time;}
 else if(!fresh&&DWORD(n.time-lastRepeat)<350)return;
 if(!fresh)lastRepeat=n.time-250;else lastRepeat=n.time;
 if(!gui(root))return;
 // The exclusive stack selects the actual modal, not widgets hidden behind it.
 auto manager=*reinterpret_cast<BYTE**>(engine+0xf220c);
 if(readable(manager,0x40)&&*reinterpret_cast<int*>(manager+0x38)>0){auto node=*reinterpret_cast<BYTE**>(manager+0x3c);if(!readable(node,4))return;root=*reinterpret_cast<BYTE**>(node);if(!gui(root))return;}
 if(*reinterpret_cast<ULONG_PTR*>(root)==reinterpret_cast<ULONG_PTR>(engine+0xc2340)){
  auto title=*reinterpret_cast<BYTE**>(root+0x1a8);if(!readable(title,0x74)||*reinterpret_cast<int*>(title+0x70)!=4)return;
 }
 int w=*reinterpret_cast<int*>(engine+0xf1b48),h=*reinterpret_cast<int*>(engine+0xf1b4c);if(w<=0||h<=0)return;
 float x=float(*reinterpret_cast<int*>(engine+0xf20b0)),y=float(*reinterpret_cast<int*>(engine+0xf20a8));
 std::vector<modern_input::FocusTarget> targets;std::set<BYTE*> seen;bool native=false;collect(root,targets,seen,x,y,w,h,native);if(native)return;
 int dx=(held&4)?-1:(held&8)?1:0,dy=(held&1)?-1:(held&2)?1:0;if(dy)dx=0;
 int index=modern_input::chooseFocus(targets,x,y,dx,dy);if(index<0)return;const auto& r=targets[index];
 modernGamepadFocusCursor((r.left+r.right)*.5f,(r.top+r.bottom)*.5f);
 static LONG calls=0;if(InterlockedIncrement(&calls)==1&&trace)trace(L"GAMEPAD_UI_FOCUS_APPLIED native_hit_rects=true click_dispatch=original modal_scope=retained");
}
int __fastcall dispatchHook(void* root,void*){
 bool outer=depth++==0;int result=0;
 __try {if(outer)navigate(static_cast<BYTE*>(root));result=original(root);}
 __finally {--depth;}
 return result;
}
bool write(DWORD* p,DWORD from,DWORD to){if(*p!=from)return false;DWORD old;if(!VirtualProtect(p,4,PAGE_READWRITE,&old))return false;bool good=InterlockedCompareExchange(reinterpret_cast<LONG*>(p),to,from)==static_cast<LONG>(from);DWORD ignored;if(!VirtualProtect(p,4,old,&ignored)){if(good)InterlockedCompareExchange(reinterpret_cast<LONG*>(p),from,to);VirtualProtect(p,4,old,&ignored);return false;}return good;}
bool set(BYTE* p,bool enabled,void(*logger)(const wchar_t*),bool dry=false){
 if(!readable(p,0x10b000)||memcmp(p+0x55134,prefix,sizeof(prefix)))return false;
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(p);if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>4096)return false;
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+dos->e_lfanew);if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||nt->OptionalHeader.SizeOfImage!=0x10b000)return false;
 DWORD base=reinterpret_cast<DWORD>(p+0x55134),hook=reinterpret_cast<DWORD>(&dispatchHook);
 bool allBase=true,allHook=true;for(auto r:slots){auto v=*reinterpret_cast<DWORD*>(p+r);allBase&=v==base;allHook&=v==hook;}
 if(!allBase&&!(allHook&&engine==p))return false;if(enabled&&allHook)return true;if(!enabled&&allBase)return true;
 if(dry)return true;
 if(enabled){engine=p;original=reinterpret_cast<Dispatch>(base);trace=logger;}
 unsigned done=0;for(auto r:slots){if(!write(reinterpret_cast<DWORD*>(p+r),enabled?base:hook,enabled?hook:base)){for(unsigned i=0;i<done;++i)write(reinterpret_cast<DWORD*>(p+slots[i]),enabled?hook:base,enabled?base:hook);return false;}++done;}
 if(enabled&&logger)logger(L"GAMEPAD_UI_READY source_classes=21 focus=directional native_arrow_controls=preserved cursor=virtual");return true;
}
}
bool installGamepadUi(HMODULE m,void(*logger)(const wchar_t*)){return set(reinterpret_cast<BYTE*>(m),true,logger);}
bool removeGamepadUi(HMODULE m){return set(reinterpret_cast<BYTE*>(m),false,nullptr);}
bool canSetGamepadUi(HMODULE m,bool enabled){return set(reinterpret_cast<BYTE*>(m),enabled,nullptr,true);}
#ifdef MODERN_INPUT_TEST
void initializeGamepadUiFixture(BYTE* p){memcpy(p+0x55134,prefix,sizeof(prefix));for(auto s:slots)*reinterpret_cast<DWORD*>(p+s)=reinterpret_cast<DWORD>(p+0x55134);}
#endif
