# 继续游戏首帧异常调查（2026-10-23）

## 已验证的现场证据

本次人工启动的共享入口日志记录标题 phase 11→12、四次高清文字纹理创建，随后
`world=1`，再出现失焦记录并退出。截图显示 Exception 对话框及地址
`0x7003a52c`。日志、截图、原有存档和设置摘要已在本地保留。

原生 Core.dll 的默认 `Exception` 标题分支在对话框后调用 `exit(0)`，因此启动器的退出码 0
不代表读档成功。截图位置字段来自原始异常记录；它本身不足以确定模块归属，
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
