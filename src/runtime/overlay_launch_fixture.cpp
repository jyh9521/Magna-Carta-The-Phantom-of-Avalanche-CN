// Execute the production launcher entry point with read-only registry responses.
// Registry writes and child creation are trapped; no installed state is altered.
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <vector>
#include <iostream>
#include <string>
namespace replay {
std::wstring installed;unsigned writes=0,children=0;
LSTATUS WINAPI open(HKEY,LPCWSTR,DWORD,REGSAM,PHKEY out){*out=reinterpret_cast<HKEY>(1);return ERROR_SUCCESS;}
LSTATUS WINAPI query(HKEY,LPCWSTR,LPDWORD,LPDWORD type,LPBYTE out,LPDWORD size){DWORD n=DWORD((installed.size()+1)*sizeof(wchar_t));if(*size<n)return ERROR_MORE_DATA;*type=REG_SZ;memcpy(out,installed.c_str(),n);*size=n;return ERROR_SUCCESS;}
LSTATUS WINAPI close(HKEY){return ERROR_SUCCESS;}
LSTATUS WINAPI create(HKEY,LPCWSTR,DWORD,LPWSTR,DWORD,REGSAM,const LPSECURITY_ATTRIBUTES,PHKEY,LPDWORD){++writes;return ERROR_ACCESS_DENIED;}
BOOL WINAPI child(LPCWSTR,LPWSTR,LPSECURITY_ATTRIBUTES,LPSECURITY_ATTRIBUTES,BOOL,DWORD,LPVOID,LPCWSTR,LPSTARTUPINFOW,LPPROCESS_INFORMATION){++children;return FALSE;}
}
#define RegOpenKeyExW replay::open
#define RegQueryValueExW replay::query
#define RegCloseKey replay::close
#define RegCreateKeyExW replay::create
#define CreateProcessW replay::child
#define wmain productionMain
#include "workspace_launcher.cpp"
#undef wmain
struct Result{int code;std::string out,error;};
Result run(std::vector<std::wstring> args){std::vector<wchar_t*> ptr;for(auto& a:args)ptr.push_back(a.data());std::ostringstream out,error;auto o=std::cout.rdbuf(out.rdbuf()),e=std::cerr.rdbuf(error.rdbuf());int code=productionMain(int(ptr.size()),ptr.data());std::cout.rdbuf(o);std::cerr.rdbuf(e);return {code,out.str(),error.str()};}
void check(bool good,const char* why){if(!good)throw std::runtime_error(why);}
int wmain(int argc,wchar_t** argv){try{
 check(argc==2,"workspace required");fs::path ws=fs::canonical(argv[1]);replay::installed=ws.wstring();
 std::vector<std::wstring> args={L"launcher",L"--workspace",ws.wstring(),L"--shim",(ws/L"modules/profile.dll").wstring(),L"--profile",(ws/L"cache/profile.bin").wstring(),L"--log",(ws/L"cache/session.log").wstring()};
 auto normal=run(args);check(normal.code==125&&normal.error.find("Original install must not be used as workspace")!=std::string::npos,"normal launch did not reproduce original-install rejection");
 std::cout<<"NATIVE_BASELINE "<<normal.error;
 args.push_back(L"--verify-only");auto verify=run(args);
 check(verify.code==125,"verify-only bypassed the actual launch location preflight");
 replay::installed=(ws.parent_path()/L"independent-original").wstring();auto isolated=run(args);check(isolated.code==0,"independent isolated preflight regressed");
 replay::installed=ws.wstring();args.push_back(L"--in-place-overlay");auto flat=run(args);check(flat.code==0,"explicit localized overlay preflight failed");
 check(flat.out.find("WORKSPACE_VERIFY PASS")!=std::string::npos,"overlay verification missing");
 // Overlay permission applies to the exact installed root, never an ancestor.
 replay::installed=(ws/L"nested-original").wstring();auto parent=run(args);check(parent.code==125,"overlay accepted ancestor of installed root");
 // A log outside the overlay cache is never allowed.
 replay::installed=ws.wstring();args[8]=(ws.parent_path()/L"outside.log").wstring();
 auto log=run(args);check(log.code==125,"overlay accepted outside log");
 check(replay::writes==0&&replay::children==0,"preflight wrote registry or created process");
 std::cout<<"OVERLAY_LAUNCH PASS registered_root=accepted legacy=rejected verify=full_preflight ancestor=rejected outside_log=rejected registry_writes=0 children=0 game_started=false\n";return 0;
}catch(const std::exception& e){std::cout<<"OVERLAY_LAUNCH FAIL "<<e.what()<<"\n";return 1;}}
