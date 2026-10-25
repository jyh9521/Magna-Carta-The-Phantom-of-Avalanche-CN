# 继续游戏首帧异常调查（2026-10-23）

## 已验证的现场证据

本次人工启动的共享入口日志记录标题 phase 11→12、四次高清文字纹理创建，随后
`world=1`，再出现失焦记录并退出。截图显示 Exception 对话框及地址
`0x7003a52c`。日志、截图、原有存档和设置摘要已在本地保留。

原生 Core.dll 的默认 `Exception` 标题分支在对话框后调用 `exit(0)`，因此启动器的退出码 0
不代表读档成功。截图位置字段来自原始异常记录；该字段不足以确定模块归属，
也不等于已经获得故障调用栈或异常码。

当前普通入口没有开启 `--capture-exception`，这次现场没有异常转储。
首次场景键盘采样已经返回；近期连招字段读取受战斗场景作用域限制，
没有证据把这次首次 field 异常归因于连招精准窗修正。

**状态：游戏崩溃根因未定，尚未修复。** 不把下面的诊断链通过写成读档修复。

## 已修复的取证链缺口

原 capture_helper 仅允许 build 树内目标和输出，不能直接用于共享运行目录。
现在新增明确的 `modules/capture_helper.exe → data/MagnaCarta.exe → cache/engine-*.dmp`
布局支持；真实目标同时锁定游戏、Core.dll 和 MCAlpha.dll 的完整 SHA256。
输出必须在同一共享目录 cache 内且尚不存在，不允许覆盖已有证据或捕获无关目标。
原 build 布局和自有异常样本保留。

正常入口行为不变。`Start.ps1 -CaptureException` 才显式开启原有 Core 异常钩子；
`Play-diagnostic.cmd` 复用 configured 配方、同一游戏数据、存档和增强设置。
转储在原异常框前由独立 helper 保存，之后保留原对话框和退出行为。
不捕获所有正常输入、不吞异常、不通过关闭增强来规避症状。

## 非交互红绿验证

自有共享布局只复制四个自有二进制，Core 是返回 42 的测试 DLL，而非商业文件。
真实生产异常钩子委托 helper，完整内存回读故障样本的原始 0x78 异常与堆哨兵：

| 状态 | 共享布局转储 | 原对话框返回 |
| --- | --- | --- |
| 原 helper | 拒绝，0份 | 42 |
| 新 helper | 成功，1份，原异常/堆内容可回读 | 42 |
| 独立副本恢复原 helper | 再次拒绝，0份 | 42 |

无关进程、已有输出和逃逸路径另行验证拒绝且不写入。
上述测试没有启动游戏、显示窗口或切换显示模式，不证明真实游戏已成功捕获现场。

```powershell
cmake --build build/native --config Release --target capture_helper capture_core_fixture workspace_profile
python tools/verify_shared_capture.py --bin build/native/Release --helper build/native/Release/capture_helper.exe --output build/NEW-shared-capture
python -m unittest discover -s tests -p 'test_shared*.py' -v
```

共享目录生成器可选 `--capture-helper` 参数；只有提供有效 PE32/x86 EXE 时才
复制 helper 并生成诊断入口，未提供时不会留下缺依赖的入口。
源码 `src/configuration/StartShared.ps1` 是运行目录 Start.ps1 的模板。

## 下一次人工复现

关闭已有游戏后，由测试者手动运行共享目录 `Play-diagnostic.cmd`，点击“继续游戏”。
如弹出异常框，等待自动转储完成，再正常关闭对话框。
`runtime/cache/profile.log` 中 `ENGINE_FULL_CAPTURE_PASS` 和实际新增
`engine-*.dmp` 才表示该次保存成功；没有文件不宣称已取证。
下一步依现场模块基址、原始异常记录、寄存器和资源对象定位失败调用。

完整内存仅保留本地忽略目录，不加入提交或更新包。当前 minidump 工具对 C++ 异常
恢复仍有限，须按现场类型检查 Core 包装对象，不把未恢复记录当作没有异常。

诊断入口事务只新增自有 helper/入口并更新 Start/manifest，保留活动12份增强模块、
游戏数据、存档、设置和本次旧日志。变更、精确撤回和原始输出保留在本地
`build/continue-game-crash/VERIFICATION.txt`。

## 回归与取证状态

完整回归852项通过（1项按条件跳过）；随后新增的集成事务7项单独通过。
共享布局生产钩子、原build布局、显式参数路由和隔离精确撤回均通过。
Core静态证据、现场原日志和截图均保留；游戏仍由测试者手动复现，尚无本次游戏完整转储。

## 2026-10-23 人工复现后的完整转储定位与修正

**当前状态：已修复现场对应的钩子后置空指针读取；离线验证通过，继续游戏仍待人工复测。**
前述“没有转储、尚未修复”是诊断入口安装前的历史状态。

### 已验证

诊断入口实际保存了完整转储，原始读取异常为 `0xc0000005`，线程 57468：
`scaled-font.dll` 基址 `0x70010000`，故障 `0x7003a52c`，即模块 RVA `0x2a52c`。
故障指令为 `cmp dword ptr [esi],6`，ESI=0、读取地址=0；EDI 的对白对象
`0x1f9649f8` 仍可读，phase=2，文本源长度=1。栈中保存的字段地址为
`0x1f964b88`，恰是对象+0x190。不是凭截图猜测的驱动故障，也没有对象已释放的现场证据。

