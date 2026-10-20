# 战斗菜单宽度断言（2026-10-20）

## 玩家报告与边界

刚进入下水道即弹窗，尚未保存该处进度。截图为`MCBtlMenu.cpp`、Line169、Expression0。
另报告切尔西及偶尔主角慢走时眼球瞬间外突，分别追踪。本地保留当次截图、profile、
launcher日志；launcher的exit=0不代表没有游戏内断言。没有自动启动游戏或新建完整副本。

## Verified：原始分支与修正

MCAlpha完整SHA256：`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
初始化RVA ae6e8在aefcc/af068比较f1b48与640/800，分别选择FDI100/206；
其他宽度在af11c触发Line169、Expression0。两份本地FDI均存在。REA证据：
`ev_f254f2fd5d0e505be3a3ebde7d00268c8ec341fde30c689a7baaf08843eb4135`。

宽屏模块把同一字段扩为853/1067。新增回放执行原比较、跳转、断言参数压栈，
两种扩展宽度均触发截图中的同一断言；640/800到达各自分配边界。分配、构造、
解码、完整换区及真实绘制不在回放内。High-confidence deduction：宽屏字段误用
解释本次截图；完整下水道路线仍待玩家复验。

修正只将两处CMP地址操作数指向模块保存的原生宽度；常量、条件跳转、资源ID、
未知宽度断言不改。画布仍为853/1067，不临时改全局值，不改存档或资源。
两处原始10字节与既有站点一起预检、事务安装、失败补偿及精确撤销。

自有C++夹具直接执行生产改写后的CMP。旧代码得到
`BATTLE_WIDTH FAIL physical=640 canvas=853 compare=640 selected=0 expected=1`，exit1。
修正后640/800选择正确，1024不伪装成支持模式；13站点漂移拒绝、写失败补偿、
原字节回滚和鼠标往返通过。独立最小源码副本恢复后新回归重新失败，活动源码保留修正。

## 眼球仍未修复：延长晚期观察

大量world_skipped=0不代表所有角色及所有时刻通过。原Diagnostics在120窗口后关闭；
约29分钟会话的后段缺少动作统计。现在前120窗口至少1秒汇总，此后至少10秒汇总，
窗口计数饱和不溢出。只记录既有标量，不记录商业姿态数组或对象地址。第121窗口
及计数保留有回归，骨骼/world/相机插值不改。这是观察能力修正，不是眼球视觉修复。

## 离线重跑与撤回

```powershell
$env:PYTHONPATH='runtime/dependencies;tools;tests'
python tools/replay_battle_menu_width.py --sample runtime/data/MCAlpha.dll --report build/NEW-battle-width.json
cmake --build build/native --config Release --target wide_ui_fixture render_timeline_fixture workspace_profile
build/native/Release/wide_ui_fixture.exe --battle-width-check
build/native/Release/wide_ui_fixture.exe
build/native/Release/render_timeline_fixture.exe
python -m unittest test_battle_menu_width test_rigid_motion_native test_motion_queued_world test_configuration_verify_transaction
```

本地`build/battle-width-evidence/`保留基线摘要、修改副本、diff、验证记录、可执行
隔离源码回滚脚本。共享目录仅更新自有DLL与清单，存档、设置、商业资源摘要保持。
模块撤回命令（游戏退出后）：

```powershell
python tools/deploy_text_runtime.py rollback --runtime runtime --record build/battle-width-evidence/runtime-deployment
```

人工复验由玩家手动运行原`runtime/Play.cmd`，预计5—10分钟，正常菜单退出。
读取最近已有存档，重走下水道入口及首次战斗，不要求故障点存档。观察切尔西及
主角慢走，外突时记录时间并保留短视频；新弹窗保留截图，下一次启动前保存cache，
不覆盖唯一进度。自动验证不包含这些画面验收。
