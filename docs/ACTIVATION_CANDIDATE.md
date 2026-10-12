# DirectDraw 激活路径对照

## 已确认的失败

会话 session-20261012-134848-617，PID 15744，出现 FOCUS_GUARD_READY 和一次 FOCUS_MINIMIZE_SUPPRESSED，但反馈仍为切出后切不回。40 个采样中，约 10.032 秒起原窗口 HWND 0x90ffe 仍为最小化、客户区 0×0；最终退出码 1。候选安装并命中不等于修复通过。
该证据排除“候选完全没有启用”这一解释，也证明仅抑制 MCAlpha 的已知 SW_MINIMIZE 调用不足以解决问题。其他最小化来源尚未取得现场调用栈，不直接认定具体模块为根因。

## 固定上游源码依据

已读取 narzoul/DDrawCompat commit `2c9a07fdf9308e2b0b117886a7e363b149ee1bc7` 的 [DDraw/DirectDraw.cpp](https://github.com/narzoul/DDrawCompat/blob/2c9a07fdf9308e2b0b117886a7e363b149ee1bc7/DDrawCompat/DDraw/DirectDraw.cpp)。handleActivateApp 在 AltTabFix=off 时调用系统 DirectDraw 原窗口过程；noactivateapp 分支绕过该激活处理、保留资源，并自行处理窗口显示及焦点。Config/Settings/AltTabFix.h 明确参数 PassToApp 范围 0..1。
[官方配置说明](https://github.com/narzoul/DDrawCompat/wiki/Configuration#alttabfix) 记载 noactivateapp(0) 不向 DirectDraw 和应用转发该激活通知，可能改变失焦暂停和后台声音。上述为源码/文档验证，不代表当前游戏已通过。

## 单变量调整

保留上轮未更新驱动、同一 DDrawCompat、FocusGuard、异常采集和观察器，只增加：

```ini
AltTabFix = noactivateapp(0)
```

graphics_compat.py 的 activation 配置由 standard 四项原设置加这一行组成，SHA-256 为 `9e9c39e6f51eee015fb90533fa67cd4bd66e076908c1a12ff15f70b28a1ead31`。
启动器的 FocusGuard 只允许原 standard 与该 activation 两个固定配置哈希，不放宽未知配置。没有添加其他兼容层、深度参数、设备类型、输入或分辨率变化。正常未更新驱动副本保持无层状态。

```powershell
python tools/graphics_compat.py select-profile --workspace build/runtime/window-game --driver-version unpatched --profile activation
python tools/graphics_compat.py select-profile --workspace build/runtime/window-game --driver-version unpatched --profile standard
```

第二条只恢复本轮单变量，保留上轮 FocusGuard。完整返回可用基线使用 LaunchUnpatchedDriver.cmd，而不是把失败组合标记为正常版本。
本地 LaunchBorderlessTrial.cmd 显式选择 activation 再启动带 FocusGuard 的同一副本；LaunchFocusStandard.cmd 为上一轮 standard 加 FocusGuard 的对照入口。配置验证失败不启动游戏。

## 验证与下一次实测

Win32 构建通过；70 项单元测试包含 activation→standard 字节往返。隐藏窗口 FocusGuard 样本、错误图形层拒绝与注册表隔离回归保持通过。隔离回滚副本恢复原配置和原源码，待测试副本保留 activation。
本轮没有启动、终止或操作游戏窗口。只读采样时游戏已自行结束，不宣称捕获了实时最小化调用栈。
下一次先测试切出并切回一次，再扩展到五次，检查点击、读档、模型和音画。日志须确认实际 AltTabFix=noactivateapp(0)、FOCUS_GUARD_READY，并核对切回后的窗口状态。特别观察后台是否继续运行或播放声音；不默认保证暂停。
当前仍未修复，P1 和 1080p 输出继续保持待验收。
