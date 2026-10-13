#include "system_messages.h"
#include <cstdio>
#include <vector>
#include <cstring>
#ifdef SYSTEM_MESSAGE_RULES_HEADER
#include SYSTEM_MESSAGE_RULES_HEADER
#else
int main(){puts("SYSTEM_MESSAGES_BASELINE PASS rules=0 game_started=false");return 0;}
#endif
#ifdef SYSTEM_MESSAGE_RULES_HEADER
namespace {
std::wstring captured,title;int calledA=0,calledW=0;bool argsGood=true;
int WINAPI sinkA(HWND owner,LPCSTR text,LPCSTR caption,UINT flags) {
    ++calledA;argsGood &= owner==reinterpret_cast<HWND>(0x1234) && text && flags==0x1010;
    (void)caption;return 17;
}
int WINAPI sinkW(HWND owner,LPCWSTR text,LPCWSTR caption,UINT flags) {
    ++calledW;argsGood &= owner==reinterpret_cast<HWND>(0x1234) && text && flags==0x1010;
    captured=text;title=caption?caption:L"<null>";return 29;
}
std::string encode(const std::wstring& input) {
    int n=WideCharToMultiByte(localeSystemCodePage,0,input.c_str(),-1,nullptr,0,nullptr,nullptr);
    std::vector<char> buffer(n);WideCharToMultiByte(localeSystemCodePage,0,input.c_str(),-1,buffer.data(),n,nullptr,nullptr);
    return buffer.data();
}
int invoke(const std::wstring& input,const char* caption="Critical - Magna Carta") {
    auto bytes=encode(input);
    return dispatchSystemMessage(reinterpret_cast<HWND>(0x1234),bytes.c_str(),caption,0x1010,sinkA,sinkW);
}
}
int main() {
    unsigned cases=0;
    for (const auto& item:localeSystemFixtureCases) {
        if (invoke(item.source)!=29 || captured!=item.target || title!=localeSystemCaptions[0].target) return 1;
        for (const auto& envelope:localeSystemEnvelopes) {
            if (invoke(std::wstring(envelope.source)+item.source)!=29 || captured!=std::wstring(envelope.target)+item.target) return 2;
        }
        ++cases;
    }
    if (invoke(localeSystemFixtureCases[0].source,nullptr)!=29 || title!=L"<null>") return 3;
    unsigned glyphs=0;
    for (const auto& glyph:localeSystemGlyphs) {
        if (!glyph.pair) continue;
        const SystemRule* party=nullptr;
        for (const auto& r:localeSystemRules) if (!wcsncmp(r.source,L"%s",2)) {party=&r;break;}
        if (!party) return 11;
        std::string bytes;bytes+=static_cast<char>(glyph.pair>>8);bytes+=static_cast<char>(glyph.pair&255);
        bytes+=encode(std::wstring(party->source).substr(2));
        std::wstring expected=party->target;auto pos=expected.find(L"%s");expected.replace(pos,2,glyph.text);
        if (dispatchSystemMessage(reinterpret_cast<HWND>(0x1234),bytes.c_str(),nullptr,0x1010,sinkA,sinkW)!=29 || captured!=expected) return 12;
        ++glyphs;
    }
    int w=calledW;
    if (invoke(L"unrecognized text")!=17 || invoke(std::wstring(L"prefix")+localeSystemFixtureCases[0].source)!=17) return 4;
    if (invoke(std::wstring(2050,L'x'))!=17) return 5;
    if (dispatchSystemMessage(reinterpret_cast<HWND>(0x1234),"\x81",nullptr,0x1010,sinkA,sinkW)!=17) return 6;
    if (!argsGood || calledW!=w || calledA!=4) return 7;
    if (systemMessageModuleMatches(GetModuleHandleW(nullptr))) return 8;
    printf("SYSTEM_MESSAGES_MODIFIED PASS fields=%u native_glyphs=%u unicode_calls=%d unchanged_calls=%d owner_flags_returns=preserved unknown_version=rejected game_started=false\n",cases,glyphs,calledW,calledA);
    return 0;
}
#endif
