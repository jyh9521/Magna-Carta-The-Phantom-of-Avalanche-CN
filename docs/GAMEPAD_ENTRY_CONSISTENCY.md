# 手柄入口的输入修订一致性

## Verified（2026-10-15）

共享包中 `gamepad`、`motion-gamepad` 使用当前 `input-diagnostics`，但
`camera-gamepad`、`maps-gamepad` 原来仍选择历史 `camera`、`maps` DLL。
这些角色是包含输入实现的完整 shim，不会因为同目录的输入 DLL 更新而自动组合。
因此旧角色不包含后续的方向独占、菜单光标绘制边界修正。

打包器现在在显式提供 `input-diagnostics` 时，将四个手柄入口统一到该模块。
当前 shim 本身具有由环境变量启用的摄像机和地图观察器；配方继续保留
`camera`/`maps` 开关和显示/动作设置。未提供输入候选的旧打包调用保持原角色。
无手柄入口仍选择原来的已验收模块；本次没有替换任何 DLL、图像或游戏数据。

新回归断言在原打包器失败于 `camera-gamepad`，修改后五项打包测试通过。
对另一份源文件执行摘要守卫回滚后，同一断言恢复失败；正式源保持修改。
四个实际入口的 `Start.ps1 -Recipe NAME -VerifyOnly` 均通过，只执行原生预检，
未启动商业游戏。预检会写入 cache，并临时选择后恢复显示 INI。

## Unverified

入口一致性不是当前不可见光标根因的现场证明。已有最后游玩日志早于当前绘制槽
修正，不能据此判断当前指针是否真正显示。不要继续凭离线输入成功宣称可见性通过。

## 手动验收

先用 `runtime/Play-gamepad.cmd`：在主菜单按十字键逐项移动，观察橙色原生
指针位置，按下再松开 A，确认打开的就是指向项。进入状态菜单，确认右侧选项与
中央绿色箭头不会同时响应；再用右摇杆定位中央控件，测试 A。真实鼠标移动应接管。

然后按需测试 `Play-motion-gamepad.cmd`、`Play-camera-gamepad.cmd`、
`Play-maps-gamepad.cmd`。若仍不可见，保留本次会话 `runtime/cache/profile.log`，
结合 `INPUT_CURSOR_DRAW` 与 `INPUT_UI_FOCUS` 定位，而不是强制改过场隐藏字段。

受控记录：`runtime/maintenance/gamepad-entry-consistency/VERIFICATION.txt`。
