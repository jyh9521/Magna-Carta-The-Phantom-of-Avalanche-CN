# 一次性连招辅助：原生判定链修正

## 已验证的根因

旧辅助以宽松接受窗中心发送第二、三次确认。真实 `ValueData/0001.val`
中 `0x23=10` 是间隔，`0x24=6` 是接受窗，`0x25=2` 是精准窗。
因此旧序列 `[0,12,22]` 虽被原生处理器接受三次，仍错过半开精准窗
`[10,12)`、`[20,22)`。这不是按键未发送，而是动作结算结果不符合辅助目标。

| 路径 | 原生记录 tick | 成功数 | 精准标志 | 最终动作 |
| --- | --- | --- | --- | --- |
| 原源码构建 | 0/12/22 | 3 | 0 | 10 |
| 修正源码构建 | 0/10/20 | 3 | 1 | 7 |
| 独立副本恢复原源码并重新构建 | 0/12/22 | 3 | 0 | 10 |

普通攻击动作 3 的真实 ABI 记录、能量等级 3 / 消耗等级 0 是本组输入。
动作 7/10 是该记录在这些条件下的原生选择，不泛化为全部角色的统一动作编号。
精准路径还产生原生 popup kind 3 和声音 ID `0x239`；三次普通成功声音是 `0x237`。
失败按键同样可能增加连击计数，所以只看 `count=3` 不能证明成功。

另外两项生产缺陷也已红绿复现：

- 输入合并发生在辅助之后，持续按住 A/X 会覆盖辅助需要的松键帧。现在物理
  Space 和手柄 A/X 都优先接管并取消辅助，不删除或屏蔽手动确认。
- 同一战斗场景可复用到下一攻击，场景地址不变不等于同一请求。
  现在 actor/action 变化、tick/count 回退、离开 Field 模式、失焦、设备断连或
  设备切换都取消请求；返回后需要新的辅助按下沿。松键采样也更新生命周期快照。

## 原生闭环证据

`combo_assist_chain_fixture` 编译当前生产 `modern_gamepad.cpp` 和
`battle_input.h`，实际安装和撤回键盘/消息 IAT。每个原生键盘轮询把实时 scene
字段（包含 actor/action 身份）送入该持久进程，完整 256 字节键盘快照再送回原生指令。不是 Python 重写宏。

执行链：真实 33ms 任务注册/调度和消息泵 → 原生键盘计数 → GUI 键盘分发 →
`a2f7a` 战斗监听 → `a3681` 连击处理 → `a14b2` 计时 → `a1764` 结算调用 →
`a57a0` 成功/精准判定 → `a58ba` 动作选择 → 原生计时器选择 `a7303` 后续动作。
真实 `a40df/a412d` 资格判断、`8e0ef` ready 查询、`b5b0e/b5967`
配置/动作查询均执行；未用恒真谓词替代。

输入摘要锁定：

- MCAlpha.dll：`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`
- ValueData/0001.val：`1433183acb6763aae110e6b1da7362704c9be30978eef7b6dbe46fd44edff58c`
- Abi/0000.abi：`4ec8bf4949f3a2cc62a15e0a7b0b57ab34fd641e05c60999c131703303fd0a85`
- Att/0000.att：`557dece3f750327e4826064e435951994241d87980a3a8ee5ed82f4b233f7916`

30/60Hz × F10/R3 四条正例得到相同精准结果。A/X 持续按住、失焦和断连的
八条负例只留下原生首击，结算保持非精准基础动作，不被辅助补成成功。
生产输入上下文夹具另验证菜单/结果/阻塞模式、设备变更和同场景回退。
双 IAT 在各次关闭后逐字节恢复，页保护恢复只读。原生闭环在动作选择后停止，
结算后 pending 清除及 actor/action 变更取消由生产类/上下文回归另行覆盖。

## 明确的验证边界

未启动游戏或加载商业 DLL 入口，未注入系统按键。普通攻击及目标已选中的状态、
资源加载、结算前的几何/伤害准备、能量条件是显式夹具输入；没有执行完整战斗内容。
图形/声音对象构造和最终动画是叶边界。原生判定与动作选择是真指令，不把这些
边界写成完整伤害、动画、实体输入或实机画面验收。

## 构建与重放

```powershell
cmake --build build/native --config Release --target workspace_profile combo_assist_chain_fixture combo_assist_context_fixture battle_input_fixture
python tools/replay_combo_assist_chain.py --sample runtime/data/MCAlpha.dll --values runtime/data/ValueData/0001.val --abilities runtime/data/Abi/0000.abi --bridge build/native/Release/combo_assist_chain_fixture.exe --report build/NEW-assist-chain.json --expect-perfect --include-negative
python -m unittest discover -s tests -p 'test_combo*.py' -v
```

Python 依赖沿用项目环境或 `runtime/dependencies`；报告必须使用新路径。
不修改原生判定窗、伤害、技能资源、存档和增强设置。

## 操作及撤回

先选择普通攻击与目标，释放 Space/A/X，再按一次 F10 或已启用手柄的 R3。
辅助不负责自动选择菜单，不将按住辅助键视为连续战斗请求；半途接管若已错过精准窗，
取消而非在宽松窗后段发出降级确认。手柄关闭时 F10 仍可独立工作，不加载 XInput。

详细基线/修改/独立源码回滚、运行目录事务、原始输出和摘要保留在本机
`build/combo-assist-chain/VERIFICATION.txt`。共享目录只更新 12 份自有模块与运行清单，
保留原摘要和撤回文件；游戏资源、设置、存档不进入替换集合。
活动目录保留修正；实体手柄和实际战斗由测试者另行启动原入口验收。

## 增量更新

`dist/MagnaCarta-combo-assist-update-20261023.zip` 只含 12 份自有模块与清单等更新材料，
不含完整商业资源。解压后执行 `Update.cmd -Action Verify -Runtime 已安装共享目录`
核对前置版本，再以 `Install` 应用、`CheckInstalled` 复核；`Rollback` 精确恢复安装前文件。
未知或混合版本拒绝。实际 PowerShell 更新器四态已在只含自有文件的小型副本中验证，
不需要另复制整套游戏。

## 本轮回归记录

完整 Python 回归 846 项通过（1 项按条件跳过），其中连招专用回归 10 项通过；
最新身份字段传递桥另行执行 12 条原生正反例并核对二进制摘要。
生产辅助类 46 项、生产输入上下文 14 项检查通过。
完整构建、文档检查、原生旧源/新源/独立恢复旧源三态和运行模块事务均通过。
这些结果仍不替代实际游戏战斗验收。
