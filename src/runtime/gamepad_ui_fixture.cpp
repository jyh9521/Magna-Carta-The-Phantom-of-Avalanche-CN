#include "gamepad_ui.h"
#include "modern_gamepad.h"
#include <cstdio>
#include <cstring>
static int checks=0,calls=0,originalResult=7;void require(bool v,const char* s){++checks;if(!v){fprintf(stderr,"FAIL %s\n",s);ExitProcess(1);}}
int __fastcall original(void*,void*){++calls;return originalResult;}
int main(){
 auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));require(image!=nullptr,"owned allocation");
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 initializeGamepadUiFixture(image);auto p=image+0x55134+9;*p++=0x8b;*p++=0xe5;*p++=0x5d;*p++=0xe9;*reinterpret_cast<int32_t*>(p)=static_cast<int32_t>(reinterpret_cast<ULONG_PTR>(&original)-reinterpret_cast<ULONG_PTR>(p+4));
 unsigned base=0xbee50-0x1c8;auto vt=image+base;
 // Shipped base GUI forwards arrow events to its listener (not the no-op methods).
 *reinterpret_cast<DWORD*>(vt+0xc8)=reinterpret_cast<DWORD>(image+0x55f0a);*reinterpret_cast<DWORD*>(vt+0xcc)=reinterpret_cast<DWORD>(image+0x55f23);*reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x55f3c);*reinterpret_cast<DWORD*>(vt+0xd4)=reinterpret_cast<DWORD>(image+0x55f55);
 BYTE root[0x190]{},widgets[3][0x190]{},nodes[3][8]{},manager[0x40]{},exclusive[8]{};int rects[3][4]={{300,400,500,440},{300,450,500,490},{300,500,500,540}};
 auto init=[&](BYTE* g){*reinterpret_cast<BYTE**>(g)=vt;*reinterpret_cast<int*>(g+0xe8)=1;*reinterpret_cast<int*>(g+0x160)=1;*reinterpret_cast<BYTE**>(g+0x17c)=root;};init(root);*reinterpret_cast<BYTE**>(root+0x18)=widgets[0];
 // +f8 is the list object, not its head. The engine's GetFirst accessor
 // reads list+8; a nonzero count must never be mistaken for a node pointer.
 for(int i=0;i<3;++i){init(widgets[i]);*reinterpret_cast<int**>(nodes[i])=rects[i];*reinterpret_cast<int*>(widgets[i]+0xf8)=1;*reinterpret_cast<BYTE**>(widgets[i]+0x100)=nodes[i];if(i<2)*reinterpret_cast<BYTE**>(widgets[i]+0x10)=widgets[i+1];}
 *reinterpret_cast<int*>(image+0xf1b48)=800;*reinterpret_cast<int*>(image+0xf1b4c)=600;auto x=reinterpret_cast<int*>(image+0xf20b0),y=reinterpret_cast<int*>(image+0xf20a8);*x=400;*y=300;*reinterpret_cast<BYTE**>(image+0xf220c)=manager;
 require(installGamepadUi(reinterpret_cast<HMODULE>(image),nullptr),"install all known classes");require(installGamepadUi(reinterpret_cast<HMODULE>(image),nullptr),"idempotence");
 auto invoke=[&](GamepadNavigation n){configureModernNavigationFixture(image,n);return reinterpret_cast<int(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(vt+0x1c8))(root);};
 require(invoke({2,2,1,100,true})==7&&*x==400&&*y==420,"first downward focus and original dispatcher return");
 invoke({2,0,2,200,true});require(*y==420,"repeat initial delay");invoke({2,0,3,450,true});require(*y==470,"repeat advances after delay");invoke({2,2,4,700,true});require(*y==520,"next focus");invoke({2,2,5,800,true});require(*y==420,"wrap focus");
 require(calls==5,"original dispatcher once each call");
 *reinterpret_cast<int*>(widgets[1]+0x160)=0;invoke({2,2,6,900,true});require(*y==520,"disabled widgets skipped");*reinterpret_cast<int*>(widgets[1]+0x160)=1;
 *reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x12345);invoke({1,1,7,1000,true});require(*y==520,"native arrow consumer left untouched");*reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x55f3c);
 *reinterpret_cast<int*>(manager+0x38)=1;*reinterpret_cast<BYTE**>(manager+0x3c)=exclusive;*reinterpret_cast<BYTE**>(exclusive)=widgets[1];invoke({1,1,8,1100,true});require(*y==470,"exclusive modal restricts focus");
 *reinterpret_cast<int*>(manager+0x38)=0;BYTE decoration[0x190]{};init(decoration);*reinterpret_cast<void**>(decoration+0x17c)=nullptr;*reinterpret_cast<int*>(decoration+0x160)=0;
 *reinterpret_cast<BYTE**>(widgets[0]+0x18)=decoration;*x=400;*y=300;
 invoke({2,2,9,1200,true});require(*y==420,"decorative GUI child cannot hide actionable parent button");
 *reinterpret_cast<int*>(decoration+0x160)=1;*reinterpret_cast<int*>(decoration+0xe8)=0;*y=300;invoke({2,2,10,1300,true});require(*y==420,"hidden decorative child cannot hide actionable parent button");
 *reinterpret_cast<int*>(decoration+0xe8)=1;*y=300;invoke({2,2,11,1400,true});require(*y==470,"eligible child without listener still preserves native dispatcher priority");
 *reinterpret_cast<void**>(decoration+0x17c)=root;
 BYTE childNode[8]{};int childRect[]={300,550,500,590};*reinterpret_cast<int**>(childNode)=childRect;*reinterpret_cast<BYTE**>(decoration+0x100)=childNode;
 *y=300;invoke({2,2,12,1500,true});require(*y==470,"actionable descendant retains container focus ownership");
 *reinterpret_cast<BYTE**>(widgets[0]+0x18)=nullptr;
 BYTE inactiveRoot[0x190]{};init(inactiveRoot);*reinterpret_cast<int*>(inactiveRoot+0x160)=0;
 auto invokeAt=[&](BYTE* target,GamepadNavigation n){configureModernNavigationFixture(image,n);return reinterpret_cast<int(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(vt+0x1c8))(target);};
 *x=400;*y=300;invokeAt(inactiveRoot,{2,2,13,1600,true});require(*y==300,"inactive root leaves focus unchanged");
 invokeAt(root,{2,2,13,1600,true});require(*y==420,"inactive root must not consume same-frame direction intended for active menu");
 invokeAt(inactiveRoot,{2,0,14,1950,true});require(*y==420,"inactive root leaves repeat focus unchanged");
 invokeAt(root,{2,0,14,1950,true});require(*y==470,"inactive root must not advance repeat clock before active menu handles direction");
 invokeAt(root,{2,0,14,1950,true});require(*y==470,"handled serial still moves focus at most once per frame");
 *reinterpret_cast<int*>(root+0x160)=0;*y=300;invokeAt(root,{2,2,15,2000,true});
 require(*y==420,"inactive parent must retain active descendant navigation like native child-first dispatcher");
 *reinterpret_cast<int*>(root+0x160)=1;*reinterpret_cast<int*>(root+0xe8)=0;*y=300;invokeAt(root,{2,2,16,2100,true});
 require(*y==420,"hidden parent does not discard separately active descendants from native dispatch tree");*reinterpret_cast<int*>(root+0xe8)=1;
 BYTE opaqueRoot[0x190]{};init(opaqueRoot);*reinterpret_cast<void**>(opaqueRoot+0x17c)=nullptr;*y=300;originalResult=1;
 require(invokeAt(opaqueRoot,{2,2,17,2200,true})==1&&*y==300,"native consumed root preserves original result without artificial focus target");originalResult=7;
 invokeAt(root,{2,2,17,2200,true});require(*y==300,"native consumed root prevents second navigation in same input frame");
 originalResult=0;invokeAt(inactiveRoot,{2,2,18,2300,true});originalResult=7;
 invokeAt(root,{2,2,18,2300,true});require(*y==420,"native declined root leaves same-frame navigation available");
 BYTE nativeRoot[0x190]{},nativeNode[8]{};int nativeRect[]={300,250,500,350};init(nativeRoot);
 *reinterpret_cast<int**>(nativeNode)=nativeRect;*reinterpret_cast<BYTE**>(nativeRoot+0x100)=nativeNode;*reinterpret_cast<int*>(nativeRoot+0x164)=1;
 *reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x12345);*y=300;originalResult=0;
 require(invokeAt(nativeRoot,{2,2,19,2400,true})==0&&*y==300,"blocked native arrow root preserves original decline and cursor");
 *reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x55f3c);originalResult=7;
 invokeAt(root,{2,2,19,2400,true});require(*y==420,"declined native arrow root cannot consume another menu direction");
 auto changed=*reinterpret_cast<DWORD*>(image+0xc2508);*reinterpret_cast<DWORD*>(image+0xc2508)=1;require(!removeGamepadUi(reinterpret_cast<HMODULE>(image)),"unknown slot rejects whole rollback");require(*reinterpret_cast<DWORD*>(vt+0x1c8)!=reinterpret_cast<DWORD>(image+0x55134),"rejection no partial restore");*reinterpret_cast<DWORD*>(image+0xc2508)=changed;
 require(removeGamepadUi(reinterpret_cast<HMODULE>(image)),"rollback");require(*reinterpret_cast<DWORD*>(vt+0x1c8)==reinterpret_cast<DWORD>(image+0x55134),"exact original dispatcher slot");
 VirtualFree(image,0,MEM_RELEASE);printf("GAMEPAD_UI_FIXTURE PASS checks=%d native_rects=true directional=true modal=true original_dispatch=true rollback=exact game_started=false\n",checks);
}
