#include <windows.h>
extern "C" __declspec(dllexport) void WINAPI AIL_start_3D_sample(void*){SetLastError(0x4455);}
extern "C" __declspec(dllexport) void WINAPI AIL_stop_3D_sample(void*){SetLastError(0x4455);}
extern "C" __declspec(dllexport) void WINAPI AIL_end_3D_sample(void*){SetLastError(0x4455);}
extern "C" __declspec(dllexport) void WINAPI AIL_release_3D_sample_handle(void*){SetLastError(0x4455);}
extern "C" __declspec(dllexport) unsigned WINAPI AIL_3D_sample_status(void*){return 4;}
extern "C" __declspec(dllexport) void WINAPI AIL_stream_ms_position(void*,int* total,int* current){*total=5000;*current=500;}
