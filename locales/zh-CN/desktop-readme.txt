《真名法典：冰之魅影》简体中文汉化＋修复版 v1.0

本 ZIP 是覆盖补丁，不含完整游戏。解压到匹配的游戏目录（MagnaCarta.exe 所在层）。
先保留独立原版备份；更新现有汉化目录前保留个人存档。游戏资源与既有 v1.0 来源锁保持一致。
双击 Configure.exe 配置，双击 Game.exe 启动。使用 Windows .NET Framework 4.x / WPF；
配置、启动、校验逻辑已编译，图标、界面、配置模板和校验清单内嵌，无需 PowerShell 或 Python。
保留 modules、fonts、maps 等运行资产目录。modules/DesktopRuntime.dll 是编译后的公共程序集。

默认 1080P、无边框、60 帧。玩家设置位于：
%LOCALAPPDATA%\MagnaCarta\Installations\安装标识\enhancements.json
同一安装路径继续使用已有用户设置；首次读取旧 config/enhancements.json 时迁移而不删除原文件。
日志在同一位置的 cache 目录。存档不移动、不重置。
F5 随机遇敌，F10 普通连招辅助，F11 暴走辅助；F9 小地图 → 全屏半透明地图 → 关闭。
本次小地图呈现和桌面封装为离线验证结果，不冒充新增通关或真实帧率验收。

检查覆盖文件：Game.exe --check-installed
入口预检（不启动游戏）：Game.exe --verify-only
配置界面离线自检（不显示窗口）：Configure.exe --self-test
检查原版备份：Game.exe --check-baseline "原版备份目录"
恢复原版资源：Game.exe --rollback "原版备份目录"
回滚保留存档、用户设置、显示 INI、说明和桌面检查程序；恢复后从原版入口启动。
对照关闭原有碰撞/声音候选：Game.exe --without-test-candidates

ZIP 不含 config 文件夹、PS1/PSM1 脚本、外置 runtime.json 或 Overlay-Manifest.json。
覆盖旧版不会自动删除旧脚本。可在成功校验并保存用户设置后移走旧版 config、Start.ps1、
Verify-Overlay.ps1、runtime.json、Overlay-Manifest.json；新程序不执行这些旧文件。
完整源码与构建流程继续保留在项目仓库。

2026-10-26 完整覆盖修订：这是同一个完整汉化＋修复补丁，不是单项补文件包。
已纳入 Asura.dll、匹配引擎基础库、驱动、音频组件，以及清单所需的原版图像和帧数据。
另含来源锁定的旧安装兼容资源：130 项缺失资源和 167 项不同版本资源，一次覆盖恢复匹配基线。
所有固定运行依赖均包含在 ZIP 中并绑定摘要，不再要求另补基础库或叠加历史测试包。
保留原游戏与存档备份，退出游戏和配置工具，将本 ZIP 全部内容一次性解压到游戏根目录，
同名文件全部覆盖，保留 modules、fonts、maps、redist 等目录层级；系统询问管理员确认时选择继续。
覆盖不会删除存档、重置用户设置或自动启动游戏。先点“检查入口”，通过后再手动启动。
Asura.dll 的匹配版本为 516096 字节，SHA-256：
f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557。
