《真名法典：冰之魅影》统一测试补丁 2026-10-17

包含当前汉化（正文、图片、字体、系统提示、视频字幕）、免CD启动、
现代Windows隔离启动/焦点保护、正常驱动与DDrawCompat 0.7.1、高清标题、
1080P/2K/4K/自适应、全屏/窗口/无边框、30/60帧动作候选、
XInput手柄、自由视角、区域地图和独立纹理生命周期修复入口。
这些是待实机确认的候选，不把自动校验当作游戏内验收。

安装：解压到可写目录，双击 Install.cmd。
输入未修改原版目录（包含 MagnaCarta.exe）；仅支持包内记录的原版哈希。
自动在补丁包的上一级新建 MagnaCarta-PlayerTest，不覆盖原版。
玩家端仅需Windows自带PowerShell 5.1，不需要Python。
也可指定路径：Install.cmd -Source "原版目录" -Target "新测试目录"
不要将目标放入原版目录内；路径应能由系统当前ANSI代码页表示。

安装完成：打开新测试目录，双击 Configure.cmd。
先用默认1080P、无边框、30帧、键鼠、自由视角关闭测试中文与读档；
再逐项开启60帧、手柄和自由视角，方便定位差异。
Play.cmd使用保存设置。Play-texture.cmd单独测试纹理生命周期修复；
Play-maps.cmd/Play-maps-gamepad.cmd测试区域地图；
Play-motion.cmd/Play-gamepad.cmd/Play-motion-gamepad.cmd提供独立对照。
各固定配方有自己的预设，不一定使用Configure保存的显示设置。
所有入口共享data内同一套游戏和存档；关闭前一个游戏再切入口。
不要直接启动data/MagnaCarta.exe，那会绕过现代化运行模块。
自由视角：探索场景F6开关、F7关闭复位；NumLock开启，按住Ctrl+Alt，
小键盘4/6环绕、8/2俯仰、加/减调距离。地图F8大图、F9小图；
手柄地图入口对应View/Back和R3。地图打开时游戏继续运行。

建议检查：未挂载光盘时进入标题、新游戏/读档、中文菜单与对白、
场景切换、音乐语音视频、Alt+Tab、鼠标坐标、退出恢复桌面；
60帧检查移动/转向/战斗节奏；手柄检查跳过、菜单、确认取消；
出现问题保留cache目录日志、截图及所选配置。
原版旧存档名字不转换；开头SOFTMAX Logo与开发名单保持原样。

只检查原版：Install.cmd -Action Verify -Source "原版目录"
检查测试副本：Install.cmd -Action CheckInstalled -Target "测试目录"
恢复游戏资源：Install.cmd -Action Rollback -Source "原版目录" -Target "测试目录"
回滚预检目标摘要后恢复原版资源（含EXE/驱动），不删除存档与设置。
回滚后现代化入口会按版本锁拒绝启动；原安装始终可作原版对照。
测试包不含完整商业游戏；原版资源须保留用于安装与回滚。
