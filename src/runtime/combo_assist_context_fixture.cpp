// Owned white-box regression driver for production keyboard routing; no game modules load.
#include "modern_gamepad.cpp"
#include <cstdio>
#include <initializer_list>
static WORD fixtureButtons=0;static bool fixtureF10=false;static unsigned fixtureDevice=0;
static BOOL WINAPI fixtureKeyboard(PBYTE k){memset(k,0,256);if(fixtureF10)k[VK_F10]=0x80;return TRUE;}
static DWORD WINAPI fixturePoll(DWORD slot,XINPUT_STATE* s){if(slot!=fixtureDevice)return ERROR_DEVICE_NOT_CONNECTED;*s={};s->Gamepad.wButtons=fixtureButtons;return ERROR_SUCCESS;}
int main(){
 engine=(BYTE*)VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);battleReady=true;nativeRouting=true;gameWindow=(HWND*)(engine+0xf1b44);
 BYTE scene[0x1e04]{},gui[0x1c0]{},config[4]{};*(BYTE**)scene=engine+0xc1960;*(BYTE**)(scene+0x10fc)=gui;*(BYTE**)gui=engine+0xc203c;*(BYTE**)(gui+0x1bc)=scene;*(BYTE**)(engine+0xf2428)=config;
 BYTE getter[]={0x8b,0x44,0x24,0x04,0x83,0xf8,0x23,0xb8,10,0,0,0,0x74,0x05,0xb8,4,0,0,0,0xc2,4,0};memcpy(engine+0xb5b0e,getter,sizeof getter);
 BYTE* outer[2]={scene,nullptr};BYTE* f[2]={(BYTE*)&outer[1],engine+0xa0b92};BYTE keys[256];unsigned failed=0,checks=0;
 auto step=[&](){modernBattleKeyboardFixture(keys,f);};
 auto verify=[&](bool ok,const char* name){++checks;printf("%s %s space=%u pending=%u pad_owned=%u\n",ok?"PASS":"FAIL",name,!!(keys[VK_SPACE]&0x80),comboAssist.pending(),assistPadOwned);if(!ok)++failed;};
 auto reset=[&](){comboAssist=combat_input::ComboAssist();router=modern_input::Router();padContext.reset();spaceEdges.clear();edgeScene=nullptr;assistPadOwned=false;fixtureButtons=0;fixtureF10=false;fixtureDevice=0;selected=0xffffffff;*(unsigned*)(gui+0x190)=1;*(int*)(scene+0x1dc4)=1;*(int*)(scene+0x1dcc)=1;*(unsigned*)(scene+0x1ddc)=1;*(unsigned*)(scene+0x1de0)=5;configureModernGamepadFixture(fixtureKeyboard,fixturePoll,true);step();step();};
 for(WORD manual:{WORD(XINPUT_GAMEPAD_A),WORD(XINPUT_GAMEPAD_X)}){
  reset();fixtureButtons=manual;step();fixtureButtons|=XINPUT_GAMEPAD_RIGHT_THUMB;step();verify(!comboAssist.pending()&&(keys[VK_SPACE]&0x80),manual==XINPUT_GAMEPAD_A?"held_A_blocks_R3":"held_X_blocks_R3");
  reset();fixtureButtons=XINPUT_GAMEPAD_RIGHT_THUMB;step();verify(comboAssist.pending(),"R3_request_armed");fixtureButtons=manual;*(unsigned*)(scene+0x1de0)=6;step();verify(!comboAssist.pending()&&(keys[VK_SPACE]&0x80),manual==XINPUT_GAMEPAD_A?"A_manual_takeover_cancels":"X_manual_takeover_cancels");
 }
 for(unsigned mode:{4u,7u,99u}){
  reset();fixtureButtons=XINPUT_GAMEPAD_RIGHT_THUMB;step();*(unsigned*)(gui+0x190)=mode;fixtureButtons=0;*(unsigned*)(scene+0x1de0)=11;step();verify(!comboAssist.pending()&&!(keys[VK_SPACE]&0x80),mode==4?"pad_mode_menu_cancel":mode==7?"pad_mode_result_cancel":"pad_mode_blocked_cancel");
  reset();fixtureF10=true;step();*(unsigned*)(gui+0x190)=mode;fixtureF10=false;*(unsigned*)(scene+0x1de0)=11;step();verify(!comboAssist.pending()&&!(keys[VK_SPACE]&0x80),mode==4?"F10_mode_menu_cancel":mode==7?"F10_mode_result_cancel":"F10_mode_blocked_cancel");
 }
 reset();fixtureButtons=XINPUT_GAMEPAD_RIGHT_THUMB;step();fixtureDevice=1;fixtureButtons=0;*(unsigned*)(scene+0x1de0)=11;step();verify(!comboAssist.pending()&&!(keys[VK_SPACE]&0x80),"pad_device_switch_cancel");
 reset();fixtureF10=true;step();fixtureF10=false;*(unsigned*)(scene+0x1de0)=11;step();*(unsigned*)(scene+0x1ddc)=2;*(unsigned*)(scene+0x1de0)=12;step();*(unsigned*)(scene+0x1ddc)=1;*(unsigned*)(scene+0x1de0)=1;step();verify(!comboAssist.pending(),"same_scene_attack_regression_cancel");
 printf("COMBO_ASSIST_CONTEXT checks=%u failures=%u game_started=false commercial_dll_loaded=false\n",checks,failed);return failed?1:0;
}
