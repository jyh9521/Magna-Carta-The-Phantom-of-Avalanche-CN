# 60Hz战斗短按边沿修正

## 支持输入与验证方法

只读当前MCAlpha.dll，SHA-256
`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
`ValueData/0001.val`的SHA-256为
`1433183acb6763aae110e6b1da7362704c9be30978eef7b6dbe46fd44edff58c`；
实际配置`0x23=10`、`0x24=6`，不修改原生判定窗。
源指令在Unicorn中执行，Win32键盘队列、图形和声音设备边界采用显式夹具。
本轮不启动游戏，不载入商业DLL入口，不产生系统键盘事件。

## 已验证的机制

战斗主循环`8ae8a`通过`8aebc → cdc4`执行33ms固定任务，
`8aec4`绘制后在`8afda → bdbe`取出并分发消息。
`bdbe`循环调用`PeekMessageA`、`GetMessageA`、`TranslateMessage`和`DispatchMessageA`，
直到消息队列清空；原生键盘采样`2f95`仅发生在逻辑更新中。
60Hz解锁额外绘制帧，也额外清空消息队列，却没有增加键盘逻辑采样。

[Microsoft的GetKeyboardState契约](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getkeyboardstate)
明确区分消息移除后的线程状态与异步硬件状态。
因此，真实按下和松开消息均可在两个逻辑采样之间被取走；下一次采样只看到松开，
原生Space计数从未达到1，GUI不产生`0x13`按下事件，连击处理`a3681`没有收到该次操作。
这与判定窗缩半、动画或成功提示数字双速是不同问题。

例如同一输入在20ms按下、40ms松开：30Hz在33ms消息泵取出按下，
66ms逻辑采样仍看到按下；60Hz在50ms的额外帧先取出松开，66ms逻辑采样看到松开。
该例的按下时刻和持续时间没有随帧率改变。

## 同墙钟输入差分

三次短按保持按下20／400／760ms、松开40／420／780ms：

| 路径 | 原生处理时刻(ms) | 原生记录tick | 成功声音次数 |
| --- | --- | --- | --- |
| 30Hz原版 | 66／433／800 | 0／11／22 | 3 |
| 60Hz原版 | 433 | 0／未记录／未记录 | 1 |
| 60Hz修正 | 66／433／800 | 0／11／22 | 3 |

整链执行原生消息泵、任务注册／调度、键盘计数、GUI、战斗监听器和连击处理。
33种短按相位扫描中，原版30／60Hz各收到20次，但捕获相位不同；
其中13种是30Hz收到而60Hz丢失。修正后33种均收到。
这证明特定固定节奏会发生60Hz独有漏按，不证明随机均匀输入的60Hz总体丢失率更高。
实际反馈是否还包含其它手感因素仍需人工比较，不将该缺口宣称为所有差异的唯一原因。

过早输入对照仍会失败：边沿缓存不会把窗口外按键延迟到成功窗口。

## 修正边界

原生`GetMessageA`返回桥仅记录原生消息泵取出的真实Space按下沿，消息原样透传。
下一次原生战斗键盘采样消费一次；长按重复消息不新增边沿。
该缓存不等待成功窗口，不自动连击，不修改伤害、动作速度、配置或存档。
场景退出、失焦、键盘失败或有界时限到达时清空缓存。

作用域从真实战斗键盘调用栈及构造函数写入的虚表`c1960`建立；
战斗输入和辅助路由共用同一正确识别。首次普通攻击需要在`active=1`、
`timed=0`时建立限时连击，所以缓存不要求已经进入timed状态。
非攻击菜单和非战斗场景不接收延迟确认。

上一轮关闭当前攻击者插值的兼容候选已移除；姿态、world与相机继续采用正常平滑。
`battle_rhythm_fixture`现验证保留插值，不再把降采样作为连击修正证据。

## 反证与纠正

真实构造写入`c1960`，旧值`c195c`是前一虚表的末槽；
只在实现和夹具重复旧常量会出现假阳性。
通用节点`+4/+8`分别是自身／递归更新，`+c/+10`分别是自身／递归绘制。
Combo数字`ab371`和通用计时`4c7c6`均属于更新，额外绘制不把这些计时翻倍。
原生成功／失败声音由`a3681`结果触发，不是额外绘制发出的预测节拍。

## 复现与撤回

```powershell
cmake --build build/native --config Release --parallel 4
cmake -S src/runtime -B build/battle-edge-bridge -A x64 -DBATTLE_EDGE_BRIDGE_ONLY=ON
cmake --build build/battle-edge-bridge --config Release
python tools/replay_battle_message_queue.py --sample runtime/data/MCAlpha.dll --values runtime/data/ValueData/0001.val --latch-bridge build/battle-edge-bridge/Release/battle_edge_bridge.dll --report build/NEW-combo-queue.json
```

桥接DLL只含自有边沿类，架构须匹配运行回放的Python；不链接或载入商业DLL。
未知输入摘要、变动指令及已有输出路径会拒绝。

详细命令、原始输出、构建摘要、隔离撤回和活动运行目录状态保留在
本机`build/combo-root-cause/VERIFICATION.txt`。
运行目录只替换12份自有模块和文件清单，商业输入、13份存档和增强设置保留。
源代码、测试和文档进入版本控制，完整商业文件和本机分析快照不提交。

离线验证证明消息丢沿机制及修正路径；实体键盘、手柄和画面中的操作感仍由测试者人工验收。

## 玩家小更新

共享运行目录已保留本轮修正，默认入口和增强开关不变。
累计小更新`dist/MagnaCarta-feedback-combo-update-20261023.zip`面向2026-10-22统一包，
包含上一轮反馈修正和本轮边沿修正；增量小更新
`dist/MagnaCarta-combo-edge-update-20261023.zip`面向上一轮反馈更新后的同一清单。
两包各只替换12份自有DLL和运行清单，未知／混合版本先拒绝，不包含完整商业资源。

解压对应小更新后执行`Update.cmd -Action Verify -Runtime 已安装共享目录`核对来源，
`-Action Install`应用，`-Action CheckInstalled`核对结果，`-Action Rollback`恢复安装前版本。
两种来源分别经过实际PowerShell更新器的四态隔离验证，存档和设置哨兵保持原字节。
运行目录直接撤回本轮自有模块的记录为`build/combo-root-cause/deployment-final`；
`ROLLBACK.sh`默认仅运行隔离撤回验证，`--active`才按记录撤回活动目录。

旧源、修正源、恢复旧源均实际编译同一输入回归夹具，结果为失败／通过／失败。
恢复旧源重新出现漏按，活动共享目录仍保留修正模块。
