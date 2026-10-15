# 配置工具接回共享运行入口（2026-10-15）

入口预检对游戏显示 INI 的临时切换和恢复见 [配置预检事务](CONFIGURATION_VERIFY_TRANSACTION.md)；预检仍更新 cache 诊断文件，不等于零磁盘写入。

## Verified

迁移后活动 `runtime/config/Configure.ps1` 仍尝试启动同目录 `StartEnhanced.ps1`，而共享目录中没有该文件。直接以 `-File runtime/config/StartEnhanced.ps1 -VerifyOnly` 调用实际返回 -196608，提示文件不存在；没有启动游戏。先前仅检查控件值的隐藏表单自检未覆盖这个连接。

新增语言无关 `Get-EnhancementLaunchSpec`：检测父目录 `runtime.json` 时必须使用父目录 `Start.ps1 -Recipe configured`；共享入口缺失时明确报错，不退回旧脚本。没有共享清单的旧独立布局仍支持 `StartEnhanced.ps1`。路径与参数分开构造，包含空格/非 ASCII 的路径通过自有脚本验收；入口存在性在写配置前检查。

`StartShared.ps1` 新增显式 `SettingsFile` 参数，缺省仍读取 `config/enhancements.json`，保证配置工具保存的文件与入口读取的是同一份。固定配方仍按既有规则覆盖其预设设置。日志提示按布局生成：共享目录为 `cache/profile.log`，旧独立目录为 `session-*/profile.log`。

中文配置页现标示 X 为原生空格、右摇杆为菜单指针，并说明菜单保留定位指针。游戏汉化正文、字体与标题资源未修改。

## 自动验证

`tests/test_configuration_launch_route.py` 覆盖共享优先、旧布局、入口缺失拒绝，以及隐藏表单通过真实 `Run-Entry` 路径启动自有验证脚本，检查 `configured`、明确设置文件和 `VerifyOnly` 实际到达。自有脚本不是游戏入口。

```powershell
python -m unittest discover -s tests -p test_configuration_launch_route.py
```

`Configure.ps1 -SelfTest -VerifyEntry` 要求显式且不同于默认配置的测试设置文件，表单不可见，子进程只走 VerifyOnly。通常 `-SelfTest` 不启动子进程。离屏预览确认四行按键说明无裁切，不代替所有 DPI 下的窗口验收。

## 玩家入口

`runtime/Configure.cmd`：保存设置后关闭重开，检查值保持；点击“检查入口”应通过且不启动游戏。游戏仍由玩家点击“启动游戏”或手动入口启动。手柄验收仍用 `runtime/Play-gamepad.cmd`，当前菜单与指针的实机确认不由配置测试替代。

仅更新配置脚本、界面说明与清单摘要；所有角色 DLL、共享游戏数据、存档和默认设置保持不变，不创建完整游戏副本。
