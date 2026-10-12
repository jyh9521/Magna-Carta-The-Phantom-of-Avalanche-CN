#include <windows.h>
#include <ddraw.h>
#include <d3d.h>
#include <iostream>
#include <stdexcept>
#include <filesystem>

// Noninteractive offscreen test: no ShowWindow, SetDisplayMode or game launch.
void checked(HRESULT result, const char* stage) {
    if (FAILED(result)) {
        std::cerr << "GRAPHICS_PROBE_FAIL stage=" << stage << " hr=0x"
                  << std::hex << static_cast<unsigned long>(result) << std::endl;
        throw std::runtime_error(stage);
    }
}

struct Vertex { float x, y, z, rhw; DWORD color; };
constexpr DWORD fvf = D3DFVF_XYZRHW | D3DFVF_DIFFUSE;
DDPIXELFORMAT depthFormat{};
unsigned halDevices = 0, tnlDevices = 0;
HRESULT CALLBACK deviceEnum(char*, char*, D3DDEVICEDESC7* caps, void*) {
    if (IsEqualGUID(caps->deviceGUID, IID_IDirect3DHALDevice)) ++halDevices;
    if (IsEqualGUID(caps->deviceGUID, IID_IDirect3DTnLHalDevice)) ++tnlDevices;
    return D3DENUMRET_OK;
}
HRESULT CALLBACK depthEnum(DDPIXELFORMAT* format, void*) {
    if (format->dwZBufferBitDepth == 16) {
        depthFormat = *format;
        return D3DENUMRET_CANCEL;
    }
    return D3DENUMRET_OK;
}

