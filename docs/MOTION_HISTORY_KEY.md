# 过渡历史：完整原生采样请求身份

## Verified：源字段与旧代码失败

支持版本MCAlpha.dll的3b0c0使用：动作+4总帧数、+8每采样步长、
+18资源序列、记录+4骨骼资源，以及对象+f4过渡计数和+f0输入历史。
原生帧号先模总帧数，再按步长选择资源。静态证据及支持版本摘要参见
`MOTION_HISTORY_CAPACITY.md`。

旧`prepareHistory()`只比较动作地址、缓冲地址、数量和逻辑阶段；
同一阶段内改帧或改资源时，仍可能把旧请求的历史写入新请求。
生产入口合成回归在旧代码上失败：
`FAIL same-tick changed native frame cannot replay another sample history input`。

另以当前夹具配旧生产代码运行`--render-history-only`，经实际renderHook进入
生产prepareHistory，再进入源形状的非商业过渡绘制桩。两次原生采样依次
从0生成10，再从10生成20；旧缓存把第二次输入恢复成0，生成15，输出：
`FAIL real render hook frame change uses current native transition history not prior sample input`。
此回放证明请求身份混用，但不证明玩家实际调用顺序就是该合成场景。

## 修正

历史身份增加归一化帧号、总长度、步长、当前骨骼资源地址及过渡计数。
任何一项变化则捕获当前原生历史；全部相同才回放。归一化遵循原生取模：
长度8的帧1与帧9属于同一采样请求，仍复用历史，避免无意义重复累计。
原版本守卫、资源可读性、512骨骼和128历史容量边界保留。
不改商业动画资源、不改原采样器/过渡函数、不推进原逻辑或事件。

229项完整夹具、222项渲染路径模式通过。检查包含改帧、同帧重复、同数量换资源、
同地址换长度、换步长、改变过渡计数以及等价模长请求。
独立源回滚恢复219项原行为；主动模块保持修正。

## Unverified / 玩家验收

未证明玩家抽搐由上述同阶段请求变化引起，也未进行商业游戏启动。
完整60FPS动作仍待真实角色、剧情、战斗与换区验收。

入口`runtime/Play-motion.cmd`，对照`runtime/Play-baseline.cmd`。
重点测试行走→停止→转身、待机循环、对话进入/退出、换区后的首个动作，
观察切换瞬间是否抽动或出现旧姿态拖影。退出后提供`runtime/cache/profile.log`
并注明具体动作。源回滚、摘要及逐项命令在
`runtime/maintenance/motion-history-key/VERIFICATION.txt`。

本轮游戏启动0次、完整游戏复制0份，默认增强配置和汉化数据不变。
