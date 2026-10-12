# 可用驱动基线上的无边框候选

## 当前阶段

未更新驱动的当前读档场景画面已收到正常反馈，基线为 build/runtime/unpatched-game。P1 先验证无边框、比例、点击和失焦，不同时增加渲染分辨率或更改输入。可用副本保持不变，新实验使用独立 build/runtime/window-game。

本次不同于历史补丁驱动试验：锁定未更新 AsrD3DDrv 和 AsrGlDrv 哈希，不启用补丁驱动专用 TextureLifetime。历史补丁驱动组合的读档失败及离屏退出异常继续保持失败记录，不自动外推为本次通过或失败。

## 候选与复现

复用固定 DDrawCompat v0.7.1，来源、包/DLL 哈希及 0BSD 见 [原候选记录](GRAPHICS_CANDIDATE.md)。[官方 FullscreenMode 配置](https://github.com/narzoul/DDrawCompat/wiki/Configuration#fullscreenmode) 是无边框候选依据，不作为本作验收。独立副本只添加一个图形层及其受控配置/manifest。

```powershell
python tools/prepare_workspace.py --source build/runtime/unpatched-game --target build/runtime/window-game --manifest build/borderless-unpatched-evidence/game-copy-manifest.json
python tools/graphics_compat.py apply --workspace build/runtime/window-game --package build/graphics-research/DDrawCompat-v0.7.1.zip --driver-version unpatched
python tools/graphics_compat.py remove --workspace build/runtime/window-game
```

工具新增显式 patched/unpatched 输入矩阵。默认仍为 patched，不默许未知驱动；unpatched 同时核对两个驱动，EXE 和 MCAlpha 不改变。恢复只移除新增图形层、配置及 manifest，保持未更新驱动和存档。其他候选工具不随之放宽版本检查。

配置固定为 FullscreenMode=borderless、DisplayAspectRatio=app、ResolutionScale=app、LogLevel=info。没有强制 1080p、设备类型、深度或纹理参数；不声称原生高分辨率。不叠加 dgVoodoo2、DxWnd 或纹理槽候选。

## 窗口测量

tools/observe_window.py 是只读诊断工具，不启动游戏、不切换焦点、不发送按键、不改窗口风格、不改变系统显示模式。读取已创建会话的游戏 PID 与 IAT_READY 路径，核对隔离位置及 EXE 哈希，再确认该 PID 实际映像路径，避免采样其他应用。

每秒记录该 PID 窗口的外框、客户区、style、可见性、显示器坐标、DPI、前台状态和最小化状态，最长默认 120 秒。无标题/可调整边框的 popup 与覆盖显示器分别判断，不把任何小型无边框窗口误认作全屏无边框。输出在会话 window-observation.json；异常在 window-observer.stderr.log。

客户区尺寸不是内部渲染分辨率，观察报告显式区分。本轮不读取或修改游戏渲染状态，也不声称测得实际渲染尺寸。

显式手动运行本地 LaunchBorderlessTrial.cmd 才启动游戏并附带观察器；默认正常入口不启动观察器。也可单独执行：

```powershell
python tools/observe_window.py --session build/runtime-launch/session-<时间> --seconds 120
```

## 已完成检查

69 项单元测试通过，覆盖版本矩阵和负坐标显示器、普通带标题窗口、无边框小窗口判定。自建隐藏窗口验证客户区 640×480、无边框风格和销毁，退出码 0；测试不运行游戏、不显示窗口、不改变桌面分辨率。启动脚本仅作语法解析。
独立回滚样本移除图形层后恢复三个新增文件之前的状态，未更新驱动字节保持；当前候选保留待测，可用基线不变。

## 实际验收清单

1. 运行 LaunchBorderlessTrial.cmd，读取同一存档，检查角色、地形、贴图是否仍正常。
2. 检查无标题栏、任务栏/桌面切换、比例和菜单/移动点击坐标；图形日志确认实际候选加载，观察报告确认 visible、borderless_style 与 covers_monitor。
3. 首轮 Alt+Tab 五次，测试失焦恢复和正常退出；首轮通过后再按主清单扩展到 20 次、不同 DPI 与多显示器。不预设 Alt+Enter 已支持。
4. 游戏闪退、显示回归或鼠标错位则记录失败，新会话异常采集保留现场；正常入口仍使用 LaunchUnpatchedDriver.cmd，不撤销可用基线。

当前游戏验收未执行。窗口遥测成功不替代画面、输入或存档验收。后续 1080p 输出须在本组通过后再建立单变量配置，内部渲染提升与比例缩放分别记录。
