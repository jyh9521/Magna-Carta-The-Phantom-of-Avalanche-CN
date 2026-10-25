# Release v1.0：汉化与最终修复版

**发布状态：Release v1.0 已发布。**

2026-10-25 收到完整流程通关、测试无误的验收反馈。正式包合并当前汉化、最终修复与现代 Windows 运行组件，无需串联历史测试补丁。现有专项研究记录保留各阶段证据，不据通关反馈推定所有显示器、硬件或研究功能均已逐项验收。

## 下载与使用

发布文件：`MagnaCarta-zh-CN-v1.0.zip`。

1. 保留匹配版本的独立纯净游戏备份。
2. 将 ZIP 全部内容解压至游戏根目录（`MagnaCarta.exe` 所在层），替换同名文件。
3. 双击 `Configure.exe` 调整增强选项，双击 `Game.exe` 启动。
4. `config/`、`modules/`、`fonts/`、`maps/`、`Start.ps1` 和清单文件为外置依赖，须完整保留。

两份桌面 EXE 各为 7 KiB，不打包 Python 或自包含 .NET 运行时。依赖 Windows 自带 .NET Framework 4.x、Windows PowerShell 5.1 与 WPF。游戏目录须可写，以保存配置与日志。发布 ZIP 不含完整游戏及存档。

默认设置沿用通关包：1080P、无边框、60 帧、键鼠。配置窗口为 790×670 DIP，原版为 1040×850 DIP；150% 缩放离屏画布为 1185×1005 像素。较小工作区继续使用尺寸约束与滚动布局。窗口化尺寸选择、保存、默认恢复、入口检查和启动功能保留。原生游戏与修复模块保持通关包字节，不因入口改造重新构建。

F5 切换随机遇敌，F10 普通连招辅助，F11 暴走连招辅助；地图入口保留 F8/F9。手柄与自由视角研究功能已归档，不列入正式功能。

## 校验与恢复

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Verify-Overlay.ps1 -Action CheckInstalled
powershell -NoProfile -ExecutionPolicy Bypass -File Verify-Overlay.ps1 -Action Rollback -Source "ORIGINAL_GAME"
```

`ORIGINAL_GAME` 为独立纯净备份目录。恢复工具先预检覆盖资源摘要，再恢复原版资源；存档与设置保留。恢复后使用原版游戏入口，现代化入口继续按版本锁拒绝不匹配资源。启动日志位于 `cache/Game.log`、`cache/Configure.log` 和 `cache/profile.log`。

桌面入口支持隐藏验证：`Game.exe --verify-only` 执行既有版本预检，不启动游戏；`Configure.exe --verify-only` 执行 WPF 离屏自检，不显示配置窗口。正常双击时错误提示指向对应日志。

## 可复现构建

```powershell
python tools/build_desktop_entries.py --output build/desktop-entries
python tools/build_release_v1.py --source dist/ACCEPTED_OVERLAY.zip --source-sha256 ACCEPTED_SHA256 --entries build/desktop-entries --output dist/MagnaCarta-zh-CN-v1.0.zip
```

`ACCEPTED_OVERLAY.zip` 为已验收的完整覆盖包；`ACCEPTED_SHA256` 为对应摘要。打包器校验输入 ZIP CRC、所有文件摘要、资源目标摘要、运行依赖及输出回读；只替换配置 XAML、桌面入口、发布说明与相关清单，移除 CMD 玩家入口。814 份已修改游戏资源及既有修复模块保持字节不变。

### 通关输入身份

本轮采用 `MagnaCarta-clean-game-caption-complete-test-20261025.zip`，SHA-256 为 `3d4a6961b4225619b459dfcd568048860c5dd88cca632ad63b60ce87642691a0`。该覆盖包与原始统一增量包作为本地构建输入保留，不加入源码提交。

## 验收记录

- 游戏流程：完整通关且测试无误的反馈，日期 2026-10-25。
- 配置工具：WPF 离屏渲染、选择态动画、设置矩阵与保存/启动路由测试。
- 桌面入口：真实 EXE 编译、小尺寸检查、脚本路由与隐藏验证退出码测试。
- 发布归档：CRC、逐文件 SHA-256、通关资源不变、无 CMD 入口、独立夹具恢复。
- 新桌面入口与紧凑布局未另行启动商业游戏；自动检查与完整通关反馈分别记录。
