# 读档崩溃：真实转储分析

## 已验证的首次异常与次生异常

已取得 PID 79424 的 Windows 转储，来自 DDrawCompat 读档失败会话；不是新启动游戏或人工构造的运行现场。原件保留，分析作用于本地副本，转储不提交。
转储记录最终 `0xc000041d`、系统 ddraw.dll RVA `0x3b717`。保存的线程栈还包含更早的 x86 异常记录及 CONTEXT：

- 首次异常：`0xc0000005`，读取地址 `0x78`。
- 首次位置：d3dim700.dll RVA `0x9984`，EAX 为 0。
- 首个帧指针链返回位置：AsrD3DDrv.dll RVA `0x7bb6`；随后为 MCAlpha.dll RVA `0x2649f`、`0x27f2e` 等。
- 最终异常帧链经过系统 ddraw.dll、兼容层 ddraw.dll、user32.dll 和 Core.dll RVA `0x21b4`，位于异常对话框路径。

Core.dll 的异常对话框缓冲区也记录首次地址 `0x68ec9984`、读取目标 `0x78`，与恢复的原始记录及寄存器一致。该文本只用于本地交叉验证，不将全量内存或资源上传。
因此 `ddraw.dll` 的最终异常不是此次最早的故障，不能据最终 Windows 事件把最终异常当作唯一根因。

## 已锁定的调用位置

锁定的 AsrD3DDrv.dll 在 RVA `0x7bb0` 通过设备 vtable offset `0x8c` 调用 IDirect3DDevice7::SetTexture，返回位置正为 `0x7bb6`。参数为纹理阶段 0 和非零纹理表项；调用来自 MCAlpha 的纹理绑定路径。这里是此次首次异常的直接调用点，不是已确认的修复补丁位置。
系统 d3dim700.dll 的磁盘映像与转储模块时间戳及 SizeOfImage 一致；对应代码先取纹理内部指针，再读取偏移 `0x78`。磁盘指令和现场 EAX=0/读取0x78一致，属于高置信解释，不声称未捕获的对象内存已经读取成功。

## 仍缺少的关键证据

转储没有捕获设备对象和纹理对象的完整内存。纹理是否被释放、创建失败后遗留、内部状态损坏或发生接口混用尚未确定。不能只加空值判断、吞掉异常或跳过绘制就报告修复。
已检查驱动中部分释放路径，释放后有纹理表项归零操作；不能笼统断言整个驱动忘记清空缓存。
此转储仅对应 DDrawCompat 会话；D3D11 的 `0xc0000005` 和无层基线的模型/地形缺失分别保持待定位，不直接套用本次原因。

## 已实施的取证与回归改进

`tools/inspect_minidump.py` 检查边界、流目录、x86 架构和模块列表，只在异常线程栈内恢复匹配的异常记录/CONTEXT；同名模块用加载基址区分。帧指针链没有符号信息，不当作完整符号化调用栈。
格式、截断、错误架构、错误关联和巨大目录均有合成回归测试。命令：

```powershell
python tools/inspect_minidump.py --dump LOCAL_DUMP --report build/crash-analysis.json
```

独立 graphics_probe 补充 A1R5G5B5 托管纹理创建、上传、绑定、解绑、释放和重建，覆盖 6 次纹理重建与 120 次绑定；增加 T&L 设备选项 `--device-tnl`。原生 HAL、T&L 与本地 D3D11 探针仍可完成该有限用例，尚未复现游戏对象故障，不将结果当作读档修复。
当前副本保留可读档的无图形层基线。本轮没有启动游戏，也没有改写游戏或系统 DLL；没有新的修复候选需要重复测试。

## 完整对象取证：已实现，游戏现场待采集

现有小转储没有设备与纹理堆对象，故新增独立 `capture_helper.exe`。显式 `--capture-exception` 诊断模式在锁定 Core.dll 的 Exception 对话框调用前，委托独立进程写完整内存转储，随后调用原对话框函数；不吞掉异常、不跳过绘制、不更改原函数返回值，也不修改保护模块。
常规入口默认关闭取证模式。启动器同时验证游戏、引擎及 Core.dll 哈希；helper 限定 build/ 中的游戏或自身故障样本，输出须为 build/ 中的新文件，不结束目标进程。完整转储只保存在本地忽略目录，不提交、不作为发行内容。
Core.dll 锁定 SHA-256：`72c91c8102ee268ef491c41b56180babca90760df31a00075f63aed018d62571`。

```powershell
& tools/launch_workspace.ps1 -Workspace build/runtime/diagnostic-game -CaptureException
python tools/inspect_minidump.py --dump LOCAL_FULL_DUMP --report build/full-crash-analysis.json
```

独立诊断副本从当前可读档工作副本复制并逐文件校验；仅诊断副本加入原失败的 DDrawCompat standard 配置，以重现已知异常并采集对象。正常工作副本不重新启用图形层；两份存档、设置与后续写入分别隔离。该配置是取证重现，不是重新推荐的修复方案。
诊断入口由测试确认后手动启动，本轮没有运行游戏。读档如触发锁定的异常对话框，日志记录 `ENGINE_FULL_CAPTURE_PASS`，并在会话目录生成 `engine-PID-TICK.dmp`。没有该事件不报告成功捕获；其他错误或直接终止仍需另行分析。

已完成非交互测试：50 项单元测试、8 项注册表隔离检查通过；自建异常样本的完整堆标记与首次读取0x78异常均恢复成功；模拟对话框返回42保持，三个目标/输出守卫通过，无可见窗口、无游戏启动。默认和启用模式的实际游戏表现仍分别待验收。
测试用 Core.dll 来自 `capture_core_fixture.cpp`，只用于构建目录中的模拟调用，不能复制到任何游戏目录。
API 依据：[Microsoft MiniDumpWriteDump](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/nf-minidumpapiset-minidumpwritedump)，采用外部进程采集，避免在故障进程中直接执行转储写入。

## 完整游戏现场已采集

PID 11760 的完整取证成功，已恢复首次读取 `0xC` 的异常和设备旧绑定对象字段。针对删除前解绑的实现、版本守卫和待验收范围见 [纹理生命周期候选](TEXTURE_LIFETIME_CANDIDATE.md)。取证工具可用与候选修复生效分别验收。
