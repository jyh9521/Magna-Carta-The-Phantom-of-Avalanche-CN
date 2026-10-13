# 手柄开场跳过与普通菜单焦点：源路径修正

## Verified：支持的源版本

MCAlpha.dll SHA256 `5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。
REA 静态证据保存在本地维护目录 `runtime/maintenance/input-skip`，没有启动游戏。

## Verified：开场跳过

原标题更新 `0x520b71a6` 在 `0x520b71cc` 调用输入更新，返回 `0x520b71d1`；
栈帧 `ebp-38` 保存标题场景 this，场景构造 `0x520b662b` 写入 vtable `0x520c22f0`。
原更新随后检查新按下的 Esc（0x1b），设置场景+64。
原 `0x520b7571` 在 logo 状态1、opening状态3读取+64并结束相应播放。
旧 Confirm 注入 Space，与这个原路径不符。
现在 A 在1/3状态注入 Esc；0/2准备状态不注入 Confirm；4/8可交互状态保留点击；
过渡状态不发 Confirm。没有直接写跳过字段或调用播放器结束函数。

夹具新建标题→输入→IAT bridge的两层栈，保留真实返回位置与 this 偏移，
仅执行自建桩。旧代码失败 `logo skip uses source Esc not Space through IAT bridge`；
修改后 WORLD_GAMEPAD_FIXTURE 27项通过，此前23项仍包含在内。

## Verified：导航分类错误

普通 GUI vtable `0x520bec88`、标题GUI `0x520c2340` 的 +c8/+cc/+d0/+d4
实际分别是 `0x52055f0a/55f23/55f3c/55f55`。
这些基类方法向 listener转发通用方向事件3/7/11/15。
旧 defaultArrows却只认 `55b97/55b8c/55b81/55ba2` 的空方法，
将真正的普通GUI误判为特殊方向控件，未收集菜单焦点。
旧夹具同样写了错误函数表，因此此前16项通过没有覆盖真实普通GUI。

现在识别真实基类事件转发函数组与已知空函数组；其他覆盖仍保留原生方向行为。
方向事件仍由原派发器处理，补丁只移动虚拟焦点。
测试改为实际基类函数表，旧代码失败 `first downward focus and original dispatcher return`；
修改版16项通过，包括重复、环绕、禁用控件、模态范围、特殊覆盖保留与精确回滚。
独立源码回滚恢复旧23/16项通过，不覆盖当前候选。

## 玩家验收与当前限制

入口 `runtime/Play-gamepad.cmd`，模块 `runtime/modules/input-diagnostics.dll`，
共享数据 `runtime/data`。增强配置中的手柄及动作+手柄组合也选择该新候选，
但没有替玩家打开选项或更改已验收默认设置。

1. 手柄先松开所有按钮/摇杆，再按 A，分别检查厂商logo和开场动画能否跳过。
2. 主菜单使用方向键/左摇杆上下移动，检查选中项是否变化；A确认、B返回。
3. 进入游戏，Start打开菜单；检查方向键、A、B对状态/保存/读取列表是否生效。
4. 检查左摇杆移动是否维持正常，鼠标和键盘仍能接管。

夹具及VerifyOnly不证明实体菜单全部可用，需玩家反馈。
探索中A仍使用原Space、X仍使用原左键，尚未解决用户报告的语义不合理映射；
不能把开场与焦点分类修复称为完整Xbox验收通过。
标题默认亮度/选中提示、视角移动、地图实用性仍待推进；Alt+Tab继续搁置。

没有改动中文翻译、字体、已验收4K背景；没有新增完整游戏副本。
