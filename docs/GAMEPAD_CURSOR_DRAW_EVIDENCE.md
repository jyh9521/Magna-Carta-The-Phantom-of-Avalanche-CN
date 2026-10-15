# 光标绘制入口的只读诊断（2026-10-15）

## 本轮目的

菜单现场验收仍待反馈。输入日志显示 `cursor_hidden=0` 仅代表手柄模块未主动隐藏，无法判断原生对象是否自行隐藏，也不表示真正进入了精灵绘制槽。本轮补足该观测，不宣称修复了尚未复现的全部现场现象。

## Verified：字段与边界

只对当前 `f2388` 光标对象，在 `be380 → 48774` 实际绘制入口记录 `INPUT_CURSOR_DRAW`：

- `decision=skip/original`：手柄模块跳过该次提交，或调用原生绘制函数。
- `x/y`：原生点击全局坐标；`sprite_x/sprite_y`：对象本地浮点位置，不称为最终屏幕像素。
- `sprite_finite`：位置是否为有限数。非有限数仅在日志内规范为零，不改原对象。
- `native_block/native_order`：对象 `+114/+118` 的原值；`native_blocked` 按原生 `38a2f` 的非零条件计算。
- `observation=draw_entry pixels=not_observed`：只证明到达绘制入口与条件，不证明图形驱动已呈现像素。

状态完全相同不重复记录；对象、坐标、隐藏条件变化才产生新记录。每次实际安装最多 64 条状态记录和一次 `INPUT_CURSOR_TRACE_LIMIT`，幂等安装不重置预算。无关精灵不记录；原有菜单事件的 256 条预算独立保留。日志沿用 `runtime/cache/profile.log`，不增加窗口、轮询线程或诊断开关。

## 回归证据

旧生产源加新断言实际失败：`FAIL cursor decision evidence must distinguish actual draw entry from input readiness`。新夹具通过生产输入与绘制钩子，验证跳过/原生入口、相同状态去重、无关精灵忽略、原生隐藏值和本地位置记录、原对象字节不变、64 条上限及幂等安装预算保留。

手柄映射、焦点移动规则、原生可见性字段和绘制调用决定均不改变；不是强制显示指针或新增选中框。未启动商业游戏。实际菜单可见性与实体 Xbox 仍需玩家验证。

## 验收和后续定位

仍使用 `runtime/Play-gamepad.cmd`：菜单方向移动、A 按下再松开，探索中用手柄后再动鼠标。若指针仍不可见，维护时读取最新本地日志：

1. 没有绘制入口记录时，继续调查原生遍历/对象是否进入该槽；不能直接断言手柄隐藏。
2. `decision=original native_blocked=1` 时，继续追原生显示状态来源。
3. `decision=original native_blocked=0` 时，再核对坐标准备、纹理和实际绘制/呈现；仍不等于像素正常。

只更新手柄候选模块；已验收动作/镜头/显示/地图角色、共享数据、默认配置、汉化与 Alt+Tab 均不动。
