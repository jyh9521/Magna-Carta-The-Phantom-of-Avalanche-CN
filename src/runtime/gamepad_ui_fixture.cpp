#include "gamepad_ui.h"
#include "modern_gamepad.h"
#include <cstdio>
#include <cstring>
#include <cwchar>
static int checks=0,calls=0,originalResult=7;void require(bool v,const char* s){++checks;if(!v){fprintf(stderr,"FAIL %s\n",s);ExitProcess(1);}}
static BYTE* replayImage=nullptr;static bool inspectArrows=false;static int greenMoves=0;
static int focusRecords=0,clickRecords=0,traceLimits=0;static wchar_t lastFocus[512]{},lastClick[512]{};
void capture(const wchar_t* line){
 if(wcsncmp(line,L"INPUT_UI_FOCUS ",15)==0){++focusRecords;wcscpy_s(lastFocus,line);}
 if(wcsncmp(line,L"INPUT_UI_CLICK ",15)==0){++clickRecords;wcscpy_s(lastClick,line);}
 if(wcsncmp(line,L"INPUT_UI_TRACE_LIMIT ",21)==0)++traceLimits;
}
int __fastcall original(void*,void*){++calls;
 if(inspectArrows){const int arrows[]={VK_UP,VK_DOWN,VK_LEFT,VK_RIGHT};for(int k:arrows)if(*reinterpret_cast<int*>(replayImage+0xf1c9c+k*4)!=0||(replayImage[0xf1b94+k]&0x80))++greenMoves;}
return originalResult;}
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
 for(int i=0;i<3;++i){init(widgets[i]);*reinterpret_cast<unsigned*>(widgets[i]+4)=0x200+i;*reinterpret_cast<int**>(nodes[i])=rects[i];*reinterpret_cast<int*>(widgets[i]+0xf8)=1;*reinterpret_cast<BYTE**>(widgets[i]+0x100)=nodes[i];if(i<2)*reinterpret_cast<BYTE**>(widgets[i]+0x10)=widgets[i+1];}
 *reinterpret_cast<int*>(image+0xf1b48)=800;*reinterpret_cast<int*>(image+0xf1b4c)=600;auto x=reinterpret_cast<int*>(image+0xf20b0),y=reinterpret_cast<int*>(image+0xf20a8);*x=400;*y=300;*reinterpret_cast<BYTE**>(image+0xf220c)=manager;
 *reinterpret_cast<DWORD*>(image+0xbe38c)=1;
 require(!installGamepadUi(reinterpret_cast<HMODULE>(image),&capture),"unknown cursor preparation slot rejects render hook installation");
 require(*reinterpret_cast<DWORD*>(image+0xbe380)==reinterpret_cast<DWORD>(image+0x48774),"preparation guard rejects before writing render slot");
 *reinterpret_cast<DWORD*>(image+0xbe38c)=reinterpret_cast<DWORD>(image+0x38c24);
 auto admissionSlot=reinterpret_cast<DWORD*>(vt+0x1dc);*admissionSlot=reinterpret_cast<DWORD>(image+0x56640);
 require(!installGamepadUi(reinterpret_cast<HMODULE>(image),&capture),"unknown native admission implementation rejects before patching");
 require(*reinterpret_cast<DWORD*>(vt+0x1c8)==reinterpret_cast<DWORD>(image+0x55134),"admission guard rejection preserves original input slot");
 *admissionSlot=reinterpret_cast<DWORD>(image+0x5663f);
 require(installGamepadUi(reinterpret_cast<HMODULE>(image),&capture),"install all known classes");require(installGamepadUi(reinterpret_cast<HMODULE>(image),nullptr),"idempotence");
 require(*reinterpret_cast<DWORD*>(image+0xbe38c)==reinterpret_cast<DWORD>(image+0x38c24),"cursor preparation must remain original while render suppression uses its own slot");
 auto invoke=[&](GamepadNavigation n){configureModernNavigationFixture(image,n);return reinterpret_cast<int(__thiscall*)(void*)>(*reinterpret_cast<DWORD*>(vt+0x1c8))(root);};
 require(invoke({2,2,1,100,true})==7&&*x==400&&*y==420,"first downward focus and original dispatcher return");
 require(focusRecords==1&&wcsstr(lastFocus,L"target_id=200")&&wcsstr(lastFocus,L"root_class=bec88")&&wcsstr(lastFocus,L"to=400,420"),"selected target identity and native coordinates must be observable, not only first-use readiness");
 invoke({2,0,2,200,true});require(*y==420,"repeat initial delay");invoke({2,0,3,500,true});require(*y==470,"repeat advances after delay");invoke({2,2,4,700,true});require(*y==520,"next focus");invoke({2,2,5,800,true});require(*y==420,"wrap focus");
 require(calls==5,"original dispatcher once each call");
 *reinterpret_cast<int*>(widgets[1]+0x164)=2;invoke({2,2,4096,850,true});require(*y==520,"virtual focus must skip nonmodal input mode rejected by original native mouse eligibility");
 *reinterpret_cast<int*>(widgets[1]+0x164)=0;*y=420;
 *reinterpret_cast<int*>(widgets[1]+0x160)=0;invoke({2,2,6,900,true});require(*y==520,"disabled widgets skipped");*reinterpret_cast<int*>(widgets[1]+0x160)=1;
 *reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x12345);invoke({1,1,7,1000,true});require(*y==520,"native arrow consumer left untouched");*reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x55f3c);
 *reinterpret_cast<int*>(manager+0x38)=1;*reinterpret_cast<BYTE**>(manager+0x3c)=exclusive;*reinterpret_cast<BYTE**>(exclusive)=widgets[1];invoke({1,1,8,1100,true});require(*y==470,"exclusive modal restricts focus");
 BYTE modalChild[0x190]{},modalNode[8]{};int modalRect[]={300,550,500,590};init(modalChild);*reinterpret_cast<int**>(modalNode)=modalRect;*reinterpret_cast<BYTE**>(modalChild+0x100)=modalNode;
 *reinterpret_cast<BYTE**>(widgets[1]+0x18)=modalChild;*reinterpret_cast<int*>(widgets[1]+0x164)=2;*y=520;
 invoke({1,1,4097,1150,true});require(*y==470,"exclusive owner overrides local mode but its ordinary descendants must not steal virtual focus");
 *reinterpret_cast<BYTE**>(widgets[1]+0x18)=nullptr;*reinterpret_cast<int*>(widgets[1]+0x164)=0;
 printf("GAMEPAD_NATIVE_ADMISSION_REPLAY PASS nonmodal_mode2=skipped exact_modal_owner=admitted ordinary_descendant=rejected source_mouse_contract=matched game_started=false\n");
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
 invokeAt(inactiveRoot,{2,0,14,2000,true});require(*y==420,"inactive root leaves repeat focus unchanged");
 invokeAt(root,{2,0,14,2000,true});require(*y==470,"inactive root must not advance repeat clock before active menu handles direction");
 invokeAt(root,{2,0,14,2000,true});require(*y==470,"handled serial still moves focus at most once per frame");
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
 auto cursorSlot=*reinterpret_cast<DWORD*>(image+0xbe380);*reinterpret_cast<DWORD*>(image+0xbe380)=1;
 require(!removeGamepadUi(reinterpret_cast<HMODULE>(image)),"unknown cursor draw slot rejects all GUI rollback before writes");
 require(*reinterpret_cast<DWORD*>(vt+0x1c8)!=reinterpret_cast<DWORD>(image+0x55134),"cursor guard rejection keeps every GUI hook installed");
 *reinterpret_cast<DWORD*>(image+0xbe380)=cursorSlot;
 replayImage=image;inspectArrows=true;*x=400;*y=300;
 auto downCounter=reinterpret_cast<int*>(image+0xf1c9c+VK_DOWN*4);*downCounter=1;image[0xf1b94+VK_DOWN]=0x81;
 invokeAt(root,{2,2,21,2500,true});require(*y==420&&greenMoves==0,"virtual right menu navigation must not also drive native green-arrow keyboard control");
 require(*downCounter==1&&image[0xf1b94+VK_DOWN]==0x81,"original controller key counter and bytes restored exactly after dispatch");
 *downCounter=2;invokeAt(root,{2,0,22,2600,true});require(*y==420&&greenMoves==0,"held direction during repeat delay stays exclusive to virtual menu");
 *downCounter=-1;image[0xf1b94+VK_DOWN]=1;invokeAt(root,{0,0,23,2700,true});require(greenMoves==0&&*downCounter==-1,"synthetic arrow release remains exclusive and restores native counter");
 *downCounter=1;image[0xf1b94+VK_DOWN]=0x80;invokeAt(root,{2,2,24,2800,false});require(greenMoves==1,"physical keyboard priority bypasses controller direction mask");
 *reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x12345);*y=420;
 invokeAt(root,{2,2,25,2900,true});require(greenMoves==2&&*y==420,"focused native arrow control receives controller input without moving sidebar focus");
 *y=50;invokeAt(nativeRoot,{2,2,26,3000,true});require(*y==300&&greenMoves==2,"controller can enter native control without applying its arrow action on entry");
 invokeAt(nativeRoot,{2,2,26,3000,true});require(greenMoves==2,"same-frame second root cannot replay direction after virtual focus entry");
 invokeAt(nativeRoot,{2,0,27,3100,true});require(*y==300&&greenMoves==3,"next-frame focused native control owns direction without sidebar movement");
 *reinterpret_cast<DWORD*>(vt+0xd0)=reinterpret_cast<DWORD>(image+0x55f3c);*downCounter=0;image[0xf1b94+VK_DOWN]=0;inspectArrows=false;
 printf("GAMEPAD_DIRECTION_OWNER_REPLAY PASS sidebar=exclusive green_control=native repeat=exclusive release=exclusive physical_keyboard=preserved state_restore=exact game_started=false\n");
 auto leftState=reinterpret_cast<int*>(image+0xf1c9c+VK_LBUTTON*4);*leftState=1;
 invokeAt(root,{0,0,30,3200,true});require(clickRecords==1&&wcsstr(lastClick,L"left=1")&&wcsstr(lastClick,L"phase=before_mouse"),"click-edge evidence records merged native counter without claiming transition execution");
 require(*leftState==1,"event evidence must preserve click counter");*leftState=0;
 for(unsigned i=0;i<300;++i)invokeAt(root,{2,2,31+i,3300+i*40,true});
 require(focusRecords+clickRecords==256&&traceLimits==1,"bounded menu event evidence emits one explicit limit, never unbounded logs");
 printf("GAMEPAD_MENU_EVIDENCE_REPLAY PASS target_identity=true native_coordinates=true click_phase=before_mouse state=unchanged limit=256 limit_notice=once game_started=false\n");
 auto changed=*reinterpret_cast<DWORD*>(image+0xc2508);*reinterpret_cast<DWORD*>(image+0xc2508)=1;require(!removeGamepadUi(reinterpret_cast<HMODULE>(image)),"unknown slot rejects whole rollback");require(*reinterpret_cast<DWORD*>(vt+0x1c8)!=reinterpret_cast<DWORD>(image+0x55134),"rejection no partial restore");*reinterpret_cast<DWORD*>(image+0xc2508)=changed;
 require(removeGamepadUi(reinterpret_cast<HMODULE>(image)),"rollback");require(*reinterpret_cast<DWORD*>(vt+0x1c8)==reinterpret_cast<DWORD>(image+0x55134),"exact original dispatcher slot");
 require(*reinterpret_cast<DWORD*>(image+0xbe38c)==reinterpret_cast<DWORD>(image+0x38c24),"exact original cursor preparation slot restored");
 require(*reinterpret_cast<DWORD*>(image+0xbe380)==reinterpret_cast<DWORD>(image+0x48774),"exact original cursor render slot restored");
 VirtualFree(image,0,MEM_RELEASE);printf("GAMEPAD_UI_FIXTURE PASS checks=%d native_rects=true directional=true modal=true original_dispatch=true rollback=exact game_started=false\n",checks);
}
