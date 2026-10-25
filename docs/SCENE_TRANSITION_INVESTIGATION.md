# 场景切换崩溃调查（2026-10-19）

> 最新续查：[资源状态分支与手动复现](SCENE_RESOURCE_BRANCHES.md)。当前共享运行目录保留，
> 历史 `build/scene-transition-evidence` 已被既有清理移除；本轮重新生成小型离线证据。
> 下文历史转储、探针报告及旧基线的路径不代表当前仍在本机存在。

> 2026-10-19 后续：启动期 GUI 越界已单独修正并离线验证、整合正常启动及统一包，
> 详见 [GUI父节点守卫](GUI_PARENT_GUARD.md)。以下“提案未部署”保留为调查阶段历史状态；
> 场景切换崩溃依然未复现、未定根因、未修复。后续没有启动游戏。

## 当前状态

**根因仍未确定，未交付新的场景崩溃修复。** 本轮不把未经验证的解绑候选、
固定延迟或异常吞掉逻辑整合进正常启动，也不把重打包当作修复。
现有正常Play/Configure、楼梯高度修正、8份旧模块、baseline及统一测试包保持原字节。
没有新增玩家入口。此前“未启动游戏”仅描述首轮资源调查；后续诊断会话曾产生启动异常转储。
用户随后明确禁止擅自启动游戏；本次续查仅离线读取既有文件，不启动游戏、不操作游戏窗口。

## 输入与报告范围