int wmain(int argc, wchar_t** argv) {
    IDirectDraw7* draw = nullptr;
    IDirect3D7* d3d = nullptr;
    IDirectDrawSurface7* target = nullptr;
    IDirectDrawSurface7* depth = nullptr;
    IDirect3DDevice7* device = nullptr;
    HMODULE module = nullptr;
    HWND window = nullptr;
    int result = 1;
    try {
        if ((argc != 2 && argc != 3) || !std::filesystem::path(argv[1]).is_absolute())
            throw std::runtime_error("Explicit absolute DLL path required");
        bool expectHalOnly = argc == 3 && wcscmp(argv[2], L"--expect-hal-only") == 0;
        if (argc == 3 && !expectHalOnly) throw std::runtime_error("Unknown probe option");
        module = LoadLibraryW(argv[1]);
        if (!module) throw std::runtime_error("DLL load failed");
        using Create = HRESULT(WINAPI*)(GUID*, void**, REFIID, IUnknown*);
        auto create = reinterpret_cast<Create>(GetProcAddress(module, "DirectDrawCreateEx"));
        if (!create) throw std::runtime_error("DirectDrawCreateEx missing");
        window = CreateWindowExW(0, L"STATIC", L"OffscreenGraphicsProbe", WS_POPUP,
                                 0, 0, 64, 64, nullptr, nullptr, nullptr, nullptr);
        if (!window) throw std::runtime_error("Hidden window creation failed");
        checked(create(nullptr, reinterpret_cast<void**>(&draw), IID_IDirectDraw7, nullptr), "create");
        checked(draw->SetCooperativeLevel(window, DDSCL_NORMAL), "cooperative");
        checked(draw->QueryInterface(IID_IDirect3D7, reinterpret_cast<void**>(&d3d)), "query_d3d7");
        checked(d3d->EnumDevices(deviceEnum, nullptr), "device_enum");
        std::cout << "DEVICE_ENUM hal=" << halDevices << " tnl=" << tnlDevices << std::endl;
        if (expectHalOnly && (halDevices != 1 || tnlDevices != 0))
            throw std::runtime_error("HAL-only device filter not effective");
        DDSURFACEDESC2 desc{}; desc.dwSize = sizeof(desc);
        desc.dwFlags = DDSD_CAPS | DDSD_WIDTH | DDSD_HEIGHT | DDSD_PIXELFORMAT;
        desc.dwWidth = 64; desc.dwHeight = 64;
        desc.ddsCaps.dwCaps = DDSCAPS_OFFSCREENPLAIN | DDSCAPS_3DDEVICE | DDSCAPS_VIDEOMEMORY;
        desc.ddpfPixelFormat.dwSize = sizeof(DDPIXELFORMAT);
        desc.ddpfPixelFormat.dwFlags = DDPF_RGB;
        desc.ddpfPixelFormat.dwRGBBitCount = 32;
        desc.ddpfPixelFormat.dwRBitMask = 0xff0000;
        desc.ddpfPixelFormat.dwGBitMask = 0xff00;
        desc.ddpfPixelFormat.dwBBitMask = 0xff;
        checked(draw->CreateSurface(&desc, &target, nullptr), "color_surface");
        checked(d3d->EnumZBufferFormats(IID_IDirect3DHALDevice, depthEnum, nullptr), "depth_enum");
        if (!depthFormat.dwSize) throw std::runtime_error("16-bit depth unavailable");
        desc.ddsCaps.dwCaps = DDSCAPS_ZBUFFER | DDSCAPS_VIDEOMEMORY;
        desc.ddpfPixelFormat = depthFormat;
        checked(draw->CreateSurface(&desc, &depth, nullptr), "depth_surface");
        checked(target->AddAttachedSurface(depth), "depth_attach");
        checked(d3d->CreateDevice(IID_IDirect3DHALDevice, target, &device), "device");
        D3DVIEWPORT7 viewport{0, 0, 64, 64, 0.f, 1.f};
        checked(device->SetViewport(&viewport), "viewport");
        checked(device->SetRenderState(D3DRENDERSTATE_ZENABLE, D3DZB_TRUE), "z_enable");
        checked(device->SetRenderState(D3DRENDERSTATE_ZWRITEENABLE, TRUE), "z_write");
        checked(device->SetRenderState(D3DRENDERSTATE_ZFUNC, D3DCMP_LESSEQUAL), "z_function");
        checked(device->SetRenderState(D3DRENDERSTATE_CULLMODE, D3DCULL_NONE), "cull");
        checked(device->SetRenderState(D3DRENDERSTATE_LIGHTING, FALSE), "lighting");
        Vertex nearTriangle[] = {{4,4,.25f,1,0xff00ff00},{60,4,.25f,1,0xff00ff00},{32,60,.25f,1,0xff00ff00}};
        Vertex farTriangle[] = {{4,4,.75f,1,0xffff0000},{60,4,.75f,1,0xffff0000},{32,60,.75f,1,0xffff0000}};
        for (unsigned frame = 0; frame < 120; ++frame) {
            checked(device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0, 1.f, 0), "clear");
            checked(device->BeginScene(), "begin");
            // Alternate drawing order: the near green triangle must remain visible.
            auto first = frame % 2 ? farTriangle : nearTriangle;
            auto second = frame % 2 ? nearTriangle : farTriangle;
            checked(device->DrawPrimitive(D3DPT_TRIANGLELIST, fvf, first, 3, 0), "draw_first");
            checked(device->DrawPrimitive(D3DPT_TRIANGLELIST, fvf, second, 3, 0), "draw_second");
            checked(device->EndScene(), "end");
            DDSURFACEDESC2 locked{}; locked.dwSize = sizeof(locked);
            checked(target->Lock(nullptr, &locked, DDLOCK_WAIT | DDLOCK_READONLY, nullptr), "readback");
            auto pixel = *reinterpret_cast<DWORD*>(static_cast<BYTE*>(locked.lpSurface) + 20 * locked.lPitch + 32 * 4);
            checked(target->Unlock(nullptr), "unlock");
            if ((pixel & 0xffffff) != 0x00ff00) {
                std::cerr << "PIXEL_MISMATCH frame=" << frame << " rgb=0x" << std::hex << (pixel & 0xffffff) << std::endl;
                throw std::runtime_error("Depth visibility check failed");
            }
        }
        std::cout << "BACKEND_MODULES d3d11_loaded=" << (GetModuleHandleW(L"d3d11.dll") ? "true" : "false")
                  << " d3d12_loaded=" << (GetModuleHandleW(L"d3d12.dll") ? "true" : "false") << std::endl;
        std::cout << "GRAPHICS_PROBE_PASS frames=120 depth=16 near_visible=120 display_mode_changed=false game_started=false" << std::endl;
        result = 0;
    } catch (const std::exception& e) {
        std::cerr << "GRAPHICS_PROBE_ERROR " << e.what() << std::endl;
    }
    if (device) device->Release();
    if (depth) depth->Release();
    if (target) target->Release();
    if (d3d) d3d->Release();
    if (draw) draw->Release();
    if (window) DestroyWindow(window);
    // Hook-based compatibility modules remain loaded until process termination.
    // Explicit unloading can leave hooks targeting released code during teardown.
    return result;
}
