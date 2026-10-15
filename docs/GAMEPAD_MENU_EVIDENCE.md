# 菜单选择与确认输入的事件证据（2026-10-15）

## 状态与目的
上一版菜单定位及Xbox手感尚待玩家反馈；日志时间仍为2026-10-14 22:04，不能据此宣布通过。
本轮不调整焦点算法、方向归属、摇杆阈值、菜单指针政策、A/B/Start/X映射。
补充自动记录，避免下一次仍只凭截图和每秒一次的INPUT_FRAME猜测选择位置。

## 事件与含义
输入候选已经通过原trace回调写runtime/cache/profile.log，不新增窗口、游戏副本或手动日志开关。
- INPUT_UI_FOCUS：每次成功的虚拟选项移动记录serial、root_class/root_id、target_class/target_id、起止坐标、命中矩形。
  类地址均为MCAlpha内部RVA，不是运行时进程地址。字段是经过readable/已知类检查的只读观察。
  observation=virtual_selection明确只代表补丁选中了该目标，不代表原生GUI已渲染高亮。
- INPUT_UI_CLICK：合并输入的左/右按钮计数为1或-1时，记录根类/ID、坐标、两个计数。
  phase=before_mouse且source=merged_input：可能来自手柄或真实鼠标，不能直接叫作A键。
  记录位置在键盘GUI派发作用域内、后续原鼠标派发前；不证明实际鼠标listener、原生转场、存档或脚本已执行。
- 每次真实安装最多256条上述菜单事件，之后仅发一次INPUT_UI_TRACE_LIMIT。
  原INPUT_FRAME/READY日志独立保留；满额后明确停止事件记录，不循环写大日志。
  同一已安装模块的幂等安装不会重置上限；新的正常游戏进程获得新的预算。

## 验证
新断言在旧生产源码失败：
FAIL selected target identity and native coordinates must be observable, not only first-use readiness (exit1)。
这是旧诊断覆盖不足，不是宣称复现了玩家全部实际菜单问题。
GUI48项：已知目标ID和RVA、精确坐标、点击阶段标签、原计数不变，以及连续300次选择后仍只记录256条/一次限额提示。
原方向独占、物理键盘、重复/释放及回滚检查保留。综合世界120项保持通过，Python完整461项通过。
独立两文件源码回滚重编译恢复44项原GUI行为；实际菜单/手柄画面仍未验收。

## 使用
入口仍是runtime/Play-gamepad.cmd。玩家正常选择、A确认和B返回即可自动留下上述事件。
优先观察定位指针是否可见、A是否命中所指选项，以及状态页绿色箭头/右侧菜单是否独立。
如果还有异常，只需描述出错的选项和操作；维护时直接读取本地profile.log，不要求额外启动诊断程序。
只更新input-diagnostics.dll，四个已验收角色模块、游戏数据、汉化、Alt+Tab及默认设置不变。商业游戏启动0次。
