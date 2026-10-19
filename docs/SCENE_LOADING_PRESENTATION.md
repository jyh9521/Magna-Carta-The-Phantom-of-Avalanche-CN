# 换区前 Loading 呈现候选

2026-10-19。适用当前源锁引擎及D3D7驱动。状态：**已完成离线验证及共享入口整合，实机待验收**。
不是场景切换崩溃修复，不保证减少资源加载总耗时；原同步清理、读取和初始化顺序不变。

## 改动及版本守卫

`src/runtime/scene_loading.cpp`只替换MCAlpha RVA`63075`的5字节CALL，原字节
`e8 e1 00 00 00`，原目标`6315b`。该调用位于场景循环返回之后、旧场景清理之前。
钩子仅在作业管理器`f2250+30`的下一作业为`1f`（探索Field）时绘制；
返回标题、菜单、战斗及退出保持原行为。新场景首次启动没有旧探索场景清理，不由此钩子覆盖。

预备画面为自有320×180深色像素画布，居中`LOADING...`和静态短线，不显示虚假进度。
像素在安装钩子时准备，不在切换点读取图片、创建纹理、加载字体或申请画布。
它是原生Loading之前的独立简洁提示，不把原版Loading资源读取前移。
静态画布按现有后缓冲尺寸填满；最终窗口缩放继续使用既有窗口呈现路径。

执行顺序：

1. 验证当前驱动、renderer虚表、后缓冲、尺寸及函数指针；原生BeginScene标志必须为0。
2. 从现有后缓冲surface获取DC，通过`StretchDIBits`写入整帧提示，刷新GDI并释放DC。
3. 调用现有renderer虚表`+14`的UpdateFrame，保留既有60帧节拍及窗口缩放钩子。
4. 恢复Win32 LastError，再原样调用`6315b`一次。

不引用旧World／Camera，不清空纹理表，不跳过析构，不改资源队列、不新增加载线程。
surface忙、丢失、GetDC／ReleaseDC失败或原生呈现失败时不循环重试，不阻断原清理。
不吞访问违规；意外硬件异常仍沿异常路径传播。线程内重入不重复呈现。

安装核对PE32/I386、引擎timestamp=`3ed73966`、SizeOfImage=`10b000`、循环前缀和原CALL；
launcher另验证完整引擎SHA256：
`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
驱动timestamp=`3c2b7d28`、SizeOfImage=`2c000`、虚表`1a5a8`，
Clear槽指向`3d3e`、BackOut槽指向`6522`；磁盘完整驱动摘要仍由共享清单检查：
`00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29`。
卸载精确核对已安装CALL并恢复原5字节；代码页原保护恢复，外来钩子或漂移时拒绝。

## Verified：图形调用与原始流程依据

本轮核对驱动`3262 → 3155`：UpdateFrame调用必要的EndScene，然后走窗口Blt或全屏Flip。
驱动`6522`的BackOut也使用同一后缓冲wrapper`+38`及surface`+4`；
GetDC接口偏移`44`，ReleaseDC接口偏移`68`。候选采用相同COM ABI，
但不复用原GetDC包装器的无限重试，不调用其固定256字节vsprintf路径。
管理器`0ca25`在外层派发前读取并清空下一作业；旧场景清理前仍可读取下一作业1f。
`703de`、`72a55`、`72b56`等原始调用点向同一管理器请求1f，支持Field→Field条件。

REA证据：UpdateFrame `ev_df861b91083893022b9a8f85090656520424ae6b202de431e93f2cdeb74b1997`；
BackOut `ev_5eab41651e6a6e1f84e73c7045a8d30de97b6d5a16562eeab819eea965e43b79`；
ReleaseDC `ev_f642bc9a7c6f92a7ecd47b72a470bc7a833c798c60ca7f541cf02030b2e93e42`；
管理器读取 `ev_521e3eb679e30a50c78d6e4d2484c7974b8a265c819d773ceb9075533d99af1b`。

## 离线验证与限制

`scene_loading_fixture`创建自有PE布局、清理函数、COM边界和真实GDI内存DIB。
它执行生产CALL安装和生产钩子，验证整帧像素、DC释放→呈现→清理顺序及LastError保留，
不创建游戏进程、可见窗口或真实游戏D3D设备，也不加载商业DLL。
原生驱动真实设备／兼容层行为仍待实机确认；自有表面成功不等同游戏画面通过。

```powershell
cmake --build build/native --config Release --target workspace_profile scene_loading_fixture
build/native/Release/scene_loading_fixture.exe baseline
build/native/Release/scene_loading_fixture.exe modified build/scene-loading-evidence/loading.bmp
build/native/Release/scene_loading_fixture.exe rollback
$env:PYTHONPATH='runtime/dependencies;tools;tests'
python -m unittest test_scene_loading
```

baseline预期exit1：旧帧保留、呈现0次、清理1次；modified预期exit0：画面写入且先呈现后清理；
rollback预期exit1：原字节及旧帧行为恢复。失败条件属于自有表面的呈现顺序断言，
不是用户实际游戏停顿的已复现红绿闭环。真实时延没有离线测量。

## 共享入口、撤回与重建

正常`runtime/Play.cmd`仍使用唯一`runtime/data`。事务新增`modules/scene-loading.dll`，
只更新`Start.ps1`和`runtime.json`，保留全部已有模块、设置、存档、商业资源及旧统一ZIP。
`MC_SCENE_LOADING=1`仅作用于此候选；父进程环境在成功或失败后恢复。
GUI父节点和楼梯守卫独立保留；baseline配方不启用本候选。

手动临时关闭（不是本轮自动执行的命令）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -WithoutSceneLoading
```

此方式仍保留GUI／楼梯守卫，适合作为单变量对照，优于直接改用Play-baseline。
退出游戏后完整撤回：

```powershell
python tools/integrate_scene_loading.py --rollback build/scene-loading-evidence/integration
```

事务核对当前控制文件、候选及备份摘要，漂移拒绝，部分写入失败补偿；
沿用共享入口互斥锁，入口活动时不执行文件事务。隔离回滚使用微型自有清单和模块，不复制整套游戏。
重建支持`prepare_shared_runtime.py --scene-loading DLL`；统一包构建器记录呈现候选但仍标记
`in_game_verified=false`及`scene_transition_crash_fixed=false`。本轮不生成新发行ZIP，旧ZIP不包含该候选。

## 手动验收（约3—5分钟）

1. 测试者手动运行现有Play入口，加载已有出口附近存档，保持当前设置不变。
2. 正常A→B→A往返3轮，录制从触发前约3秒到新场景可控制的过程。
3. 观察旧场景是否立即被深色Loading替代，有无闪烁、拉伸异常或长黑屏；
   原版后续Loading仍可能出现，提示静态不动并非进度卡死。
4. 如有问题，从菜单退出后使用WithoutSceneLoading对照一轮；不覆盖唯一存档。
5. 下一次启动前保存runtime/cache中的profile.log；
   `SCENE_LOADING_PRESENTED`只证明呈现调用成功返回，不证明肉眼画面或加载耗时验收。
   `SCENE_LOADING_SKIPPED`表示该次可选呈现没有成功，不改写为修复通过。
6. 提交A/B名称、方向、录屏及日志；关闭原入口或异常对话框结束测试。

本轮没有启动游戏、设置程序，没有切换显示模式、挂载镜像或结束游戏进程。
