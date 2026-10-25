# 增强配置工具：分段选择与 Material 3 风格

> 当前发行：Release v1.0 已发布；2026-10-25 收到完整流程通关、测试无误的验收反馈。正式入口为 `Configure.exe` / `Game.exe`。以下日期化调查与测试包记录保留历史证据，旧待验收状态不代表 v1.0 发布状态；专项未独立采样的结论仍保留原证据边界。现行用法见 [v1.0 发布说明](RELEASE_V1.0.md)。

2026-10-16。当前入口为 `runtime/Configure.cmd`，标题为《真名法典：冰之魅影》增强配置工具。

## 界面与交互

Windows 自带 WPF 替换旧 Windows Forms 页面，无新增 GUI 运行库。界面采用冰蓝色调、圆角层级卡片、选中勾选与胶囊分段按钮；顶部复用 `locales/zh-CN/art/title-wordmark.png` 的主菜单原创字标。右下角“伯翎飞云”链接到 <https://blog.blfy.cc/>，仅主动点击才打开浏览器。

五组原有选项保持直接点选；窗口化增加独立分辨率下拉框：

- 分辨率：1080P（1920×1080）、2K（2560×1440）、4K（3840×2160）、自适应屏幕分辨率。
- 窗口模式：全屏、窗口化、无边框窗口化。
- 窗口分辨率：仅窗口化显示下拉框，960×540、1280×720、1600×900、1920×1080、2560×1440；默认1280×720。
- 帧数：30、60。
- 使用手柄：开、关。
- 自由视角：开、关。

选择态颜色渐变、按钮悬停/按压反馈、页面淡入上移和状态提示淡入已实现。关闭系统客户区动画时停用渐变；键盘焦点有明确描边，分组使用原生 RadioButton 键盘导航。窗口按工作区限制初始尺寸，内容区可滚动，底部操作区保持可见。

