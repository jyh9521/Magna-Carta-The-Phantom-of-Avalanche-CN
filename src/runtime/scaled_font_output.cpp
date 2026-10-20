#include "scaled_font_output.h"
#include <algorithm>

bool parseScaledFontOutput(const wchar_t* text,ScaledFontOutput& output){
    output={};if(!text||!*text)return false;
    unsigned values[2]{};
    for(unsigned i=0;i<2;++i){unsigned digits=0;
        while(*text>=L'0'&&*text<=L'9'){
            if(++digits>5)return false;values[i]=values[i]*10+unsigned(*text++-L'0');
        }
        if(!digits||values[i]<1||values[i]>16384)return false;
        if(i==0&&*text++!=L'x')return false;
    }
    if(*text)return false;output={values[0],values[1]};return true;
}
bool highScaledFontOutput(const ScaledFontOutput& o){return o.width>=2560||o.height>=1440;}
bool resolveScaledFontOutput(const std::wstring& profile,const std::wstring& window,
                             unsigned dw,unsigned dh,ScaledFontOutput& output){
    output={};if(!dw||!dh||dw>16384||dh>16384)return false;
    ScaledFontOutput render{dw,dh};
    if(profile==L"baseline"||profile==L"fps60")render={1920,1080};
    else if(profile==L"render4k"||profile==L"wide4k"||profile==L"combined")render={3840,2160};
    else if(profile.rfind(L"md3-",0)==0){
        const auto separator=profile.find(L'-',4);if(separator==std::wstring::npos)return false;
        auto resolution=profile.substr(4,separator-4),tail=profile.substr(separator+1);
        if(tail!=L"borderless-30"&&tail!=L"borderless-60"&&tail!=L"fullscreen-30"&&tail!=L"fullscreen-60"&&tail!=L"windowed-30"&&tail!=L"windowed-60")return false;
        if(resolution==L"1080p")render={1920,1080};else if(resolution==L"2k")render={2560,1440};
        else if(resolution==L"4k")render={3840,2160};else if(resolution!=L"auto")return false;
    }else return false;
    ScaledFontOutput presentation{dw,dh};
    if(!window.empty()&&!parseScaledFontOutput(window.c_str(),presentation))return false;
    output={std::min(presentation.width,render.width),std::min(presentation.height,render.height)};return true;
}
