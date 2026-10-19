# 场景切换崩溃调查（2026-10-19）

## 当前状态

**根因仍未确定，未交付新的场景崩溃修复。** 本轮不把未经验证的解绑候选、
固定延迟或异常吞掉逻辑整合进正常启动，也不把重打包当作修复。
现有正常Play/Configure、楼梯高度修正、8份旧模块、baseline及统一测试包保持原字节。
没有新增玩家入口，没有启动商业游戏，没有要求玩家提前游玩或准备存档。

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
下一次原生Bind或最后解绑可正常释放它。**未解绑不等于UAF，合法保留引用不是崩溃证据。**
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