设计参考：[Material 3](https://m3.material.io/get-started) 的组件、颜色角色与形状层级。此实现是 WPF 原生风格适配，不引入 Android/Web 组件库，也不宣称使用官方桌面组件。

## 设置与实际启动连接（Verified）

`schema=2` 保存 `resolution/window_mode/frame_rate/native_gamepad/free_view`，并允许经过白名单验证的 `window_resolution`。旧schema=2缺少该字段时只在内存中补入1280×720，打开界面不改写文件。旧 schema=1 文件仍可读取，固定配方保留旧显示配置。打开界面不写配置；保存或显式检查/启动时才将当前选择写为 schema=2。旧 4:3 配方在新界面保存后按对应高度转换为 16:9 新预设，不保留隐藏的比例选择。

`tools/build_configuration_profiles.py` 生成 4×3×2 共24份显示 INI 及原生摘要白名单。启动器精确核对名称和文件摘要，不接受任意 INI；60帧同时启用呈现与完整动作候选，仍保留原33ms逻辑。自适应使用已固定 DDrawCompat v0.7.1 支持的 `ResolutionScale=display(-1)`，保持16:9画面，不等于新增21:9摄像机支持。全屏使用 `exclusive`，无边框使用 `borderless`；分辨率选项指内部渲染缩放目标，不承诺切换桌面显示模式。配置语义依据[官方说明](https://github.com/narzoul/DDrawCompat/wiki/Configuration#resolutionscale)与[v0.7.1源码](https://github.com/narzoul/DDrawCompat/blob/v0.7.1/DDrawCompat/Config/Settings/ResolutionScale.cpp)。

原生设置载入路径 `MCAlpha RVA 0x99cf` 无条件将 `engine+0xf1b40` 写为1；修改保存设置的窗口字节不会改变该路径。窗口化候选只在专用增强配置模块中，将 RVA `0x9a0e` 的 `mov dword ptr [engine+0xf1b40],1` 的立即数改为0。守卫核对PE32/x86/映像大小和完整10字节指令，重复安装幂等；关闭候选恢复立即数1。原窗口创建函数 RVA `0xc0dd` 已有带边框窗口样式 `0x12ca0000`。这是已验证的静态路径及自有执行桩，不是实际窗口化游戏验收。

源版本 SHA256：`5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。
REA/Ghidra证据：`ev_5a0a842a6667e9a0889f2fcb923b39da2d7b8abbc291ee15d64659f93a56687b`、`ev_7706f5a329ade6def3a6711876fb0b0a55c1eb90c52f18b22bc28632e3d72166`、`ev_d375492a426613e8b5922b9a0da4d115e28b87f96fc4521382ed500aa1abbc2a`。

schema=2 的配置入口使用专用 `configuration.dll`，不替换固定动作、手柄、地图及视角入口的历史模块。自由视角接入 `MC_FREE_VIEW`；关闭手柄时选择 input-passthrough，避免仅为视角强制开启手柄。自由视角在30帧下也安装所需的共享时钟/相机钩子，但不解锁60Hz绘制，显示限帧仍为30；不能只设置环境开关而漏掉相机消费者。所有开关在子启动结束后恢复父进程环境。版本预检临时切换显示 INI，并在成功/失败时恢复原字节。

## 构建与更新

```powershell
python tools/build_configuration_profiles.py --output build/configuration-profiles --header src/runtime/configuration_display_presets.h
cmake --build build/native --config Release --target workspace_profile workspace_launcher configuration_display_fixture
python tools/update_configuration_runtime.py apply --runtime runtime --native build/native/Release --record build/configuration-deployment
```

更新器先核对现有清单中的所有运行文件摘要，仅更新33份小型脚本、配置、原创字标和自有模块；不复制游戏目录，不写存档，不改当前设置文件。新打包需显式提供 `prepare_shared_runtime.py --configuration`；其它角色继续独立绑定。

```powershell
python tools/update_configuration_runtime.py rollback --runtime runtime --record build/configuration-deployment
```

回滚先整批核实当前摘要与原始备份，出现后续文件修改或设置已保存为新值时，整批拒绝回滚，保留当前设置和界面，避免恢复旧界面后无法读取新设置。原有文件逐字节恢复，新文件移除，配置设置文件与游戏数据保留。

## 验证与后续实测

自动检查覆盖96种设置组合、24份原生配置摘要、窗口标志实际x86写入/恢复及未知指令拒绝；隐藏WPF检查13个选项、选择态中间颜色、150%离屏渲染、保存/启动连接；自有验证EXE核实实际共享脚本传入的模块、参数与环境开关。

实际窗口化、独占全屏、各屏幕自适应、鼠标坐标与自由视角效果仍由手工游戏验收确认。默认不启动游戏或设置窗口，不切换桌面显示模式。新界面与启动连接完成不代表60FPS、实体手柄或自由视角已完成游戏验收。

本轮本机24份显示配置逐一通过真实共享入口 `VerifyOnly`，每次均恢复原显示INI；专用原生夹具119项通过。独立小型运行文件副本执行回滚后，旧界面自检恢复为12控件、5个下拉选项。活动运行目录保持新版，实际游戏启动0次。

## 窗口尺寸修正（2026-10-19）

**Verified（静态路径及自有隐藏窗口夹具）**：渲染缩放与窗口客户区大小属于不同参数。
原版MCAlpha窗口创建路径RVA 0xc0dd使用原逻辑宽高；原生窗口标志只切换窗口模式，
不会按照ResolutionScale放大窗口。新增字段通过MC_WINDOW_RESOLUTION传入专用配置模块，
其它配方清空该环境变量，入口结束后恢复父环境。

原生模块在版本匹配的MCAlpha导入槽0xbd418创建主窗口后，按所选客户区尺寸居中。
外框与任务栏占用计入最近显示器工作区，超出时按16:9等比缩小，避免标题栏越界。
引擎逻辑画布、资源、存档及桌面显示模式不变。
AsrD3DDrv呈现路径RVA 0x3155使用固定逻辑尺寸构造Blt目标矩形；
仅放大外框会造成画面未填满。导入槽0x1a55c的OffsetRect适配仅接受返回地址0x31fd，
将目标矩形改为实际客户区；源矩形保持原值，其它调用原样转发。
MCAlpha GetCursorPos/SetCursorPos导入槽0xbd3e8/0xbd3e4提供双向客户区缩放，
先于既有宽屏输入钩子安装，使原宽屏逆变换仍能成对工作。
安装器验证PE32/x86、映像尺寸、调用指令及原始导入地址，不接受未知布局或部分安装。

自有隐藏Win32窗口覆盖五种尺寸、工作区收敛、16:9客户区、目标矩形与无关调用、
负坐标显示器原点的鼠标往返、未知导入/指令拒绝。WPF自检覆盖下拉框显隐、
五项选择、保存重读与忙时禁用。以上不代替实际游戏画面、点击命中与实体手柄验收。

手动入口：runtime/Configure.cmd → 窗口化 → 窗口分辨率 → 保存设置／启动游戏。
验证1280×720与1600×900的窗口尺寸、画面铺满、菜单角落点击和窗口拖动后的指针命中；
再切回无边框确认下拉框隐藏。关闭游戏后可用部署记录执行配置运行包回滚。

### 窗口化画面仅占左上角的后续修正

2026-10-19实际反馈显示：窗口已达到1920×1080，画面仍缩在左上角。
运行日志确认呈现适配已进入，但进入时源矩形也是1920×1080；并非单纯遗漏目标矩形缩放。

**Verified（静态路径、真实启动日志、自有执行与光栅夹具）**：
AsrD3DDrv的RVA 0x2a2f在窗口模式中调用GetClientRect（RVA 0x2a4c，返回地址0x2a52），
随后按客户区大小创建后台渲染面。提前放大窗口会令后台面变大，而引擎仍绘制原逻辑区域。
因此仅放大输出目标也会同时放大源面的黑色空白。

修正仅在该后台面创建调用点，向驱动返回创建窗口前记录的逻辑客户区大小。
导入槽为0x1a560，PE、调用指令、导入地址整批校验；两个呈现导入槽一起更新，失败时恢复已写入槽。
其它GetClientRect调用与实际窗口尺寸保持原值，不影响兼容层、显示器工作区或窗口拖动。
源矩形保持逻辑画布，目标矩形保持所选实际客户区。
真实1920×1080标题启动日志已确认 `WINDOW_BACKBUFFER_SIZE logical=640x480 physical=1920x1080`
和 `WINDOW_PRESENT_SIZE source=640x480 destination=1920x1080`。

回归通过自有x86调用桩执行两个受返回地址约束的真实IAT适配路径，而非直接调用辅助函数。
旧实现返回1280×720后台面并失败；新实现返回640×480源与1280×720目标。
自有GDI光栅重放验证整个目标区域没有黑色填充；此像素证据属于自建重放，不等于商业游戏GPU截图验收。
真实游戏各场景、不同DPI及菜单点击仍保留人工验收项。

## 编译式封装与横排提示修订

当前源码的默认窗口为 720×600 DIP，底部四项快捷键横排、项目间两个空格。WPF 布局仍共用 Configure.xaml，玩家包内嵌资源并由 C# 实现设置交互；外置 PowerShell 保留用于开发基线。详见 [封装说明](COMPILED_DESKTOP_RELEASE.md)。
