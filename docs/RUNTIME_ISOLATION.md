# 副本启动与进程配置隔离

更新：2026-10-12。状态：受控隔离测试通过，副本 Direct3D 启动已采样，画面与游戏流程待人工验收。

## 实现范围

工作副本使用 `build/runtime/game/`。x86 启动器新建进程专用的 HKCU 配置会话，读取并保持原有安装登记与用户设置，只覆盖会话内的 Directory 和 MCSetting。
Directory 指向工作副本，MCSetting 使用已验证的 52 字节候选。原安装 HKLM 登记与 HKCU VirtualStore 设置不改写。

游戏进程启动前载入 `workspace_profile.dll`，仅对主程序、MCAlpha.dll、Asura.dll 或 MCSetup.exe 的相关导入表进行内存重定向：

- 原生模块加载保持；在受控模块加载后安装配置重定向。
- 只匹配 `SOFTWARE\Softmax\MagnaCarta` 及其子键的打开/创建操作，返回独立会话键。
- 通过返回的键句柄读写设置时，操作落在会话区，退出后删除会话。
- 原始 EXE/DLL 文件不修改。MCBeta.dll、protect.dll 不参与重定向，光盘和保护检查不改写，不挂载任何镜像。

原有登记值保持原值复制，仅在本机会话中使用，不进入日志或源码仓库。此工具不是免 CD 实现，也不是完整文件系统沙箱。
模块路径与文件哈希是已测范围的证据；全部场景的资源、存档和媒体路径仍须验收。

## 版本与路径防护

启动器同时验证 MagnaCarta.exe 和 MCAlpha.dll 的 SHA-256，支持的指纹见 SAMPLE_AUDIT.md；未知版本停止。
工作区禁止位于原安装目录内，日志禁止写入原安装目录。路径若不能在当前 ANSI 代码页无损表达则停止，避免旧引擎误读路径。
编译强制 Win32，x64 配置被拒绝。启动器只处理自身创建的进程，不接受任意 PID。
会话进程由独立 Job 管理；失败或限时采样结束时停止测试进程，不把超时退出误报为游戏闪退。

## 已完成验证

### 独立测试程序

`tests/check_runtime_isolation.py` 完成 8 项检查：

1. 无重定向的只读基线正常执行。
2. 重定向后读取工作区 Directory 与 Direct3D 设置。
3. 测试写入仅作用于独立会话。
4. 原 HKLM 与 VirtualStore 全键值/子键摘要保持一致。
5. 进程结束后会话被清理。
6. 无重定向复测与基线输出一致；错误长度配置被拒绝。
7. 原安装目录作为工作区被拒绝。
8. 清理命令拒绝越界会话标识。

这些是测试程序证据，不代替游戏画面或流程验收。

### 实际副本采样

两次独立 20 秒采样均观察到工作副本进程：窗口标题为 Magna Carta，进程响应正常。
加载的 MCAlpha.dll、Asura.dll、AsrD3DDrv.dll 均来自工作目录；DDRAW.dll 来自系统，没有叠加第三方图形兼容层。
日志确认安装配置打开被重定向，实际图形分支为 Direct3D，而非原设置的 OpenGL。
采样结束由启动器主动停止进程，退出码 124；该值是测试时限结果，不作为自然退出或闪退证据。
退出后原安装注册表摘要保持一致，会话数为零。原目录 11,784 个文件及副本的原有文件哈希保持一致；副本新增 MC00.sav，来源目录未新增该文件。存档内容与读取正确性仍待验收。

尚未确认标题画面、新游戏、存读档、音乐、动画或场景切换，因此尚未发布运行兼容性通过结论。

## 构建与重复测试

需要 Visual Studio C++ Build Tools、Windows SDK 和 CMake；运行产物采用静态 C++ 运行库。

```powershell
cmake -S src/runtime -B build/runtime-native -G "Visual Studio 17 2022" -A Win32
cmake --build build/runtime-native --config Release
python tests/check_runtime_isolation.py --bin build/runtime-native/Release --profile build/runtime/MCSetting.direct3d.bin --output build/runtime-isolation-new
```

测试输出目录必须为新目录。独立程序测试依赖已安装的原版登记；复制目录不是完整便携安装。

## 启动与实际验收

关闭已有游戏及设置进程，保持本次有盘基线的挂载状态，再执行：

```powershell
& tools/launch_workspace.ps1
```

本地快捷入口为 `build/runtime/LaunchDirect3D.cmd`。启动脚本只打开副本，日志置于独立的时间戳目录。
默认不设时限，供实际画面和操作测试；`-Timeout 20` 仅用于限时采样。关闭游戏后会话自动清理。
此阶段测试顺序：标题画面与菜单 → 新游戏开场 → 正常退出 → 再次启动。随后再扩展存读档、场景和媒体。

## 禁用、回滚与异常恢复

不使用启动器时，没有持久导入表修改或原安装设置需要撤销；进程退出即卸载隔离模块。
基线复测在独立只读测试程序中验证，原安装目录不作为实验目标。
父启动器异常终止可能留下独立会话键，原安装设置仍不改写。会话标识格式为 PID-TICK；仅在所属进程退出后清理：

```text
workspace_launcher.exe --cleanup-session PID-TICK
```

清理只接受限定格式的独立会话标识，不删除原安装键。普通正常退出和配置失败清理已测试；异常断电恢复仍待验证。

## API 依据

进程启动、线程初始化和注册表虚拟化语义依据 Microsoft 文档；具体行为按上述测试结果记录。
[CreateRemoteThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createremotethread) / [Registry Virtualization](https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-virtualization)。
