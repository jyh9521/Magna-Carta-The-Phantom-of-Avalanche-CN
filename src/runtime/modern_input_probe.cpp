#include "modern_input.h"
#include <windows.h>
#include <Xinput.h>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace modern_input;
static int checks=0;
static void check(bool value){++checks;if(!value)throw std::runtime_error("input regression failed");}
static void arm(Router& r,Sample s){r.update(s,true,true);check(r.update(s,true,true).armed);}
static void fixture() {
    Sample s; s.connected=true;Router r;arm(r,s);
    s.buttons=0x1000;auto f=r.update(s,true,true);check(f.held==Confirm&&f.pressed==Confirm);
    f=r.update(s,true,true);check(f.held==Confirm&&f.pressed==0);
    f=r.update(s,true,false);check(f.held==0&&f.released==Confirm&&!f.armed);
    check(r.update(s,true,true).held==0);check(r.update(s,true,true).held==0);
    s.buttons=0;check(r.update(s,true,true).armed);
    s.buttons=0x1000;check(r.update(s,true,true).pressed==Confirm);
    s.connected=false;f=r.update(s,true,true);check(f.released==Confirm&&!f.armed);
    s.connected=true;check(!r.update(s,true,true).armed);check(r.update(s,true,true).held==0);
    s.buttons=0;check(r.update(s,true,true).armed);
    s.x=16000;check(r.update(s,true,true).held==Right);
    s.x=12000;check(r.update(s,true,true).held==Right);
    s.x=10000;check(r.update(s,true,true).held==0);
    s.x=-32768;check(r.update(s,true,true).held==Left);
    s.buttons=8;check(r.update(s,true,true).held==0);
    s.buttons=0;s.x=0;s.y=32767;check(r.update(s,true,true).held==Up);
    f=r.update(s,false,true);check(f.released==Up&&f.held==0);
    check(r.update(s,true,true).held==0);check(r.update(s,true,true).held==0);
    s.y=0;check(r.update(s,true,true).armed);
    s.buttons=0x2000;check(r.update(s,true,true).held==Cancel);
    s.device=1;f=r.update(s,true,true);check(f.released==Cancel&&!f.armed);
    check(r.update(s,true,true).held==0);s.buttons=0;check(r.update(s,true,true).armed);
    Router mapped({16000,10000,0x2000,0x1000,0x20});arm(mapped,s);
    s.buttons=0x2000;check(mapped.update(s,true,true).held==Confirm);
    uint8_t keys[258]{};keys[0]=0x55;keys[257]=0xaa;keys[1+32]=1;keys[1+65]=0x80;
    const uint8_t binding[7]={38,40,37,39,32,27,0};
    mergeKeyboard(keys+1,{Confirm,Confirm,0,true},binding);
    check(keys[1+32]==0x81&&keys[1+65]==0x80&&keys[0]==0x55&&keys[257]==0xaa);
    mergeKeyboard(keys+1,{},binding);check(keys[1+32]==0x81);
    for(auto c:{Config{10000,10000},Config{16000,0},Config{16000,10000,0x1000,0x1000},Config{16000,10000,1,0x2000}}){
        bool rejected=false;try{Router bad(c);}catch(const std::invalid_argument&){rejected=true;}check(rejected);
    }
    // Exhaustive signed-axis extremes and all button bits; loss of focus always releases.
    for(int value=-32768;value<=32767;++value){
        Router fuzz;s={true,0,0,0,0};arm(fuzz,s);s.x=static_cast<int16_t>(value);s.y=static_cast<int16_t>(value);
        f=fuzz.update(s,true,true);check((f.held&~(Up|Down|Left|Right))==0);
        auto off=fuzz.update(s,true,false);check(off.held==0&&off.released==f.held);
    }
    for(unsigned value=0;value<=0xffff;++value){
        Router fuzz;s={true,0,0,0,0};arm(fuzz,s);s.buttons=static_cast<uint16_t>(value);
        f=fuzz.update(s,true,true);check((f.held&~127u)==0);
        check((f.held&(Up|Down))!=(Up|Down));check((f.held&(Left|Right))!=(Left|Right));
    }
    std::cout<<"MODERN_INPUT_FIXTURE PASS checks="<<checks<<" focus_release=true neutral_rearm=true disconnect=true device_switch=true remap=true hysteresis=true axes=65536 buttons=65536 game_started=false injection=false\n";
}
static void snapshot() {
    auto module=LoadLibraryExW(L"xinput1_4.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!module)throw std::runtime_error("system XInput 1.4 unavailable");
    using Poll=DWORD(WINAPI*)(DWORD,XINPUT_STATE*);
    auto poll=reinterpret_cast<Poll>(GetProcAddress(module,"XInputGetState"));
    if(!poll){FreeLibrary(module);throw std::runtime_error("XInputGetState missing");}
    unsigned count=0;
    std::cout<<"{\"backend\":\"xinput1_4\",\"slots\":[";
    for(DWORD i=0;i<4;++i){
        XINPUT_STATE s{};auto result=poll(i,&s);if(i)std::cout<<',';
        std::cout<<"{\"slot\":"<<i<<",\"status\":"<<result<<",\"connected\":"<<(result==ERROR_SUCCESS?"true":"false");
        if(result==ERROR_SUCCESS){++count;std::cout<<",\"buttons\":"<<s.Gamepad.wButtons<<",\"x\":"<<s.Gamepad.sThumbLX<<",\"y\":"<<s.Gamepad.sThumbLY;}
        std::cout<<'}';
    }
    std::cout<<"],\"connected_count\":"<<count<<",\"read_only\":true,\"game_started\":false,\"injection\":false}\n";
    FreeLibrary(module);
}
int wmain(int argc,wchar_t** argv) {
    try {
        if(argc!=2)throw std::invalid_argument("explicit --fixture or --snapshot required");
        if(std::wstring(argv[1])==L"--fixture")fixture();
        else if(std::wstring(argv[1])==L"--snapshot")snapshot();
        else throw std::invalid_argument("unknown option");
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
