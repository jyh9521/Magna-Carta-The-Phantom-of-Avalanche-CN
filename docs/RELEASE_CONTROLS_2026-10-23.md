# 发布输入归档、通用模型插帧与随机遇敌开关

2026-10-23。入口保持 `runtime/Play.cmd`，复用共享数据，不创建完整游戏副本。

## 发布决定与归档

- 手柄支持、自由视角从发布设置和玩家配方中移除。历史源码、受控夹具和技术文档保留，研究基点为 `efa303e`，不删除可复用结论。
- schema 1/2 的旧设置继续可读；`native_gamepad`、`free_view` 在运行投影中强制为 false。部署不改已有设置字节；下一次正常保存会写入关闭值。
- 发布模块编译定义 `RELEASE_ARCHIVED_INPUT`：忽略环境中的旧开关，键盘钩子强制使用无手柄路径，自由视角保持关闭。普通相机插帧继续保留。
- 旧手柄/自由视角研究入口明确报归档；新玩家包不含这些入口，也不含对应配方。现有旧快捷方式不重新启用功能。
- F10 普通连招辅助、F11 暴走连招辅助及真实键鼠输入保留。

## Verified：四条模型绘制路径

此前 `motion60.cpp` 仅接入 MCAlpha 两个派生 renderer：蒙皮 `3b0c0`、刚性 `3d12f`，通过 MCAlpha IAT 调用绝对骨骼函数。
Asura 还有独立的基础类实现：`ASRObsPhysique::Render` RVA `4b6c2`、`ASRObsStatic::Render` RVA `4d6c3`。
基础类直接调用 `MakeAbsoluteMatrix`，返回点分别为 `4be55`、`4dbdc`，不经过原先的两个 vtable slot / IAT。