旧生产 `tickHook` 在原生更新前将对象+0x190 缓存在 ESI，更新后虽然重新检查
对象可读，却通过旧 ESI 读取 phase。修正将后置检查和原有语音清理移入
`noinline finishTick`，对象自身另存为 volatile 栈槽，在原生回调返回后重新读取；
语音等待的 finally 计时器恢复也使用该槽。仅拆 helper 会改变寄存器分配，可能把
对象本身放入 ESI，导致清理静默跳过，因此不能只测“不再崩溃”。

没有关闭对白增强、语音等待或原生剧情更新，没有吞掉访问异常。
新增自有 x86 夹具真实调用生产安装后的虚表钩子，主动构造现场 ESI=0 条件，
检查 phase 2/3/6、语音 waiting→confirmed 清理和 finally 计时器恢复。
原源文件独立重建：4项失败，出现空地址读取且缺少 confirmed 清理；修正版：4项通过。
隔离撤回恢复原源码后重建，再次出现同样4项失败；活动运行目录保持修正版。

只读工具 `tools/replay_captured_dialogue_tail.py` 还用转储中的真实寄存器和对象回放
旧模块故障尾部，在同一指令精确复现空读；新生成 DLL 从 `[ebp-1c]` 重载对象，
正确读取 phase 2。新栈槽由已捕获对象身份显式适配，VirtualQuery 使用转储的
MEMORY_INFO 契约，不伪称新栈帧已存在于旧转储，也不重跑游戏入口。
本轮原模块 SHA256 为
`2d259d2b58c907b64d5691286ebff93043a8fcc5ca1773f3a546591f3ba7a01a`，
修正模块为 `5230b57e4220d1f91fce33b4bb13bdf07cf10cd4cff8e50cec8922685833abfd`。
重新构建的语音链夹具也通过：原版 Miles 实际播放1598号语音尾段，原生
`49ecb` 启播、`6329` 查状态，生产钩子保持45次更新，播放状态4→2后
原生 `5c13e` 完成并将对白 phase 3→6；音量0、源文件不变、精确撤回。
该项是隔离原生函数/真实音频链验证，不启动游戏，也不是全程剧情画面验收。

### 尚未证明

完整转储是故障时刻快照，不是每条原生调用的时间序列。快照重放原生更新的
phase 0至6分支没有重现 ESI 被改写；究竟哪条间接调用首次破坏该寄存器仍未定位。
主动清零寄存器夹具只验证现场条件和补丁健壮性，不构成其最深层来源证明。
离线验证不替代测试者手动点击“继续游戏”，不宣称整段剧情或全部读档已验收。

复现输入、成品检查、原始命令输出、更新事务与精确撤回记录保留在本地忽略目录
`build/continue-game-fix/`，完整转储不加入仓库或更新包。

```powershell
cmake --build build/native --config Release --target dialogue_post_tick_fixture workspace_profile dialogue_reveal_fixture dialogue_voice_chain_fixture
build/native/Release/dialogue_post_tick_fixture.exe
python -m unittest discover -s tests -p 'test_dialogue*.py' -v
```

## 已安装错误更新包后的修复交付

测试者随后反馈“不错，可以用了”，确认修正版解决了本次继续游戏故障；该反馈
仅覆盖所报场景，不扩大为全流程验收。模块摘要仍为上述 `5230b57e...`。

`tools/build_continue_game_update.py` 将上一版玩家包的**已安装状态**作为基线，
不使用本地新增诊断入口后的整份运行清单替换玩家清单。仅修改12份自有模块和
清单中对应摘要，其余运行元数据、资源摘要、存档和设置保持不变。

旧更新器固定使用 `.text-runtime-update`，后续包直接复用该目录会被既有 installed
记录拒绝。修复包使用独立的 `ContinueGame-Fix-20261023` 脚本目录和
`.continue-game-fix-20261023` 撤回目录，完整保留旧脚本及旧撤回记录，不要求先撤回旧更新。
脚本默认目录以 `.` 结尾，避免批处理尾部反斜杠在 PowerShell 参数解析时破坏引号；
真实含空格路径的批处理红绿测试覆盖该问题。

交付为 `MagnaCarta-continue-game-fix-20261023.zip`：关闭游戏后，将全部内容解压至
有 `Play.cmd`、`runtime.json` 的共享运行目录，再双击 `Repair-ContinueGame.cmd`，
看到 `REPAIR PASS` 后手动打开原 `Play.cmd`。**仅解压并不会完成安装。**
重复运行只检查已安装状态；遇到混合版本或未知摘要整批拒绝，不盲目覆盖。

`tools/verify_continue_game_update.py` 对实际交付 ZIP 执行旧包 CheckInstalled →
修复安装 → 重复运行 → 精确撤回 → 旧包 CheckInstalled → 混合版本拒绝 → 重装。
夹具只含12份自有模块、运行清单和自有存档/设置/旧撤回哨兵，不复制完整游戏。
详细命令、输入和原始输出位于本地 `build/continue-game-release/`。
