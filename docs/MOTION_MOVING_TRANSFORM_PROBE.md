# 移动时抽动：世界/相机轨迹观察（2026-10-14）

## 当前实机事实

玩家最新反馈：待机不抽动，移动时抽动，停止后抽动几下再稳定。完整60FPS动作未通过。
2026-10-14 12:52:27的profile.log显示骨骼unsupported=0、兼容动作桥接已命中；
多个窗口骨骼resets=0。此事实既不证明世界轨迹稳定，也不证明视觉修复。
原生区域逻辑仍为33ms（约30.3Hz）；显示循环目标60Hz。本候选在显示阶段插值，
不是把事件/碰撞/音频改成60Hz逻辑。

## Verified：排除和观测缺口

只读REA核对Asura SHA256 f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557：
RVA38239矩阵乘法与现有column-major multiply一致，Evidence
`ev_b0f52023014d661bcfc86e698bba7c1df48db287fcdc0a031c81728064dd8ce5`。
RVA51a01队列注册复制16个矩阵字，不仅保留object+c指针，Evidence
`ev_8b49744e8cca26d79f20d7aabc355954d699a2d44a41eb937ee4a43451597a17`。
因此这两个具体猜测没有成为改动理由。不能据此排除其他上游变换或顶点缓冲复用问题。
MCAlpha的GetMatrix读取枚举ba6；D3D getter把driver+5c复制出来，Evidence
`ev_7f9c91e2c264f65160aced8f9920e413d1d826e745649f5b387c06e4e373c6a1`、
`ev_bef7ed7743b8d142e5fa05a4fd75c0058a07bce968469acd088ee85935609a83`。

原日志只统计骨骼缓存重置。TransformTrack独立存在同tick输入突变、切镜/大位移、
逻辑世代/追帧、非刚体旁路；这些原因没有进入原统计。
自有实际renderHook回放：同逻辑tick中人物世界位置0->1，骨骼帧和局部姿态不变。
原日志不报告世界重置，新回归失败：
`FAIL actual world hook exposes reset absent from bone-only diagnostics`。
这复现的是诊断盲区，不是玩家实际抽动根因。

## 本次改动：观察，不改插值结果

TransformTrack记录每次sample已执行的原分支。日志追加world/camera两组：
- draws：采样次数，不是游戏帧数。
- initial：首样本/显式缓存重置后的初始化，不是异常。
- phase：世代改变、倒退、跨过一个以上逻辑tick。
- cuts：超过既有位移/相机转向切换阈值。
- unstable：同一个逻辑tick中的源矩阵变化超过既有容差。
- skipped：源输入旁路；world也包括未满足现有相机/空间资格的绘制。
- max_step：该窗口最大源平移差，游戏单位，不是抽动幅度。

两组与骨骼same_frame/resets分别记录；原因可能重叠，不相加当作独立帧数。
只输出聚合标量，限既有120个窗口，不记录演员地址、姿态数组或完整游戏数据。
不放宽容差、不修改采样时钟、不改父空间假设、不调整过渡系数。
264项真实钩子和1511项数学检查通过；旧核心+新钩子回归为RED。
独立源回滚恢复259/1503项基准，活动模块保持新观察字段。
汉化、Alt+Tab、手柄路径和设置默认值不变；商业游戏启动0次。

## 下一次手动验收

用原runtime/Play-motion.cmd，同一存档，进入游戏后立即：待机10秒→走动10秒→
停止10秒，重复两轮；全部在两分钟内，避免超过诊断窗口上限。正常退出。
反馈起步、持续走动、停步阶段；无需期待这次纯观察更新改善画面。
日志仍是runtime/cache/profile.log，每次实际启动重建；VerifyOnly不删除它。
若world_unstable与移动同时增长，继续查原父矩阵和源变换同tick变化；若camera_unstable
增长，查相机重复加载；若两路均稳定，继续查骨骼根变换、绘制批次和顶点缓冲，
不把任意一个计数直接判为玩家抽动原因。
