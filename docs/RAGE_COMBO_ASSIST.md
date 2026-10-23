# F11 暴走连招辅助

## 操作

- 普通节奏继续使用 **F10 / R3**；暴走节奏使用 **F11**。
- 选择攻击和目标，进入可确认攻击的状态后，按一次对应辅助键。辅助包含启动节奏的
  第一次原生 Space，不需要额外连续按 Space。已经手动首击时，F11 可在剩余时间足够时接管。
- 每次按下只处理当前攻击，不自动选择菜单或循环下一场战斗。
- 手动 Space/A/X、失焦、菜单/结果界面、场景/角色/动作切换、计时回退会取消请求。
  已错过最佳完成时间的接管不补发。F10 和 F11 同按不发确认。
- 键盘 F11 在手柄关闭时也工作，不要求加载或连接 XInput。

本地共享运行目录已更新；本次没有启动游戏。以下为离线原生闭环，不替代暴走画面实测。
先前继续游戏崩点的 volatile 栈槽/后置检查修正保持不变。

## 已验证的原生区别

普通模式使用 scene+`1dcc/1de0/1ddc` 的启动标志、计时和次数，读取 ValueData
键 `23/24/25` 的间隔/接受窗/精准窗；默认精准记录为 **0/10/20**。

暴走是独立的 Apocalypse 分支，不是将普通间隔乘一个速度系数：

| 字段 | 原生含义 |
| --- | --- |
| scene+1de8 | 暴走节奏已启动 |
| scene+1dec | 原生按键时间记录数组指针 |
| scene+1df0 | 原生已确认次数 |
| scene+1df4 | 暴走开始后的逻辑 tick |
| ValueData 39 | 完成时限，原版10 tick |
| ValueData 3a | 所需确认次数，原版3次 |
| ValueData 3b | 最佳等级的时间余量，原版4 tick |

`A412D` 资格判断执行真实技能查询和能量 getter：技能记录+54 存在 ApocalypseAbility，
且能量等于键38（原版3）时进入暴走。`A3681` 记录确认，`A14B2` 递增暴走时钟；
`A519D–A5296` 检查整个数组。所有确认在10 tick内才完整成功，且全部时间必须
**小于等于 10−4=6** 才得到最佳 grade3。落入较慢 grade2 还可能进入原生随机惩罚路径。
辅助不改这些窗口、资源、能量或结算分支。

### 第二个实际问题：有符号键盘计数器

最初候选0/2/4确实发送了 Space，但原生只收到首击：计数器在松开后经过
`1 → -1 → 0`，只留一次松键采样就重新按下，会使 `-1 → 0`，不会产生需要的
`counter==1` 原生 GUI 按下事件。仅检查辅助按键快照会把该候选误判为成功。

最终 F11 节奏为 **0/3/6**，两次按下之间保留两个原生松键采样；第三次恰在最佳
等级允许的含端点6 tick内。辅助不强写原生键盘计数器，仍由正常输入管线产生三个事件。
剩余次数/最佳时限来自原生配置；中途接管先检查余下确认能否在最佳时限内完成。
普通 F10 的精准窗算法不变。

## 原生闭环与边界

沿用编译后的 `combo_assist_chain_fixture`，输入协议新增 F11 和暴走实时字段。
生产 `modern_gamepad.cpp` / `battle_input.h` 真实安装/撤回键盘及消息 IAT，完整
256字节键盘快照回到原生调度、计数器、GUI listener、战斗 handler、timer、评分、技能选择。
没有以 Python 重写评分，也没有以恒真桩替换技能/能量资格判断。

同一锁定 ABI 中8份 ApocalypseAbility 记录分别验证30/60Hz：
`13→199, 14→200, 22→213, 30→205, 38→201, 46→202, 54→204, 62→203`。
16个正例均记录0/3/6，grade3，选择各自原生后续动作；每次原生计时器仅转移一次。
按住F11、手动首击后早期接管、失焦、手动接管、过晚接管、模式不匹配、双键冲突另有回归。
原 F10/R3 的0/10/20及精准结算仍通过。双 IAT 与页保护在关闭夹具后精确恢复。

场景/目标已选中、技能ID及能量3是显式起始条件；资源加载映射、评分前几何/伤害准备、
评分结果视觉构造及选动作后的动画是叶边界。失败后能量/UI副作用不在本回放执行范围。
不宣称已跑完整战斗、角色动画或实际游戏画面。

输入 SHA256 沿用 [原生普通连招修正](COMBO_ASSIST_CHAIN_REPAIR.md) 中
MCAlpha.dll、ValueData/0001.val、Abi/0000.abi 和 Att/0000.att 的完整来源锁。
静态 REA 证据：`ev_517f78079c5e1e4150e9afe0ee4dbd163e8b221d4a8610cc82a1c7d64e64ea75`、
`ev_1ea0a854f141d0824417f2b6fe809b965df59aef81b73b4e37f26012e17117ef`。
静态证据、旧F10仅首击、旧F11无响应、0/2/4失败候选、修改/独立源码撤回和运行模块事务
保存在本地忽略目录 `build/rage-combo/`，不提交商业 DLL。

```powershell
cmake --build build/native --config Release --target workspace_profile combo_assist_chain_fixture battle_input_fixture combo_assist_context_fixture
python tools/replay_rage_combo_assist.py --data runtime/data --bridge build/native/Release/combo_assist_chain_fixture.exe --report build/NEW-rage.json --expect-success
python -m unittest discover -s tests -p 'test_rage_combo_assist.py' -v
```

`tools/update_runtime_modules.py` 只整批更新12份自有模块和运行清单，保留旧摘要与备份；
独立自有文件夹具验证精确撤回。共享目录保留新版；存档、设置和游戏数据不在变更集合。

## 玩家增量包

`dist/MagnaCarta-rage-F11-update-20261023.zip` 适用于**已安装继续游戏修复包**的用户，
不是旧错误包的直接替代品。关闭游戏后，将全部内容解压至含 `Play.cmd`、`runtime.json`
的共享目录，双击 `Update-F11.cmd`，看到 `REPAIR PASS` 后再手动启动 `Play.cmd`。
仅解压不完成模块安装；不要求先撤回继续游戏修复。

构建工具 `tools/build_rage_combo_update.py` 锁定上一份实际交付的继续游戏修复 ZIP、
新模块的完整 SHA256，仅替换该玩家清单中的12份自有模块及相应摘要，不用本机额外
诊断入口的整份清单覆盖玩家元数据。脚本目录 `RageCombo-F11-20261023`、撤回目录
`.rage-combo-f11-20261023` 与前两次更新独立，保留 `.text-runtime-update` 和
`.continue-game-fix-20261023`。

交付 ZIP 已用真实 PowerShell/批处理验证：前版 CheckInstalled、安装、重复运行、
精确撤回、前版再次 CheckInstalled、混合文件拒绝且零写入、重新安装。
独立夹具保留两个既有更新标记/备份哨兵及存档、设置哨兵；未复制完整游戏。
完整回归869项（1项按条件跳过）通过，发布流程另有独立回归。
