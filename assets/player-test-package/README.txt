《真名法典：冰之魅影》统一测试补丁 2026-10-23

包含当前汉化（正文、图片、字体、系统提示、视频字幕）、免CD启动、
现代Windows隔离启动/焦点保护、正常驱动与DDrawCompat 0.7.1、高清标题、
1080P/2K/4K/自适应、全屏/窗口/无边框、30/60帧动作候选、
区域地图和独立纹理生命周期修复入口。手柄、自由视角已归档，发布版移除。
这些是待实机确认的候选，不把自动校验当作游戏内验收。

本次整合战斗菜单宽屏资源选择修正、图片圆角/拼接标题修复、
高分屏高清字模启用修正及原生Loading候选，不需要叠加历史测试包。
安装默认1080P、无边框、30帧、键鼠，不继承维护端个人设置。
已知待确认：场景切换崩溃仍在调查；60帧慢走时眼球偶发外突仍未修复。
重点复验最近存档到下水道入口及首次战斗，记录所选设置和问题时间。

安装：解压到可写目录，双击 Install.cmd。
输入未修改原版目录（包含 MagnaCarta.exe）；仅支持包内记录的原版哈希。
自动在补丁包的上一级新建 MagnaCarta-PlayerTest，不覆盖原版。
玩家端仅需Windows自带PowerShell 5.1，不需要Python。
也可指定路径：Install.cmd -Source "原版目录" -Target "新测试目录"
不要将目标放入原版目录内；路径应能由系统当前ANSI代码页表示。

安装完成：打开新测试目录，双击 Configure.cmd。
先用默认1080P、无边框、30帧、键鼠测试中文与读档；
再开启60帧检查人物及怪物动作，方便定位差异。
F5切换随机遇敌：默认开启，第一次按关闭，第二次按开启。右下角短暂显示状态（1.8秒）。
关闭时冻结随机遇敌计数，剧情强制战斗和正在进行的战斗不变；重启恢复开启。
F10普通连招辅助、F11暴走连招辅助保持不变。
Play.cmd使用保存设置，默认整合总部楼梯退回高度修正与启动GUI父节点越界守卫；Configure启动同样生效。
GUI守卫仅针对启动光标构造时通用根节点的空间字段越界，已过生产代码离线回放与回滚验证。
实机由玩家自行测试；本项不代表场景切换崩溃已修复，换区问题仍在调查。
沿正常流程游玩即可，到楼梯再观察，不需要换入口或提前准备存档。
此修正已过自动验证，实际碰撞/对话/软锁消失仍待正常游玩确认。
Play-baseline.cmd保留原模块对照，8份旧模块、上次正常楼梯模块及原始安装保留。
维护可用powershell -NoProfile -ExecutionPolicy Bypass -File Start.ps1 -WithoutGuiParentGuard
临时只关闭GUI守卫，保留楼梯修正、保存设置及存档；不需要更换玩家入口。
维护可用powershell -NoProfile -ExecutionPolicy Bypass -File Start.ps1 -WithoutFieldReturnHeight
临时关闭楼梯修正并沿用保存设置，不改配置或存档。
Play-texture.cmd单独测试纹理生命周期修复；
Play-maps.cmd测试区域地图；
Play-motion.cmd提供动作对照。
各固定配方有自己的预设，不一定使用Configure保存的显示设置。
所有入口共享data内同一套游戏和存档；关闭前一个游戏再切入口。
不要直接启动data/MagnaCarta.exe，那会绕过现代化运行模块。
地图F8大图、F9小图；地图打开时游戏继续运行。

建议检查：未挂载光盘时进入标题、新游戏/读档、中文菜单与对白、
场景切换、音乐语音视频、Alt+Tab、鼠标坐标、退出恢复桌面；
60帧检查人物及怪物移动/转向/战斗节奏，检查F5遇敌提示和开关；
出现问题保留cache目录日志、截图及所选配置。
原版旧存档名字不转换；开头SOFTMAX Logo与开发名单保持原样。

只检查原版：Install.cmd -Action Verify -Source "原版目录"
检查测试副本：Install.cmd -Action CheckInstalled -Target "测试目录"
恢复游戏资源：Install.cmd -Action Rollback -Source "原版目录" -Target "测试目录"
回滚预检目标摘要后恢复原版资源（含EXE/驱动），不删除存档与设置。
回滚后现代化入口会按版本锁拒绝启动；原安装始终可作原版对照。
测试包不含完整商业游戏；原版资源须保留用于安装与回滚。

含scaled_font清单的测试包沿用Play.cmd启用C高清文字候选，低分辨率保留原字模。
单项对照：powershell -NoProfile -ExecutionPolicy Bypass -File Start.ps1 -WithoutScaledFont
字体候选仍需游戏画面验收；排查时保留cache/profile.log中的SCALED_FONT记录。
