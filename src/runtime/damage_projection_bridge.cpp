#include "damage_projection.h"
#include <windows.h>
#include <iostream>
#include <iomanip>
#include <string>
#include <stdexcept>
#include <cstring>
#include <cmath>
#include <cstdlib>
#include <cstdint>
#include <fstream>
#include <vector>
#include <cwchar>
static int nativeRaster=0,nativeFloat=0,nativeBool=0;static bool installerReady=false;
static void installed(const wchar_t* line){installerReady=std::wcsstr(line,L"DAMAGE_PROJECTION_READY")!=nullptr;}
static void __fastcall rasterLeaf(void*,void*,const float*){++nativeRaster;}
static void __fastcall floatLeaf(void*,void*,unsigned,float*){++nativeFloat;}
static void __fastcall boolLeaf(void*,void*,unsigned,BYTE*){++nativeBool;}
static void jump(BYTE* p,void* target){p[0]=0xe9;*reinterpret_cast<int32_t*>(p+1)=static_cast<int32_t>(reinterpret_cast<uintptr_t>(target)-reinterpret_cast<uintptr_t>(p+5));}
// Invoke the patched native ABI sites while explicitly testing their stack and
// nonvolatile register contract. No commercial machine code executes here.
static __declspec(naked) unsigned __cdecl auditCall(void*,void*,uintptr_t,uintptr_t,unsigned){__asm {
 push ebp
 mov ebp,esp
 push ebx
 push esi
 push edi
 sub esp,4
 mov dword ptr[ebp-16],esp
 mov ebx,11223344h
 mov esi,22334455h
 mov edi,33445566h
 cmp dword ptr[ebp+24],2
 jne one_arg
 push dword ptr[ebp+20]
 one_arg:
 push dword ptr[ebp+16]
 mov ecx,dword ptr[ebp+12]
 call dword ptr[ebp+8]
 xor eax,eax
 cmp esp,dword ptr[ebp-16]
 je stack_ok
 or eax,1
 stack_ok:
 cmp ebx,11223344h
 je ebx_ok
 or eax,2
 ebx_ok:
 cmp esi,22334455h
 je esi_ok
 or eax,4
 esi_ok:
 cmp edi,33445566h
 je edi_ok
 or eax,8
 edi_ok:
 lea esp,[ebp-12]
 pop edi
 pop esi
 pop ebx
 mov esp,ebp
 pop ebp
 ret
}}
static float number(){std::string s;if(!(std::cin>>s))throw std::runtime_error("float field");char* end=nullptr;float f=std::strtof(s.c_str(),&end);if(!end||*end)throw std::runtime_error("float token");return f;}
int main(int argc,char** argv){try{
 if(argc<2||argc>3)throw std::runtime_error("owned driver DLL absolute path [--native|--rollback]");
 bool rollback=argc==3&&!strcmp(argv[2],"--rollback");
 bool hook=argc==2||rollback;if(argc==3&&!rollback&&strcmp(argv[2],"--native"))throw std::runtime_error("unknown bridge option");
 // Validate the data-only fixture before asking the Windows loader to map it.
 // A real driver or another executable module is never a valid bridge input.
 std::ifstream file(argv[1],std::ios::binary|std::ios::ate);if(!file||file.tellg()<0||file.tellg()>0x100000)throw std::runtime_error("owned fixture input size");
 std::vector<char> raw(static_cast<size_t>(file.tellg()));file.seekg(0);file.read(raw.data(),raw.size());
 if(raw.size()<sizeof(IMAGE_DOS_HEADER))throw std::runtime_error("owned fixture DOS header");
 auto sourceDos=reinterpret_cast<const IMAGE_DOS_HEADER*>(raw.data());if(sourceDos->e_magic!=IMAGE_DOS_SIGNATURE||sourceDos->e_lfanew<0||static_cast<size_t>(sourceDos->e_lfanew)+sizeof(IMAGE_NT_HEADERS32)>raw.size())throw std::runtime_error("owned fixture PE bounds");
 auto sourceNt=reinterpret_cast<const IMAGE_NT_HEADERS32*>(raw.data()+sourceDos->e_lfanew);
 if(sourceNt->Signature!=IMAGE_NT_SIGNATURE||sourceNt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||sourceNt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC||sourceNt->OptionalHeader.AddressOfEntryPoint||sourceNt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].Size||sourceNt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_TLS].Size||std::string(raw.begin(),raw.end()).find("owned_driver_space")==std::string::npos)throw std::runtime_error("only no-entry no-import owned fixture accepted");
 auto driver=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!driver)throw std::runtime_error("owned driver fixture load");
 auto db=reinterpret_cast<BYTE*>(driver);auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(db+reinterpret_cast<IMAGE_DOS_HEADER*>(db)->e_lfanew);if(nt->OptionalHeader.AddressOfEntryPoint||nt->OptionalHeader.SizeOfImage<0x2c000)throw std::runtime_error("not data-only owned driver fixture");
 auto image=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));if(!image)throw std::runtime_error("owned image allocation");
 auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;auto pe=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+0x80);pe->Signature=IMAGE_NT_SIGNATURE;pe->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;pe->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;pe->OptionalHeader.SizeOfImage=0x10b000;
 const unsigned sites[]={0x474cf,0x474ec,0x47509};const BYTE calls[][6]={{0xff,0x92,0x94,3,0,0},{0xff,0x92,0xb4,1,0,0},{0xff,0x92,0xa4,1,0,0}};
 BYTE rasterStub[]={0x8b,0x11,0xff,0x74,0x24,0x04},queryStub[]={0x8b,0x11,0xff,0x74,0x24,0x08,0xff,0x74,0x24,0x08};
 for(unsigned i=0;i<3;++i){memcpy(image+sites[i],calls[i],6);auto p=image+0x400+i*0x20;memcpy(p,i?queryStub:rasterStub,i?10:6);jump(p+(i?10:6),image+sites[i]);image[sites[i]+6]=0xc2;image[sites[i]+7]=i?8:4;image[sites[i]+8]=0;}
 if(hook&&!installDamageProjection(reinterpret_cast<HMODULE>(image),installed))throw std::runtime_error("production hook installation");
 if(rollback){if(!setDamageProjection(image,0x10b000,false))throw std::runtime_error("explicit rollback");for(unsigned i=0;i<3;++i)if(memcmp(image+sites[i],calls[i],6))throw std::runtime_error("explicit rollback bytes");hook=false;}
 std::string id;while(std::cin>>id){
  int width,height;unsigned rva[3],valid;if(!(std::cin>>width>>height>>rva[0]>>rva[1]>>rva[2]))throw std::runtime_error("case header");
  BYTE object[0x100]{};void* table[230]{};*reinterpret_cast<void***>(object)=table;
  for(unsigned i=0;i<16;++i)reinterpret_cast<float*>(object+0x5c)[i]=number();for(unsigned i=0;i<16;++i)reinterpret_cast<float*>(object+0x9c)[i]=number();
  float point[3];for(auto& v:point)v=number();float output[4];for(auto& v:output)v=number();if(!(std::cin>>valid)||valid>255)throw std::runtime_error("bool seed");BYTE boolean=static_cast<BYTE>(valid);
  void* leaves[]={reinterpret_cast<void*>(&rasterLeaf),reinterpret_cast<void*>(&floatLeaf),reinterpret_cast<void*>(&boolLeaf)};unsigned slots[]={0x394,0x1b4,0x1a4};
  if(rva[0]==rva[1]||rva[0]==rva[2]||rva[1]==rva[2])throw std::runtime_error("distinct ABI slots required");
  for(unsigned i=0;i<3;++i){if(rva[i]<0x2000||rva[i]+5>=0x2c000)throw std::runtime_error("owned driver RVA bounds");DWORD old;if(!VirtualProtect(db+rva[i],5,PAGE_EXECUTE_READWRITE,&old))throw std::runtime_error("owned driver page");jump(db+rva[i],leaves[i]);table[slots[i]/4]=db+rva[i];}
  *reinterpret_cast<int*>(image+0xf1b48)=width;*reinterpret_cast<int*>(image+0xf1b4c)=height;nativeRaster=nativeFloat=nativeBool=0;
  unsigned abi=auditCall(image+0x400,object,reinterpret_cast<uintptr_t>(point),0,1);abi|=auditCall(image+0x420,object,0xb07,reinterpret_cast<uintptr_t>(output),2);abi|=auditCall(image+0x440,object,0xb08,reinterpret_cast<uintptr_t>(&boolean),2);
  std::cout<<"{\"id\":\""<<id<<"\",\"raster_float\":[";for(unsigned i=0;i<4;++i){if(i)std::cout<<',';if(std::isfinite(output[i]))std::cout<<std::setprecision(9)<<output[i];else std::cout<<"null";}
  std::cout<<"],\"float_bits\":[";for(unsigned i=0;i<4;++i){uint32_t v;memcpy(&v,output+i,4);if(i)std::cout<<',';std::cout<<v;}std::cout<<"],\"valid\":"<<unsigned(boolean)<<",\"abi_error_bits\":"<<abi<<",\"delegated\":["<<nativeRaster<<','<<nativeFloat<<','<<nativeBool<<"],\"hook_enabled\":"<<(hook?"true":"false")<<",\"installer_ready\":"<<(installerReady?"true":"false")<<",\"rollback_exact\":"<<(rollback?"true":"false")<<",\"driver_lookup\":"<<(GetModuleHandleW(L"AsrD3DDrv.dll")==driver?"true":"false")<<",\"commercial_dll_loaded\":false,\"game_started\":false}"<<std::endl;
 }
 if(hook&&!setDamageProjection(image,0x10b000,false))throw std::runtime_error("production hook rollback");for(unsigned i=0;i<3;++i)if(memcmp(image+sites[i],calls[i],6))throw std::runtime_error("exact rollback bytes");VirtualFree(image,0,MEM_RELEASE);FreeLibrary(driver);return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
