#include "encounter_control.h"
#include <cstdio>
#include <cstring>
#include <stdexcept>
void check(bool ok,const char* text){if(!ok)throw std::runtime_error(text);}
int main(){try{
 auto p=static_cast<BYTE*>(VirtualAlloc(nullptr,0x10b000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));check(p,"allocation");
 auto d=reinterpret_cast<IMAGE_DOS_HEADER*>(p);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;auto nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(p+0x100);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x10b000;
 BYTE code[]={0x55,0x8b,0xec,0x83,0xec,0x0c,0xff,0x05,0,0,0,0,0xb8,1,0,0,0,0x8b,0xe5,0x5d,0xc3};*reinterpret_cast<DWORD*>(code+8)=reinterpret_cast<DWORD>(p+0xf4000);memcpy(p+0x6e07d,code,sizeof(code));BYTE guard[]={0x83,0x7d,0xf4,5};memcpy(p+0x6e093,guard,4);p[0x6e22d]=0xc3;
 BYTE before[6];memcpy(before,p+0x6e07d,6);using Call=int(__thiscall*)(void*);auto call=reinterpret_cast<Call>(p+0x6e07d);auto& count=*reinterpret_cast<unsigned*>(p+0xf4000);
 check(call(p)==1&&count==1,"baseline original");check(encounterTestMapped(p,0x10b000,true),"install");check(encounterTestMapped(p,0x10b000,true),"idempotent");
 encounterTestReset();BYTE keys[256]{};keys[VK_F5]=0x80;encounterKeyboard(keys,true);check(encountersEnabled(),"initial held ignored");encounterKeyboard(keys,true);keys[VK_F5]=0x80;encounterKeyboard(keys,true);check(!encountersEnabled(),"press switches off");check(call(p)==0&&count==1,"off bypasses original and freezes counters");
 for(int i=0;i<30;++i){keys[VK_F5]=0x80;encounterKeyboard(keys,true);}check(!encountersEnabled(),"held not repeated");
 encounterKeyboard(nullptr,false);keys[VK_F5]=0x80;encounterKeyboard(keys,true);check(!encountersEnabled(),"focus held suppressed");keys[VK_F5]=0;encounterKeyboard(keys,true);keys[VK_F5]=0x80;encounterKeyboard(keys,true);check(encountersEnabled()&&call(p)==1&&count==2,"on resumes original");
 check(wcsstr(encounterStatus(),L"ON")!=nullptr,"status on");HDC dc=CreateCompatibleDC(nullptr);HBITMAP bmp=CreateBitmap(320,40,1,32,nullptr);auto old=SelectObject(dc,bmp);encounterTestPaint(dc,320,40);check(GetPixel(dc,0,0)==RGB(18,32,42),"HUD production paint");SelectObject(dc,old);DeleteObject(bmp);DeleteDC(dc);
 p[0x6e093]^=1;check(!encounterTestMapped(p,0x10b000,false),"foreign guard rejects rollback");p[0x6e093]^=1;
 check(encounterTestMapped(p,0x10b000,false)&&!memcmp(p+0x6e07d,before,6),"rollback exact");check(call(p)==1&&count==3,"restored behavior");p[0x6e07d]^=1;check(!encounterTestMapped(p,0x10b000,true),"unknown source rejected");VirtualFree(p,0,MEM_RELEASE);
 puts("ENCOUNTER_CONTROL PASS initial=on edge=debounced focus=guarded off=random_bypassed counters=frozen on=native HUD=painted rollback=exact game_started=false");return 0;
}catch(const std::exception& e){printf("ENCOUNTER_CONTROL FAIL %s\n",e.what());return 1;}}
