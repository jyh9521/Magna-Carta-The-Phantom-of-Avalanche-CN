#include "system_messages.h"
#include <bcrypt.h>
#include <cstring>
#include <regex>
#include <vector>
#ifdef SYSTEM_MESSAGE_RULES_HEADER
#include SYSTEM_MESSAGE_RULES_HEADER
#else
constexpr unsigned localeSystemCodePage=949;
constexpr char localeSystemSourceSha[]="";
const SystemRule localeSystemRules[]={{L"",L""}};
const SystemRule localeSystemEnvelopes[]={{L"",L""}};
const SystemRule localeSystemCaptions[]={{L"",L""}};
#endif

namespace {
bool convert(LPCSTR value,size_t limit,std::wstring& out) {
    if (!value) {out.clear();return true;}
    size_t length=strnlen_s(value,limit+1);
    if (length>limit) return false;
    if (!length) {out.clear();return true;}
    int n=MultiByteToWideChar(localeSystemCodePage,MB_ERR_INVALID_CHARS,value,static_cast<int>(length),nullptr,0);
    if (!n) return false;
    out.resize(n);
    return MultiByteToWideChar(localeSystemCodePage,MB_ERR_INVALID_CHARS,value,static_cast<int>(length),out.data(),n)==n;
}
size_t token(const std::wstring& s,size_t pos) {
    if (s.compare(pos,4,L"%04d")==0) return 4;
    if (s.compare(pos,2,L"%d")==0 || s.compare(pos,2,L"%s")==0) return 2;
    return 0;
}
bool ruleMatch(const SystemRule& rule,const std::wstring& input,std::wstring& output) {
    std::wstring source=rule.source,pattern,target=rule.target;
    if (source.empty()) return false;
    for (size_t i=0;i<source.size();) {
        size_t length=token(source,i);
        if (length) {
            pattern+=source[i+length-1]==L's'?L"([^\\r\\n]{1,256})":L"(-?[0-9]{1,11})";
            i+=length;
        } else {
            if (wcschr(L".^$|()[]{}*+?\\",source[i])) pattern+=L'\\';
            pattern+=source[i++];
        }
    }
    std::wsmatch match;
    if (!std::regex_match(input,match,std::wregex(pattern))) return false;
    output.clear();size_t arg=1;
    for (size_t i=0;i<target.size();) {
        size_t length=token(target,i);
        if (length) {if (arg>=match.size()) return false;output+=match[arg++].str();i+=length;}
        else output+=target[i++];
    }
    return arg==match.size();
}
}

bool translateSystemMessage(const std::wstring& input,std::wstring& output) {
    if (input.empty() || input.size()>2048) return false;
    for (const auto& rule:localeSystemRules) if (ruleMatch(rule,input,output)) return true;
    for (const auto& envelope:localeSystemEnvelopes) {
        std::wstring prefix=envelope.source;
        if (prefix.empty() || input.compare(0,prefix.size(),prefix)) continue;
        for (const auto& rule:localeSystemRules) {
            std::wstring payload;
            if (ruleMatch(rule,input.substr(prefix.size()),payload)) {output=envelope.target+payload;return true;}
        }
    }
    return false;
}

int dispatchSystemMessage(HWND owner,LPCSTR text,LPCSTR caption,UINT flags,SystemMessageA original,SystemMessageW unicode) {
    std::wstring input,output,title;
    try {
        if (!convert(text,2048,input) || !translateSystemMessage(input,output) || !convert(caption,256,title))
            return original(owner,text,caption,flags);
        for (const auto& rule:localeSystemCaptions) if (title==rule.source && title.size()) {title=rule.target;break;}
    } catch (...) {return original(owner,text,caption,flags);}
    // The caller still handles its original return code, exceptions or shutdown.
    return unicode(owner,output.c_str(),caption?title.c_str():nullptr,flags);
}

bool systemMessageModuleMatches(HMODULE module) {
    if (!module || strlen(localeSystemSourceSha)!=64) return false;
    wchar_t path[32768];DWORD length=GetModuleFileNameW(module,path,32768);
    if (!length || length>=32768) return false;
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if (file==INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;bool good=false;
    DWORD objectSize=0,used=0;BYTE digest[32]{};
    if (BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)==0 &&
        BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<BYTE*>(&objectSize),4,&used,0)==0) {
        std::vector<BYTE> object(objectSize),buffer(65536);
        if (BCryptCreateHash(algorithm,&hash,object.data(),objectSize,nullptr,0,0)==0) {
            good=true;
            while (true) {
                DWORD read=0;
                if (!ReadFile(file,buffer.data(),static_cast<DWORD>(buffer.size()),&read,nullptr)) {good=false;break;}
                if (!read) break;
                if (BCryptHashData(hash,buffer.data(),read,0)!=0) {good=false;break;}
            }
            if (good) good=BCryptFinishHash(hash,digest,32,0)==0;
        }
    }
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm,0);
    CloseHandle(file);
    constexpr char hex[]="0123456789abcdef";
    for (size_t i=0;good && i<32;++i)
        good=localeSystemSourceSha[i*2]==hex[digest[i]>>4] && localeSystemSourceSha[i*2+1]==hex[digest[i]&15];
    return good;
}
