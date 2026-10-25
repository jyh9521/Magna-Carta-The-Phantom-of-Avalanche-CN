# 实际ANI资源覆盖与稳定反射姿态

## Verified：原生读取布局与本地资源

支持MCAlpha.dll SHA256：
`5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。
REA通过`Ainim\\%04d.ani`引用2c947定位加载器2c88a；加载器读取五个u32，
然后逐骨骼读取(samples+1)个64字节矩阵和变长骨骼引用。
加载器证据：`ev_96d77695975230f2874fe05b26f633380fe88d4f370ab3273c9f3d50047a252b`。
首矩阵用于构造逆绑定矩阵，并按绑定行列式决定原生插值方法。
第一字仅读入局部变量；不把其0/1值杜撰成文件版本。

新增只读`audit_bone_animation.py`依布局严格检查长度、数量、帧/采样关系、
有限数、子引用范围和完整消费；不推断根父字段，允许原文件中的0xcccccccc。
不输出姿态数组，不回写源资源。1,818份实际文件全部解析成功，之后重新核对
每份文件SHA256，全部保持不变。

不含绑定矩阵的实际采样统计：

审计中的bind/dynamic仅按首矩阵与其余矩阵划分；首矩阵用于逆参考，但是否
也参与播放、播放索引如何对应完整资源序列尚未全面核实，不能用此划分推断实际帧数。

| 项目 | 数量 |
|---|---:|
| 采样矩阵 | 2,600,174 |
| 原proper near-rigid谓词通过 | 2,281,614 |
| 反射矩阵 | 189,551 |
| 可通过固定反射轴归一化的near-rigid矩阵 | 173,147 |
| 缩放/剪切超出原容差 | 142,329 |
| 行列式接近零 | 270 |
| 非仿射 | 0 |

类别会重叠，不能相加。统计用Python双精度模拟当前rigid条件，边界舍入
可能与C++float不同；这是序列化采样覆盖，不是全部实际加载姿态或屏幕帧。
例如0002.ani有6,048个动态矩阵，其中630个为反射，不能把问题只归因于绑定姿态。
没有确认该动画是否在玩家当前场景被使用。

## 稳定反射插值修正

旧`blend()`只接受正行列式near-rigid矩阵；反射骨骼直接显示最新原生姿态，
与已插值骨骼可能混用不同显示阶段。旧数学回归失败：
`FAIL stable mirrored bone rotates and translates at midpoint instead of 30Hz passthrough`。
独立编译的旧生产代码配新骨骼夹具也失败：
`FAIL real reflected bone hook must interpolate rather than present latest30Hz pose`。

新路径只接受前后同为near-rigid反射：两端共同右乘固定X轴反射因子，
在proper矩阵上用原旋转/轻微伸缩插值，再恢复该因子。统一因子不改变两端
相对旋转；三个源反射轴均有回归。端点仍逐字节保持，原生姿态在绘制后恢复。
`rigid()`及相机/世界轨迹的准入未扩大；仅骨骼pose与blend增加该能力。
诊断unsupported字段现用poseInterpolatable单矩阵资格，不再把所有稳定反射
列为拒绝；该结果仍不证明任意一对姿态已成功插值。

265项数学检查覆盖61个显示相位、行列式/手性、三种反射轴、精确端点和
原相机守卫。231项真实骨骼钩子夹具通过；独立源回滚恢复152/229项旧行为。

## 未完成范围

173,147只是新增单矩阵资格数量，不是已修复的屏幕帧数量。前后符号变化、
奇异矩阵和较大伸缩/剪切仍保留旧旁路，后续须继续验证原生处理并补齐。
世界/相机非proper变换也未在本轮拓宽。尚无实机证据证明玩家抽搐已消失。
完整60FPS动作仍未完成，不把真实资源扫描或合成回放称作游戏验收。

## 复现与玩家验收

```powershell
python tools/audit_bone_animation.py --source runtime/data/AINIM --output runtime/maintenance/animation-audit/ani-report.json
python -m unittest discover -s tests -p test_bone_animation_audit.py
```

入口`runtime/Play-motion.cmd`：同存档待机30秒，走动/转身/停止，观察四肢、
衣摆和动作切换；再换区重复。与`runtime/Play-baseline.cmd`对照节奏和速度，
正常退出后提供`runtime/cache/profile.log`及具体动作。
本轮商业游戏启动0次，完整游戏复制0份，动画文件与汉化未改。
统计报告、模块摘要与独立源回滚证据在`runtime/maintenance/animation-audit/`。

## 伸缩／剪切骨骼分支（2026-10-14）

Verified：旧生产数学遇到原容差外的仿射姿态仍显示最新30Hz姿态。
旧代码配新增回归失败 `FAIL scaled sheared bone reaches midpoint rather than latest native frame`。
现在骨骼分支使用双精度、幅值归一化的scaled Newton极分解（最多32步），
将proper旋转与伸缩／剪切分开，再插值并重组。固定公共反射因子保留负手性。
条件数估计超过1e6、归一化行列式<=1e-14、不收敛、非有限或非仿射仍拒绝；
相机/世界TransformTrack的rigid守卫及原生逻辑计时未变。端点字节精确，输出非有限时旁路。
1503项数学检查覆盖61相位、非均匀伸缩、剪切、正/负手性、大小均匀比例与退化输入。
真实骨骼钩子233项验证中间显示姿态与绘制后原生绝对矩阵恢复。

新增只读原生bone_pose_audit直接调用生产poseInterpolatable与blend，不导出矩阵。
对1,818份实际ANI再检查计数、长度、子引用、有限数与完整消费，遍历结果：
- 非首矩阵2,600,174个；旧near-rigid+固定反射资格2,454,761个；新资格2,600,174个。
- 相邻非首矩阵对2,528,835个；其中反射符号变化12对，仍按旧旁路，不穿越奇异几何。
- 全部遍历中间输出有限；单矩阵资格与有限输出不证明实际场景动作或任意姿态对成功插值。
- 前次审计绝对行列式接近零270个不等于真实奇异：均匀小尺度可以有很小行列式，
  此次相对尺度/条件检查均通过。不要把前次阈值类别写成270个已证实退化骨骼。
- 遍历约4.9秒是离线批处理时间，不是游戏帧时间；输入1,818份SHA256全部保持原摘要。

复现：先构建bone_pose_audit，再运行
`build/native/Release/bone_pose_audit.exe runtime/data/AINIM`。
完整Python451项通过；独立源回滚恢复数学265/骨骼231项旧行为。
源码复制后必须刷新时间戳或干净重建：Copy-Item保留旧时间可能使MSBuild复用旧夹具，
本轮曾发现265项陈旧结果，强制重编译后才接受RED证据。

人工入口仍为runtime/Play-motion.cmd和Play-motion-gamepad.cmd；同存档待机、
走动、转身、停止、动作切换、换区，检查四肢/衣摆与速度；以Play-baseline.cmd对照。
单独手柄轮询修正保留。当前未获新模块实机反馈，完整60FPS动作继续保持未完成。
没有启动商业游戏、复制游戏数据、修改汉化或原动画。
