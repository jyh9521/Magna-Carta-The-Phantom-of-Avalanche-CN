# 通用移动碰撞修复候选（2026-10-24）

MOVE-02以多地图贴墙、狭路及场景物体接触软锁为目标，不采用水之迷宫专用坐标、
地图编号或存档修改。剧情258开场的正常黑幕不处理，声音后端候选不启用。

## 已确认的锁死链与尚未复现的入口

MCAlpha SHA256为7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e。
6ed4e对八个偏移及中心逐一检查；任意起点位于实体时，将结果、速度和反射输出清零，
包括本来向外移动的请求。这是可独立复现的锁死分支，不证明现场首次穿入的原因。
65699完整玩家物理先进行中心向上15单位探测，再分别求X/Y位移、向下15单位探测及Z运动。
因此只在6ed4e内部修一个返回分支，不能覆盖整个位置提交过程。

水之神殿标签的614–617/736–739对应Map27–30、GID28–31。
这些标签仍不直接等同于反馈中的“水之迷宫”；中央建筑的现场资源身份尚未确认。
180次/份的随机起点扫描只对可进入的自有包围盒起点执行原生65699，没有得到确定的新穿入反例。
不得将该扫描写成“水之迷宫中央建筑已复现”。模型包围盒为自有测试尺寸，不是现场角色尺寸。

## 候选实现

`collision_guard.cpp`在原生65699的完整9字节序言处建立可精确撤回的跳板，仍执行原物理一次。
原生函数结束后对拟提交位置作补充检查，并通过原生4cc88同步实际位置和可视对象位置。
不替换原生加速度、重力、反射、动画或朝向计算。

- 仅处理Field当前玩家：c11e4、scene c12bc、mode=2、event lock=0、三个场景门=0、探索GUI ready=1。
  剧情、事件锁定、非玩家和未就绪对象原样运行。安装默认关闭，由专用入口启用。
- 偏移直接读取65c83→47bef使用的`((actor+2dc)->140)->58 +20`的96字节八个向量，
  不用自拟半径替换实际玩家尺寸。检查与原生横向求解一致的15单位抬升空间，不改变物理角色尺寸。
- 正常位移原样保留。位置路径以不超过1单位的最大分量步长验证；首次新增碰撞处二分14次，
  只提交已确认可站立的前缀。大于128单位的非正常物理不连续保留已知有效起点，不猜测路径。
- 初始已重叠时，在同一高度以0.5单位半径递增、16方向寻找最近的已确认可站立位置，最大16单位。
  这是局部碰撞分离，不是固定坐标回城，不向上或向下穿过地板/天花板。
  未找到、查询无效或预算不足时不假定几何为空；深层旧穿入可能仍需另行处理。
- 每次最多4096个原生点查询。点查询8a6a4会改变BSP树的hit/start/end临时状态；每次保存并恢复
  tree+14起28字节，以及调用前后的LastError。新增查询不覆盖正常求解留下的命中法线。

`COLLISION_GUARD_STEP`记录原位置、原生拟提交位置、修正后位置和状态：
1=截断新穿入，2=局部分离，3=超过局部分离能力，4=无效查询/输入；最多记录32次。
既有CONTACT_AUDIO_CONTACT仍是原生求解现场，不代表候选修正后的最终角色位置。
观察器自己的passthrough声明不等于启用修复后整次玩家物理仍保持原行为。

## 已执行验证与边界

自有Win32 RX映像实际执行安装后的跳转：未安装基线接受无效终点、退出1；安装后39项通过、退出0。
覆盖向墙内提交截断、局部脱离、正常位移原样、深层不跨越、剧情/事件锁排除、薄壁路径、未知查询、
栈和LastError、原物理调用次数、可视位置同步、查询缓存恢复、幂等安装及全映像字节精确撤回。
基线的无效物理终点是自有负例，不冒充真实游戏的首次穿入。

`collision_kernel_replay.dll`仅作为自有内核的机器码回放输入，不加载DLL入口。
Unicorn执行编译后的同源内核，其每次几何回调转入真正的8a6a4/BSP递归；没有用Python重写策略假扮修复。
GID28–31四组真实几何均验证：原生四向请求全清零，编译后局部分离位置判空，再向原实体提交被阻止。
该组是中心查询，不是实测玩家八点/动画/画面验收；八点ABI由自有夹具另测。
3项专项回归通过；完整回归921项、3项按条件跳过，其余通过（386.450秒），文档检查48项通过。
共享14项实际安装、重复安装及CheckInstalled通过；独立自有文件副本撤回后14项摘要精确恢复，
新增入口和collision_guard元数据消失。四份原有存档、增强设置、游戏数据和普通入口在安装前后保持。
完整基线、候选、撤回命令和字面输出保存在本轮本地验证记录，游戏未自动启动。

```powershell
cmake --build build/native --config Release --target workspace_profile collision_guard_fixture collision_kernel_replay
build/native/Release/collision_guard_fixture.exe --baseline
build/native/Release/collision_guard_fixture.exe
python tools/replay_collision_guard.py --source runtime/data --kernel build/native/Release/collision_kernel_replay.dll --report build/wall-ingress-20261024/native-kernel.json
python -m unittest discover -s tests -p test_collision_guard.py -v
python tools/build_shared_collision_update.py --runtime runtime --module build/native/Release/workspace_profile.dll --work build/NEW-collision --output dist/NEW-collision.zip
```

## 共享测试版与撤回

共享构建器核对完整文件清单和受支持引擎，更新12个自有模块、runtime.json及新增
Play-collision-fix.cmd共14项。只含自有模块和脚本，不分发游戏数据或存档。
安装器为Install-Collision-Guard.cmd，备份为独立`.collision-guard-20261024`。
已安装候选的目录不可重新当成原始输入构建；从受支持的未安装基线构建。

人工用`runtime/Play-collision-fix.cmd`测试贴墙、物体边角、窄路、上落台阶和水之迷宫中央建筑，
同时确认反向脱离及剧情移动没有异常。该入口设置MC_COLLISION_GUARD=1和既有接触观察，
不启用音效后端候选，不启动黑幕探针。普通Play.cmd默认不启用本候选。
不自动运行游戏、设置程序或改变显示模式；共享安装须在游戏关闭时执行。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Collision-Guard-20261024/Update.ps1 -Action Rollback -Runtime runtime
```

实际中央建筑“靠近即吸入”的现场验收尚未完成，通用保护候选不标成全地图根因已经排除。
