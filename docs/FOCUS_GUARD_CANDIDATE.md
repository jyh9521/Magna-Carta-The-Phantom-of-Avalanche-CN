# 无边框失焦自动最小化候选

## 实际失败记录

会话 session-20261012-131317-425，PID 26368，未更新驱动加 DDrawCompat standard。反馈为运行正常，但 Alt+Tab 切出后切不回；退出码 1，不据此认定访问违规或正常退出。
55 个只读采样显示初始无边框呈现窗口覆盖 2880×1800 显示器，DPI 192，原游戏窗口随后为 640×480。约 13.11 秒开始，原窗口 HWND 0x3a1aa0 最小化、客户区 0×0，直至约 55 秒仍保持该状态。呈现尺寸不作为内部渲染尺寸。

## 静态分支

MCAlpha.dll SHA-256 `79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f`，PE32 SizeOfImage 0x10b000。窗口过程 RVA 0xbea8 的跳转表将 WM_KILLFOCUS（8）送入 0xbf3d，WM_ACTIVATEAPP（0x1c）送入通用分支 0xbf83。
0xbf3d 判断全局字段 RVA 0xf1b40 是否为 1；满足时 0xbf46 压入 SW_MINIMIZE（6），调用窗口获取函数，再经 IAT 0xbd420 调用 ShowWindow，返回地址为 0xbf54。该自动最小化路径与现场吻合，但尚未证明屏蔽此调用即可恢复完整切换。
[DDrawCompat AltTabFix 文档](https://github.com/narzoul/DDrawCompat/wiki/Configuration#alttabfix) 的 noactivateapp 处理激活通知并可能改变后台暂停/声音；已定位的是独立 WM_KILLFOCUS 分支，因此不同时修改 AltTabFix，避免第二个变量。

## 已实现行为

默认关闭，显式 --focus-guard / -FocusGuard 才启用。只改变 MCAlpha 的进程内 ShowWindow IAT 槽，不改磁盘游戏文件、系统库、窗口过程或保护模块。
只有返回地址为 MCAlpha+0xbf54、命令为 SW_MINIMIZE 且窗口属于当前进程时，抑制这一自动最小化调用。其他调用的参数和返回值原样转发，失焦消息其他处理仍执行；不抢焦点、不自动恢复窗口、不发送按键。
抑制时返回窗口先前可见性，符合 ShowWindow 返回语义，不将返回值当作成功标志。

启动前锁定 EXE、MCAlpha、未更新 AsrD3DDrv、DDrawCompat DLL 与 standard 配置哈希，拒绝与 TextureLifetime 同启。加载后核对 PE、SizeOfImage、调用指令、重定位 IAT 地址和原 ShowWindow 槽；未知或已被其他钩子改动的槽拒绝安装。IAT 页保护恢复，进程退出撤销内存修改。
FOCUS_GUARD_READY 为安装成功，FOCUS_MINIMIZE_SUPPRESSED 为命中特定调用；FOCUS_GUARD_REJECTED 不作为生效证据。

## 测试与恢复

本地 LaunchBorderlessTrial.cmd 已增加 FocusGuard，保持同一 window-game、驱动、配置、异常采集和观察器。LaunchBorderlessBaseline.cmd 为同一配置关闭 FocusGuard 的对照；正常入口 LaunchUnpatchedDriver.cmd 不变。

```powershell
& tools/launch_workspace.ps1 -Workspace build/runtime/window-game -CaptureException -FocusGuard -ObserverPython <Python路径>
```

本轮不启动游戏。下一次手动读取相同存档，Alt+Tab 五次，检查切回、点击、音画、模型和退出。日志必须核对 READY 和实际抑制记录；切回后原窗口应恢复非零客户区及交互。后台运行或声音行为仍需观察，不默认保证失焦暂停。

Win32 Release 构建通过。自建隐藏窗口验证基线转发、候选抑制、其他调用/返回值保持；合成 PE 验证映像拒绝、槽安装、幂等、页保护及隔离回滚，不加载商业引擎、不显示窗口、不运行游戏。
69 项单元测试、8 项注册表隔离检查和完整异常采集回归通过；未知图形层启动检查在创建游戏进程及会话注册表前拒绝。以上证明候选实现，不作为实际 Alt+Tab 修复验收。

后续会话 session-20261012-134848-617 已确认 READY 与一次抑制，但实际仍切不回，退出码 1。该候选单独处理不足，下一组保留本候选并仅调整 [DirectDraw 激活通知配置](ACTIVATION_CANDIDATE.md)；启动器配置白名单相应增加固定 activation 哈希。
