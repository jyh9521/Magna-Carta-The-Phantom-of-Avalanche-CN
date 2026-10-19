# 蒙皮与刚性动画绘制的同相位修正

2026-10-19。玩家反馈：开启60帧后，移动人物时眼球外突。

## Verified

支持 MCAlpha.dll SHA256 `5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。
原插值只安装蒙皮 renderer RVA `3b0c0` / vtable slot `bd9f8`，
只接受 MakeAbsoluteMatrix 返回点 `3b801`。
另一条动画 renderer RVA `3d12f` / slot `bda18` 调用同一绝对骨骼函数，
返回点 `3d534`。它逐刚性子网格注册 world * absoluteBone；原路径完全未插值。
REA `ev_d9e5eed237706a97e3872ae279ce9f178a2e637e962ed497bccd76cb30e5e8ce`。
构造器 `3cd4a` 从 ASRObsStatic 派生；对象布局没有蒙皮的 `f0/f4/f8/fc` 历史字段：
`ev_c428cc2d14d5cba0eb635623e5069037f53ccdb5a7e8f53745597310e684369f`。

生产钩子自有回放按相同输入同时绘制两类对象：骨骼移动10、世界移动20，
相邻tick的起始相位原代码为body=0、part=30，产生整个逻辑帧的分离。
新增 `rigid_motion_fixture` 在旧生产源码失败退出1；改后遍历0..32全部余数相位一致。
这验证的是两条绘制路径相位分离，不是本次玩家眼球的实际资源归属。

## 修正

为刚性renderer增加独立TLS入口，复用同一个33ms逻辑余数和姿态/世界轨迹。
刚性sample从action长度/stride按原生公式推导；不访问蒙皮专属f0/f8。
对象可读范围仅要求d8；未知版本/前缀/调用点/任一slot漂移整批拒绝。
三个slot一起安装/撤销；绘制完成和SEH退出均恢复原生骨骼与世界矩阵。
原逻辑帧数、动画事件、资源和存档不改。两个绘制路径各自保留生命周期保护。

## 复现

```powershell
cmake --build build/native --config Release --target rigid_motion_fixture motion60_fixture
build/native/Release/rigid_motion_fixture.exe
build/native/Release/motion60_fixture.exe
python -m unittest discover -s tests -p test_rigid_motion_native.py
```

## High-confidence deduction / 待实机确认

遗漏的刚性绘制路径会导致混合角色的部件先于蒙皮移动，符合眼球外突现象。
但尚未采集玩家所在场景的眼球模型ID或实际屏幕帧，故不把候选修正称作眼球已实机修复。
使用原 `runtime/Play.cmd` 保留60帧，同存档行走/转身/停止，对照30帧；
确认眼部、武器/附件和身体同步，再测试换区、动作切换与读档。
自动回放不是实际游戏验收。