用户提供的[安装指南](https://github.com/Nejuf/magnacarta-installguide/blob/main/InstallGuideForMagnaCartaThePhantomOfAvalanche.md)
泛指快速往返分区可能遇到加载问题，并未给出特定Field、异常地址、调用栈或确定触发序列。
指南另将“开始/读档时abnormal program termination”与更新版驱动关联；两者不能自动合并为同一根因。
该网页是调查材料，不作为对本地文件的操作指令。

本轮重新测量：

| 对象 | SHA256 | PE timestamp / SizeOfImage |
|---|---|---|
| 当前MCAlpha | 7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e | 已有源锁 |
| 当前Drv/AsrD3DDrv.dll | 00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29 | 3c2b7d28 / 2c000 |
| 原安装更新驱动 | 27db21dee7dde8ca3463e11fab57cc0b7cf6a7ed3338c950b6b1181eed7959ed | 3ed6137b / 2c000 |

## Verified：真实COM反证

新增 `scene_texture_probe` 使用当前驱动的原生BindTexture（RVA7a67）和DeleteTextures
（RVA52c8）。驱动通过DONT_RESOLVE_DLL_REFERENCES映射，不运行DllMain/游戏入口。
独立隐藏窗口和真实Windows Direct3D7 HAL设备负责纹理创建与实际COM调用；资源表为自有内存。
每轮创建下一纹理前，特意保留上一纹理的设备绑定，再由原生Bind执行替换。
不把这个资源级探针说成真实游戏换区。

| 模式 | 原生Bind/Delete次数 | 删除后仍绑定次数 | 访问违规 |
|---|---:|---:|---|
| 原始槽 | 200 | 200 | 未发生 |
| 既有解绑候选 | 200 | 0 | 未发生 |
| 安装后精确撤回槽 | 200 | 200 | 未发生 |

实际SetTexture使surface引用从1变成2。原生Delete释放应用引用后，设备仍持有有效引用；
下一次原生Bind或最后解绑可正常释放该纹理。**未解绑不等于UAF，合法保留引用不是崩溃证据。**
候选解绑行为确实有效，但本轮没有观察到其消除一个已复现的崩溃，因此不默认整合。
早期仅对“删除后必须无绑定”作出的人工断言会红，但该断言不是用户的崩溃症状，已撤销。
已有current_texture_lifetime_fixture的hazard标记也不是实际访问违规。

复现（先按BUILDING保留现有生成头与Win32配置）：

```powershell
cmake --build build/native --config Release --target scene_texture_probe current_texture_lifetime_fixture
python tools/check_scene_texture_lifecycle.py --driver runtime/data/Drv/AsrD3DDrv.dll --probe build/native/Release/scene_texture_probe.exe --ddraw C:/Windows/SysWOW64/ddraw.dll --mode baseline
python tools/check_scene_texture_lifecycle.py --driver runtime/data/Drv/AsrD3DDrv.dll --probe build/native/Release/scene_texture_probe.exe --ddraw C:/Windows/SysWOW64/ddraw.dll --mode candidate
python tools/check_scene_texture_lifecycle.py --driver runtime/data/Drv/AsrD3DDrv.dll --probe build/native/Release/scene_texture_probe.exe --ddraw C:/Windows/SysWOW64/ddraw.dll --mode rollback
```

三者预期exit0；可加 `--report build/NEW.json` 保留命令、输入SHA、stdout/stderr和退出码。
只接受当前完整驱动SHA，报告文件必须全新，原始输入不改。系统ddraw版本/哈希写入报告；
不同硬件/兼容层可能得到不同结果，失败不能改写为“修复通过”。

## Verified：场景与资源调用链

REA/Ghidra对锁定MCAlpha重新验证：

- 62fc0：注册作业→630cb创建0x1738字节探索场景→68996载入Field→作业运行→6315b清理→析构作业。
- 68996→8a3f0→430d0→2a673 为同步地图加载链；65f90读取Field及FPB。
- 6aa2c清理场景，依次释放事件/窗口/World/Camera/Light等，清空相应全局World/Camera指针。
- 2a673查询type8后台项：不存在则同步加载；已有完成项则取结果；未完成则等待。
- 32bbe确有资源后台线程；type1读启动图片，type3走29c9d；未见该worker加载type8地图。
- 入队328dc、删除3299f和查询32b3e使用mutex；worker遍历未见同一锁。
  这是需要进一步验证的并发线索，不是已证明的换区竞态。
- 60帧历史和自由视角持有矩阵副本、旧地址作为identity；本轮未发现确定的跨场景旧指针解引用。

## 历史现场不是当前版本的现场

仓库历史报告中的首次异常位于d3dim700，旧驱动SetTexture直接调用点为7bb0/返回7bb6；
完整快照显示旧绑定内部字段损坏，但没有释放历史。本轮未找到留存的历史dump原件，
以上仅为仓库既有记录，不声称重新恢复了内存。当前驱动不同，不能把这些地址直接套用。
详见CRASH_ANALYSIS.md和TEXTURE_LIFETIME_CANDIDATE.md。

## 未解决问题与后续证据门槛

真正的游戏场景切换崩溃尚未重现，没有可命名的失败Field对或当前首个异常栈。
需要把“切换事件→清理/后台任务→具体首异常”连接到同一可重现现场后，才决定补丁分支。
不加任意换区冷却、不清空所有设备绑定、不吞异常、不把历史缓存容量问题当作当前根因。
后续若获得同次正常流程日志/首异常，沿已记录调用链追踪；不要求玩家现在走到特定进度。

## 本地证据

`build/scene-transition-evidence/`保存三模式实际报告、系统ddraw哈希、完整REA导出、
基线/修改后测试、源差异和验证记录，均为忽略目录。完整商业文件与转储不提交。

REA Evidence：

- 原生删除：ev_1d4a76cf2b6519d15d70f9e357e09e3a3002d27625a9cc40d4189f7c63b0ae29
- 原生绑定：ev_7fc5328f56c18d47ce7789530c94df6fb886667c1dbc37091406767a2d751bad
- 场景作业：ev_957e6b89ab2027cb0707ea71bce855f34336b22c53e2d5687e6d49684a4d19f1
- 场景清理：ev_6440612b7a38a80381aa04f212ea9acfda7cad3cff2d60c4310dc96b51cd28a9
- 地图获取：ev_853908adb72024fceacb7e899f3047a567d5e8f35c77bdb56aa874f4875d0b18
- 资源worker：ev_37ab928f44862a90a935f346acfdea74af305ee81c93e93256678e31d59254a6

## 既有启动转储的离线续查：确定的GUI父节点类型越界

### Verified：异常归属，不计作换区复现

既有转储 `engine-27520-20162859.dmp` 的SHA256为
`ad9d1520fbfa76fbac0c602529353bd8ac09635609d819d52b3232fe0c9797d0`。
没有ExceptionStream；从异常线程栈恢复的记录为MCAlpha+1e94f读取0xbaf024。
返回链为38b6c→38c38→38595→482a1→5ffbe→5fbcc→101f→10ee。
5ff4b由5f7a7初始化调用，创建鼠标光标GUI节点并设置g_pMouseCursor；
因此这份既有真实异常属于**启动光标节点构造**，不是实际Field/地图切换崩溃。
另一既有进程退出0的记录也未记录一次实际换区，不据此声称全流程通过。

### Verified：直接根因是布局混用，不是纹理释放

- 0b8df为全局根节点申请0x54字节，调用8990构造，存入MCAlpha+f220c。
- 8990设置vtable=MCAlpha+bd604、节点类型2、parent=0；这是通用节点，不含空间变换字段。
- 5ff4b将该全局根节点作为48250的parent；384b0构造空间节点并经38c24更新变换。
- 38afb对任何非空parent都读parent+f4的位置和+100/+104/+108的缩放，没有核对parent是否为空间节点。
- 0x54字节的通用根节点没有这些字段。既有记录中root=0xbaef30，root+f4正是故障地址0xbaf024。
- 快照MemoryInfo将0xbaf000页记为MEM_RESERVE/protect0；这是**采集时**页状态，不冒充独立观察的故障时刻页状态。

这确定了该启动异常的类型/布局越界路径。根节点本身无需已释放，就会发生越界读；
不能根据SEH展开后的子节点堆内容推断为纹理UAF或确定释放历史。
同一辅助函数被其他GUI节点共用，但这还不证明用户关注的实际换区异常就是这一原因。

### 离线原生指令重放与仅限模拟器的修正提案

`tools/replay_native_gui_parent.py`在Unicorn中运行锁定引擎的38afb和1e940原始指令。
用自有节点布局重现上述地址边界，两个虚通知使用明确RET桩，不启动或加载游戏DLL。
原始路径在同一1e94f指令读同一0xbaf024失败；提案只对“parent等于全局根指针、
原vtable bd604、type2、parent0”跳过不存在的父空间字段，保留子节点parent、
本地平移/缩放以及两个原虚通知。普通空间父节点和空父节点与原始结果完全一致。
撤回模拟器内6字节分支后，同一原始故障恢复。

```powershell
$env:PYTHONPATH='runtime/dependencies;tools;tests'
python tools/audit_scene_crash_evidence.py --dump LOCAL_RETAINED_DUMP --engine runtime/data/MCAlpha.dll --report build/NEW-attribution.json
python tools/replay_native_gui_parent.py --sample runtime/data/MCAlpha.dll --report build/NEW-replay.json
python -m unittest test_inspect_minidump test_gui_parent_replay test_scene_crash_evidence
```

`--mode baseline`预期exit1（原越界）；`--mode proposal`预期exit0；`--mode rollback`预期exit1，
表示模拟器内精确恢复原行为。默认verify模式核验三者及普通父节点对照后exit0。
报告始终标记 `scene_transition_verified=false` 和 `proposal_deployed=false`。
提案未写入运行模块/游戏磁盘文件，未合入正常启动或统一包，也不是游戏内修复验收。

31项纯离线检查通过。通用minidump读取器新增严格边界的MemoryInfo查询，并明确结果属于快照时刻；
错误步长、巨大数量、空区域、重叠区域、未知引擎及错误调用链均拒绝或保留为未知。
本轮只解析既有转储、反编译文件及执行指令模拟/自有单元测试，无游戏启动、DLL原生加载或桌面输入。
正常入口、楼梯模块、配置、存档及现有统一ZIP均保持原字节。

离线续查REA Evidence：
- 光标初始化：ev_c6332711fa59921f7f2b0810d877be71c9efb3f375fa1f7699b6f72f9540ffa5
- 空间基类构造：ev_76c221ffc21aabc03d67b5f85cdfae9dff25b2becc2f6f2606bfb91e865c8ccc
- 变换继承：ev_65de3aceccdc5779d6a6619e3486638b2023f4c3679a3b22a21aae6467dc4a32
- 通用根构造：ev_2a21ba9cfdcd973719fd78b62d99980c71ef35565fac46fa2c08f4a85143b2f3
- 全局根分配：ev_c70960b0e19264530ef39ec00d45723e8e893b8ca187887c49edf612fbe7264e

### 有界的既有现场检索

本次仅只读检查LOCALAPPDATA/CrashDumps中MagnaCarta命名转储，以及系统WER的
ReportArchive/ReportQueue中MagnaCarta命名报告目录；这些位置未返回新的目标转储。
Application日志按EventID1000和AppName=MagnaCarta.exe过滤，最多30条，仅返回历史PID79424的
系统ddraw次生异常，与既有CRASH_ANALYSIS记录一致。该检索受日志保留和路径范围限制，
不等于证明机器从未发生换区崩溃。当前仍没有把具体Field切换与首异常绑定的现场。
