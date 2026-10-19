# 带缩放的模型世界变换：复验后的相位修正

2026-10-19。玩家复验上一轮后报告：左下暗条；走动仍眼球外突。
原“补齐刚性renderer”仅覆盖一种可能路径，没有解决本次实机症状。

## Verified：玩家日志与旧生产分支

本轮开始立即保留runtime/cache/profile.log到build/affine-world-repair/player-profile.log。
日志没有MOTION60_RIGID_APPLIED，因此不能据上轮自有双renderer回放断言眼球走刚性路径。
多个窗口draws=480、world_draws=240、world_skipped=240；另有draws=540、world_skipped=300。
骨骼已在中间相位，世界变换仍大量旁路。按现有absoluteHook的分支，这些world未通过rigid守卫。
world_skipped不记录具体矩阵，不能据此把眼模型ID或某个缩放值写成实测。

原世界变换只接受近单位尺度proper rigid矩阵，骨骼则早已接受缩放、剪切与反射。
故同为蒙皮对象时，身体可插值，带缩放的部件world仍显示当前原生tick；
补另一rigid renderer的入口并不改变这个旁路。

## 反馈回路

增强rigid_motion_fixture的--affine-skin：两对象都走真实安装的skin vtable入口，
同一逻辑时钟；部件世界矩阵含0.5尺度，局部坐标相应补偿，两个原生端点恰好重合。
旧生产代码在tick起点输出body=0、part=20，退出1。
新代码遍历0..32余数相位，部件与身体始终相等，世界尺度和原生pose/world按字节恢复。
--reflected-skin还覆盖负X尺度；对象缓冲后紧贴NOACCESS页，检查布局边界。
这里的0.5是自有复现输入，不是玩家眼球模型的已测参数。

## 修正

TransformTrack新增sampleAffine，仅供模型世界轨迹使用；保留原sample的rigid守卫和所有相机行为。
复用已验证的极分解／稳定反射插值，保留缩放、剪切、手性、同tick稳定性、切场景与追帧保护。
奇异、非仿射、非有限或病态矩阵仍原样旁路；不把相机改成可缩放矩阵。
皮肤骨骼、模型world和相机仍用同一33ms余数，不改游戏逻辑计时、事件、碰撞、存档。
新增一次性MOTION60_AFFINE_WORLD_APPLIED记录实际命中骨骼数，不输出姿态数组或对象地址。

## 验证与复验入口

```powershell
cmake --build build/native --config Release --target rigid_motion_fixture motion60_fixture render_timeline_fixture
build/native/Release/rigid_motion_fixture.exe --affine-skin
build/native/Release/rigid_motion_fixture.exe --reflected-skin
build/native/Release/render_timeline_fixture.exe
```

数学夹具2309检查，蒙皮/刚性/缩放/反射钩子及SEH/三slot恢复通过。
在独立源码副本恢复三个原文件后重新构建，重新出现body0/part20，活动源码保留修正版。

High-confidence deduction：该缺口解释了移动时身体与带缩放部件分离，和本次日志旁路相符；
但实际眼部归属和新模块最终画面仍以玩家复验为准。直接使用原runtime/Play.cmd，保留现有设置。
不让玩家另找测试包，也不把自动回放称为眼球实机已通过。