支持 Asura SHA256 `f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557`，映像大小 `74d000`；
MCAlpha SHA256 `7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
静态证据：REA `ev_1ba3ad2a585163bd6f3fff76cb082005456276d822238b9ae4cb07fad5fd7dc8`。

新增基础类入口与直接调用点接入，同步使用既有人物的 33ms 余数相位、骨骼插值、世界轨迹和绘制后恢复流程。
基础类 action 的序列表存放资源句柄，按原生 `GetASRBoneAnim` 的表范围解析；不把它误读为 MCAlpha 的指针包装记录。
两条基础入口的完整九字节前缀和两条五字节调用一起预检；任一漂移拒绝整批改写。
不改动画文件、播放速度、AI、伤害、动作事件或存档。

新增自有基础类绘制回放：旧生产源码保持基础入口原样，显示最新姿态 `110.000000`，中点断言失败；
新生产钩子显示前后姿态的共享相位中间值，并精确恢复原生绝对姿态。两类基础模型及原有两类模型回归通过。
旧源码编译夹具的兼容适配仅表示原先没有基础类安装步骤；不表示商业场景曾被执行。
独立入口/调用点漂移拒绝、返回 PC 分类及原字节撤销均有回归。

完整 AINIM 只读审计：1,818 文件、2,600,174 动态矩阵均满足当前单矩阵准入，2,528,835 相邻姿态对；
12 次手性变化仍使用原生旁路，不跨反射符号强行平滑。资源未修改。

### High-confidence deduction 与未验证范围

基础类路径是原插帧覆盖之外的真实缺口，现已按模型类别统一接入，不使用主角/怪物 ID 白名单。
但尚未记录玩家所见卡顿怪物的资源与实际 renderer，因此不把该路径缺口宣称为现场卡顿的唯一根因，
也不把资源审计称作全部怪物的逐只实机验收。需观察怪物待机、移动、攻击、受击、死亡和换动作。

## Verified：F5 随机遇敌开关

原生随机遇敌判定函数 MCAlpha RVA `6e07d` 读取 Field `+10e0` 的频率类型，
更新数据管理器 `+10a0` 步进与 `+10a4` 倒计数；到期返回 1。
其已解析调用者 `6b483` 仅在随机结果为 1 且找到区域敌组时进入战斗状态。
REA `ev_9b46733e233347eed3390143bb70c8500756c0835025e89297262f218705302d`、
`ev_7d846efc782b7b4257d192c9dba42fc1f6d58d4b330151c5ad42e590e862b0d5`。

开关只包围该判定：
- 启动默认开启，F5 第一次关闭、第二次开启；退出重启恢复开启，不写存档。
- 关闭时直接返回 0，不推进随机计数、不取随机数。重新开启继续原计数，不保证额外安全步数。
- 剧情/强制战斗、已开始战斗和任务逻辑不改。
- 按下边沿去抖；按住不连翻，失焦和失焦期间按住的键不误触发。只消耗 F5，不改 F10/F11。
- 使用原生键盘采样观察接口，不依赖手柄组件的虚拟按键。

2026-10-23 提示修订：旧版常驻顶部的大条幅已由玩家画面反馈否决，并报告左上角同文闪烁。
离线生产 WM_TIMER 回放复现未按 F5 就显示；旧分支每 50ms 重定位、显示并请求重绘。
原 HDC 背景像素测试不足以发现常驻、重绘频率和呈现方式问题。

状态改成仅 F5 切换后显示 1.8 秒，右下角 16/24 像素留边；高度按客户区缩放并限制在 24–32 像素，宽度最多 320 像素。
启动不显示、过期隐藏、失焦/最小化隐藏；按住不刷新期限。切回窗口不重新计时。
文字仅绘制到离屏 32 位 DIB，再由 UpdateLayeredWindow 一次提交图像与屏幕坐标，成功后才显示。
WM_PAINT 不再绘字，不再使用 InvalidateRect，也不在内容与位置未变时重复绘制/显示。
这消除了窗口 DC 绘字和初始 (0,0) 绘字路径；与游戏内左上角闪字的因果关系仍需玩家现场确认。
提示文字来自 `locales/zh-CN/encounter-ui.json`，通用实现保留英文缺省值。

`encounter_hud_fixture` 直接包含生产实现，在 Win32 呈现边界回放相同定时器和 F5 路径，锁定时钟、窗口位置、焦点。
旧源码断言 `HUD visible before first F5 (persistent banner)` 失败；新源码验证启动隐藏、1799ms 可见/1800ms 隐藏、
紧凑尺寸、仅变化时提交、文字目标为内存 DC、失焦和过期切回行为。
窗口与焦点 API 使用确定性替身，不启动游戏、不创建桌面窗口，因此该结果不是游戏画面或 DirectDraw 兼容性验收。
无边框、窗口、独占全屏、DPI、多显示器下最终呈现仍由测试者验收。

提示热修复使用 `tools/build_encounter_hud_update.py`，基线锁定已交付的 `MagnaCarta-release-controls-20261023.zip`。
仅更新十二个自有模块和玩家原有清单，不引入维护目录特有依赖；独立 `.encounter-hud-20261023` 回滚目录保留前次更新证据。
真实 PowerShell 更新器在自有文件夹具上验证预检、安装、重复安装、回读、独立副本回滚及混合版本拒绝。
证据位于 `build/encounter-hud-repair/`，源码回滚只在隔离源码目录进行，共享运行目录保持修复状态。

## 构建与离线复现

```powershell
cmake --build build/native --config Release --target workspace_profile encounter_control_fixture encounter_hud_fixture native_actor_motion_fixture motion60_fixture rigid_motion_fixture
build/native/Release/encounter_control_fixture.exe
build/native/Release/encounter_hud_fixture.exe
build/native/Release/native_actor_motion_fixture.exe
build/native/Release/motion60_fixture.exe
build/native/Release/rigid_motion_fixture.exe
build/native/Release/bone_pose_audit.exe runtime/data/AINIM
$env:PYTHONPATH=(Resolve-Path runtime/dependencies).Path
python -m unittest discover -s tests
python tests/check_runtime_docs.py --expect modified
```

`tools/update_release_controls.py` 将十二个自有模块、六个入口/配置文件和 runtime.json 作为可撤回部署；
所有旧摘要预检、原文件备份、更新后回读均保留。不会修改游戏数据、个人设置或存档。
`tools/build_release_controls_update.py` 生成独立命名空间的小更新，保留早先更新的回滚目录。
面向已交付的统一包+F11安装，使用 `tools/prepare_release_controls_package.py` 从两份摘要锁定的真实旧包重建自有文件基线，
不使用维护目录特有的诊断入口摘要；新 manifest 的每个依赖须能由原包+更新载荷满足。
`tools/verify_release_controls_update.py` 使用仅含自有文件的两份最小夹具，运行真实 PowerShell 更新器的
Verify / Install / 重复 Install / CheckInstalled / 独立副本 Rollback，并验证混合版本拒绝和保护文件不变。
修改后夹具保持修改状态，另一份恢复原摘要，不复制游戏资源树。

统一包由 `tools/refresh_player_package.py` 从摘要锁定的上版增量包刷新：
逐份检查现有 814 资源增量仍对应当前数据，再替换自有模块和设置入口；不重新解包或复制完整游戏。
资源存在漂移时停止，要求从支持的原版重建，不静默混用版本。

本轮证据保存在 `build/release-controls-evidence/`，源码原件、差异、源回滚脚本、部署记录和玩家更新器验证互相独立。
回滚玩家更新时使用包内 `Release-Controls-20261023/Update.ps1 -Action Rollback -Runtime .`；
本地源回滚脚本只在隔离源码夹具运行，不撤销共享运行目录中的新版本。

## 手工验收

使用原 Play.cmd 和现有存档；当前个人配置维持 60 帧、自适应、无边框。
1. 打开设置确认手柄/自由视角选项消失，普通人物与镜头操作保持原样。
2. 60 帧下观察多种怪物的待机、行走、攻击、受击、死亡；必要时与 30 帧对照，记录具体怪物和动作。
3. 在可遇敌区域按 F5，检查“关闭”提示并持续行走；再按一次检查“开启”和随机战斗恢复。
4. 按住 F5、切出切回、移动窗口，确认提示不抢焦点、不遮点击、不重复切换；检查全屏可见性。
5. 检查剧情强制战斗、F10/F11 和保存读档。长流程与所有怪物的最终画面仍由测试者验收。

## 本轮离线结果

基线全套 872 项通过（1 项跳过）；调整后全套 880 项通过（1 项跳过）。最终核心钩子 996 检查、刚性同相位 33 个余数、新增基础类与遇敌夹具、20 项配置回归及8项发布调整回归通过。实际已交付的统一包+F11基线由真实小更新器验证安装、重复安装、独立副本回滚、混合版本拒绝，个人设置字节保持不变。上述均为离线结果，不提升为全部怪物或叠加提示的游戏内验收。

### 提示修复离线结果

修复后的全套 882 项通过（1 项跳过），发布控制回归 10 项通过；遇敌呈现消息回放、原随机判定钩子、996 项动作钩子检查和两类基础模型回放通过。旧源码在同一呈现回放中稳定失败，隔离源码回滚恢复相同失败及原摘要；玩家小更新的真实安装与精确回滚通过。上述结果不代替游戏内闪字消失验收。

### 两次已交付更新之后的去重小包

`tools/build_encounter_hud_update.py --f11 <F11包> --previous <发布功能调整包> ...` 同时锁定两份交付 ZIP 摘要，并核对 F11 的十三个输出摘要等于发布功能调整包对应的输入摘要。目标是依次装完这两个更新后的版本，不要求先装旧的提示修复包。十二个同摘要模块共用一份 ZIP 载荷，更新器仍逐路径预检、写入、回读和备份。独立 `Encounter-HUD-Compact-20261023` / `.encounter-hud-compact-20261023` 命名空间保留前两次更新证据。十三个目标文件只有两份不同载荷，游戏资源与个人设置不包含在更新载荷中。

### 提示消失反馈与可见后补交（候选）

玩家在共享测试版反馈 F5 无可见提示。该次 `profile.log` 保留多条 `ENCOUNTER_STATE enabled=false/true key=F5`，因此按键与开关状态确实在工作；旧日志没有位图提交与显示结果，不能凭此判定具体显示失败点。

Verified：DDrawCompat 0.7.1 `Gdi/Window.cpp::updateWindow` 对未登记的隐藏窗口直接返回；`updateLayeredWindowInfo` 只给已登记窗口缓存位图。之前的 HUD 在隐藏时提交一次位图，随后显示，状态与位置不变便不再提交。生产消息回放增加可见窗口登记/位图缓存模型后，首次 F5 稳定失败：`compat compositor missed bitmap submitted before visibility`。这证明提交顺序存在兼容缺口，但不是实际游戏最终可见性的证明。

当前候选保留隐藏时定位及初始化位图，显示成功后立即再提交一次相同内容，补足可见窗口登记后的兼容缓存；静止期间仍不持续重绘。首显示失败及位图提交失败分别检查返回值并写日志。新增 `ENCOUNTER_HUD_WINDOW_READY`、每次 F5 的 `ENCOUNTER_HUD_REQUEST`（时龄/目标窗口/前台窗口/PID/最小化）、`ENCOUNTER_HUD_PRESENT` 和按状态限频的失败日志，避免后续再次无记录地丢提示。

增加 `encounter_hidden_fixture`：仅创建隐藏自有窗口，真实调用 DIB/UpdateLayeredWindow；可选加载既有 DDrawCompat，使用 NORMAL cooperative level 和主表面，不改显示模式、不显示窗口、不加载游戏引擎。普通 API 与兼容层两种隐藏检查均通过；这不是全屏合成/游戏画面验收。候选仅部署共享测试目录，先由玩家重启后按 F5 确认，不发布另一轮玩家 ZIP。

上游来源：[DDrawCompat v0.7.1 Gdi/Window.cpp](https://github.com/narzoul/DDrawCompat/blob/v0.7.1/DDrawCompat/Gdi/Window.cpp)、[WinProc.cpp](https://github.com/narzoul/DDrawCompat/blob/v0.7.1/DDrawCompat/Gdi/WinProc.cpp)。本轮只读研究快照与现场日志、原件和回滚证据保存在 `build/encounter-hud-visibility/`，不提交商业引擎或完整游戏副本。
