# 编译式桌面入口与 v1.0 封装修订

## 状态与边界

2026-10-25：配置、启动路由和覆盖包校验逻辑从外置 PowerShell 迁入 C#，保留原生运行模块。源码仍在仓库；分发包不携带脚本源码、外置 XAML、config 目录、runtime.json 或 Overlay-Manifest.json。这是编译与资源嵌入，不是加密或防反编译保证。

本次只生成本地 v1.0 ZIP，不修改既有 GitHub Release 附件，不构建安装器。共享运行目录不部署本轮桌面改动。814 个已验收游戏资源保持输入摘要；地图模块和地图资产采用当前共享运行清单。既有游戏通关反馈不等于新桌面入口和地图组合已经完成游戏验收。

## 模块与资源

- `src/desktop/CompiledEntry.cs`：Configure.exe / Game.exe 桌面入口。
- `src/desktop/Configuration.cs`：WPF 设置、直接选择项、保存、恢复默认和子进程状态。
- `src/desktop/RuntimeCore.cs`：配置验证、运行路由、资源摘要检查与恢复。
- `modules/DesktopRuntime.dll`：上述公共实现；静态资源以 `mc/` 名称嵌入程序集。
- 图标、标题图、XAML、语言目录、显示预设、52 字节配置模板和两份清单均内嵌；不提取并执行脚本。
- 原生运行模块、地图与字体继续作为运行数据存在。程序依赖 Windows .NET Framework 4.x / WPF，不再依赖 PowerShell。

每份清单列出桌面 EXE 和运行资源摘要；公共 DLL 不在自身内嵌清单中计算递归自摘要。最终 ZIP SHA-256 覆盖公共 DLL 在内的全部归档字节。清单和摘要是完整性核对，不是数字签名或恶意文件检测。

## 用户设置与布局

设置路径为 `%LOCALAPPDATA%/MagnaCarta/Installations/<安装目录标识>/enhancements.json`，日志与运行配置在同级 `cache/`。标识沿用安装根目录标准化后 SHA-256 前 16 位。已存在的用户设置优先；仅当用户设置不存在时迁移旧 config/enhancements.json，否则使用内嵌默认值（1080P / 无边框 / 60 帧）。存档位置不变。游戏目录显示 INI 仍按原生组件要求保留。

配置窗口默认 790×600 DIP，保留小工作区滚动和窗口化尺寸选项。底部提示改为横排，相邻项目用两个空格分隔：

```text
F5切换随机遇敌  F9切换小地图  F10普通自动连招  F11暴走模式自动连招
```

提示区不再保留原先底部 16 DIP 空白；窗口较初版 670 DIP 高度减少 70 DIP。离屏预览与测试不代表实际显示器视觉验收。

## 构建与检查

输入仍为已验收覆盖 ZIP 和明确摘要，不构造完整游戏副本。MC.ico 由调用者提供，不提交图标原文件。命令中的输入摘要必须来自对应文件，不使用占位值绕过校验。

```powershell
python tools/build_compiled_release.py --source dist/MagnaCarta-zh-CN-v1.0.zip --source-sha256 44875140bcb101c017aa3759a3570f80949d8d1f7b99ad41989977f70eb38911 --icon V:/MC.ico --runtime runtime --work build/compiled-release-v1-final --output dist/MagnaCarta-zh-CN-v1.0-desktop.zip
python tools/verify_compiled_release.py --archive dist/MagnaCarta-zh-CN-v1.0-desktop.zip --icon V:/MC.ico
python -m unittest discover -s tests -p test_compiled_desktop.py
python -m unittest discover -s tests -p test_configuration_material.py
```

构建目录和输出 ZIP 必须不存在；历史脚本打包器保留用于复现原始版本。审计工具逐项核对 ZIP CRC、外置源码缺失、资源清单、原生 ICO 图像帧、窗口图标和 814 个游戏资源。托管元数据审计使用 ReflectionOnlyLoadFrom，不执行被审计程序集。

## 玩家入口与恢复

```powershell
./Configure.exe
./Game.exe --verify-only
./Game.exe --check-installed
./Game.exe --check-baseline "ORIGINAL_GAME"
./Game.exe --rollback "ORIGINAL_GAME"
./Game.exe --without-test-candidates
```

`--verify-only` 不启动游戏；Configure.exe 对应参数仅做隐藏 UI 自检。回滚先预检所有被覆盖资源的原版摘要，再恢复资源并移除新增文件，保留用户设置与存档。整个回滚不是跨文件事务；中途 IO 失败需要依据日志处理，不声明全局原子性。回滚后应使用原版游戏入口。

将 ZIP 覆盖解压到旧安装不会删除旧脚本。确认设置迁移和新入口检查成功后，可将旧 config 目录、Start.ps1、Verify-Overlay.ps1、runtime.json 和 Overlay-Manifest.json 移出游戏目录留作备份；新入口不使用这些文件。新 ZIP 本身不含这些外置文件。

## 验证与告警记录

自动测试使用自有微型数据、拒绝非 verify-only 参数的模拟原生入口，覆盖 24 种显示组合、功能开关、用户设置迁移、错误预检、INI 恢复、日志保存、完整覆盖包恢复和隐藏 WPF 预览。全量测试与此集成测试应串行执行：原生入口空闲检查是全局检查，并行测试可能触发“Exit game and native launcher first”。不修改生产空闲保护来迁就测试。

2026-10-25 用户提供安全软件截图：HEUR:Trojan/MSIL.Loader.d，文件被删除。临时 native-preflight/OwnedEntry.exe 在编译后缺失，调用失败为 WinError 2；对应源码是临时反射校验入口，不属于分发包。该临时程序没有恢复或重跑，未更改安全软件设置。仅凭截图和缺失文件不判定误报；真实原生入口的该次校验未执行，不能记录为通过。正式发布包的文件审计和功能测试不等于杀毒软件扫描通过。

本轮测试记录：全套 1076 项通过（3 项跳过）；随后横排提示调整的编译桌面 18 项与 WPF 5 项重新通过。790×600 离屏预览回读正常，默认布局无需滚动。自有数据独立回滚恢复 1 项、移除 12 项新增文件，存档和用户设置保持原字节；正常修改副本保留。详细命令、输出与本地归档摘要保留在 runtime/maintenance/compiled-desktop-v1-20261025。
