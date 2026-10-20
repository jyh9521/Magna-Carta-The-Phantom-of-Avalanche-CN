#include "scaled_font_output.h"
#include <cstdio>
#include <cstdlib>
void check(bool v){if(!v){std::puts("OUTPUT_POLICY_FAIL");std::exit(1);}}
int main(){
    unsigned cases=0;
    for(auto size:{1920u,2880u,3840u})for(auto res:{L"1080p",L"2k",L"4k",L"auto"})
        for(auto mode:{L"borderless",L"fullscreen",L"windowed"})for(auto fps:{L"30",L"60"}){
            ScaledFontOutput o;auto profile=std::wstring(L"md3-")+res+L"-"+mode+L"-"+fps;
            bool window=std::wstring(mode)==L"windowed";
            check(resolveScaledFontOutput(profile,window?L"1920x1080":L"",size,size==2880?1800:size*9/16,o));
            check(highScaledFontOutput(o)==(!window&&size>=2560&&std::wstring(res)!=L"1080p"));++cases;
        }
    ScaledFontOutput o;
    check(resolveScaledFontOutput(L"md3-auto-borderless-60",L"",2880,1800,o)&&o.width==2880&&o.height==1800);
    for(auto bad:{L"",L"0x1800",L"2880x0",L"+2880x1800",L"2880x1800tail",L"2880X1800",L"999999999x99999",L"16385x1800"})check(!parseScaledFontOutput(bad,o));
    check(!resolveScaledFontOutput(L"md3-unknown-borderless-60",L"",2880,1800,o));
    check(!resolveScaledFontOutput(L"md3-auto-windowed-60",L"bad",2880,1800,o));
    check(!resolveScaledFontOutput(L"unknown",L"",2880,1800,o));
    std::printf("OUTPUT_POLICY PASS cases=%u laptop=2880x1800 low_output=baseline windowed=bounded invalid=rejected\n",cases);
}
