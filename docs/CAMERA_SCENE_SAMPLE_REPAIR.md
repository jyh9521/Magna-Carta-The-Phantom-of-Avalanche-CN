# 临时投影与最终场景相机采样分离（2026-10-14）

## 玩家结果与现场标量

最新玩家反馈：模型不抽搐，但镜头抽动。人物模型这一项获得该场景的视觉反馈，
不代表剧情/战斗全覆盖或完整60FPS动作已完成。镜头仍待本候选验收。
当前profile.log（2026-10-14 14:41:56）在区域任务c0f20中显示：
world_unstable=0，多数骨骼resets=0；camera_draws约2970-3046/秒，
camera_unstable约29-31/秒，而呈现约60Hz、逻辑约30更新/秒。
高相机采样数说明同一相机矩阵被多路临时加载，不直接证明每次加载就是镜头帧。

## Verified：源提交点

支持MCAlpha.dll SHA256 5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427。
REA/Ghidra对RVA1d9d9只读反编译及指令观察，Evidence
`ev_5afe63cc759964c3f18ba8aed409265c0fa91c03d9d9dd90eb0aa33baeb95bcd`：
- 活动相机+80传给MODELVIEW Multiply(vtable+2d0)。
- CALL在RVA1da20，六字节为ff92d0020000，返回RVA1da26。
- 静态直接调用者包含60dcb、6187b、62159、631a0、8ae8a、b1914、b64df。
区域631a0先登记场景，随后通过1d9d9设置最终相机，再ASRRender消费队列。
47416的相机load处于物体屏幕位置计算的临时push/pop范围，其后调用人物登记。
该前后顺序见MOTION_QUEUED_WORLD_REPAIR.md的源证据。
1db27通过LookAt重建原生camera+80，不是应被插值样本收集替代的逻辑步骤；
Evidence `ev_506c02d6b379708a3cfd40dbd94655b683a7efd2e8d30f3307ae5a01710bc2b4`。
这些是静态源证据，不是本轮商业游戏执行。

## 生产缺陷的受控回归

旧钩子在所有camera+80的临时Load/Multiply处都更新同一TransformTrack。
新tick临时投影先看到旧相机0，随后原生刷新为-20；同tick最终场景加载时，
旧钩子把该变化视为不稳定输入，丢掉previous/current并立即显示-20。
自有x86调用桩在engine+1da20发出同形虚表CALL，真实返回地址为engine+1da26，
另一个桩发出临时Load；两类调用经过实际安装的driver hook，而不是传入伪造分类布尔量。
旧核心回归失败：
`FAIL temporary projection must not commit stale camera as new tick interpolation endpoint`。

修正后仅scene_commit精确返回点提交相机历史。临时投影和未知调用点原样传递，
不更改history、不触发freeOrbit输入积分、不修改原camera数组。
安装完整动作钩子校验源CALL六字节；已绑定引擎的driver安装同样检查。
源漂移拒绝，不默默把未知位置当作最终相机。
人物queued_world、骨骼准入/层级/过渡历史、原33ms逻辑和限帧纪元不改。

996项钩子检查通过：32个余数，每个插48次临时投影；晚刷新0->-20->-40；
临时加载-999不污染最终轨迹；原相机不变；源指令漂移/恢复；既有世界/骨骼/SEH恢复。
临时投影输出仍为原生矩阵，最终scene输出为共享相位的连续中间视图。
真正最终场景的同tick源突变、传送和切镜重置保护保留，不通过放宽容差掩盖变化。
独立三文件源回滚重编译恢复893项基准。场景之外未知最终提交路径不在静态直接调用者完整性证明内。

## High-confidence deduction / 待玩家确认

早期临时加载与晚期刷新混进同tick历史，与现场每秒约30次camera_unstable吻合；
受控回归证明该具体路径会跳镜头，不证明玩家所有镜头抽动只来自此原因。
完整60FPS仍未完成；不自行启动商业游戏。后续以新日志的sample_source和
camera_draws/unstable确认实际命中，再结合画面，不以测试绿代替肉眼验收。

## 手动验收

同runtime/Play-motion.cmd、同存档，待机10秒→直走10秒→转身10秒→停步10秒，
重复两次。重点看镜头跟随、停步后镜头是否还跳动，以及人物仍不抽搐。
正常退出。新日志应包含sample_source=scene_commit return_rva=1da26，
camera_draws只统计最终场景样本，临时投影不再累计其中。
再测换区和正常镜头切换；真正切镜允许原保护重置。Alt+Tab仍搁置。
组合入口保持同候选；Xbox、汉化、标题背景和默认配置不变，游戏数据仍唯一runtime/data。
