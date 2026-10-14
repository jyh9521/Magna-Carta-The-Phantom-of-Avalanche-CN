# 同骨架动作切换的显示连续性（2026-10-14）

## Verified：原生对象与绝对矩阵结构

支持MCAlpha.dll SHA256 5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427；
Asura.dll SHA256 f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557。
REA/Ghidra只读反编译MCAlpha RVA3b0c0（ev_ba778b5a7bfbfc3380d19d326da11eccb3b30907ac6e32a5eb45c4e2c7c67c54）：
object+8为模型，+a0为动作；动作+18按采样选record，record+4为data，data+14为骨骼数，
data+1c传入MakeAbsoluteMatrix。原生在此调用前完成采样和过渡，并将局部姿态复制到object+f0。
Asura RVA44f0d（ev_e533b891ab95926b916f933578c62d29aa489852b7383415d21003c083205cf8）：
ASRBone步长12，+4是子数，+8是子索引数组；该函数不读取首字。按根0递归，
将父绝对矩阵与本地矩阵组合。因此数组地址本身不代表层级不同。

## 生产回归与改动

旧缓存对action/bones地址变化无条件重置。自有骨骼钩子重放“旧动作最后姿态→
相邻逻辑更新的新动作第一姿态”，模型/姿态数组和层级一致而资源地址不同，旧代码失败：
`FAIL compatible native action switch begins at previous local pose instead of resource snap`。

新路径比较完整的根0层级子索引序列，不用哈希近似、不输出姿态或内存地址。
只有同模型、同姿态缓冲和骨骼数、完整无环单根树、同世代、相邻逻辑tick、
未超过原250ms年龄条件时才允许跨动作继续已有一帧延迟插值。
同动作资源变化还要求原长度/stride未改变且帧相邻或原生循环；动作切换允许新动作帧编号。
隐藏的同地址层级变化也会重置。层级不可读、子索引越界、重复父、循环、
不可达节点、模型变化、追帧和同tick动作突变不桥接。
原生输出先计算并保留，绘制后逐字节恢复；原生采样、过渡历史、逻辑计时均不改。
相机与世界变换轨迹不因单纯同骨架动作地址变化而清空，但原场景/矩阵保护仍保留。

248项骨骼钩子检查覆盖单骨与双骨的不同地址同层级、连续中间姿态、精确恢复、
同地址层级变化、越界/循环、模型变化、同tick突变与追帧。独立源码回滚恢复旧233项。
MOTION60_DIAG新增标量compatible_switches，便于区分兼容桥接和真正资源重置。

## High-confidence deduction / 未验证项

同拓扑和模型的已验证相邻切换应该保持显示连续；这不证明玩家可见抽动全部来自该分支。
上一份日志resource每秒数次包含真实动作变化，不是“错误重置”的直接实机计数。
尚无新模块实机日志或画面验收，完整60FPS仍未完成；反射符号变化、跳帧、其他
资源/状态生命周期继续调查。不会把回归绿或静态反编译当作玩家验收。

## 手动验收

使用runtime/Play-motion.cmd，同存档待机30秒，走动→停止→转身反复10次，
观察动作切换是否跳一下；换区后再测，与Play-baseline.cmd对照速度和姿态。
手柄组合仍用Play-motion-gamepad.cmd，前轮真实鼠标轮询修正继续保留。
正常退出后runtime/cache/profile.log包含compatible_switches和resets等窗口统计。
本轮商业游戏启动0次，完整数据复制0份；汉化和原游戏文件未改，Alt+Tab搁置。
