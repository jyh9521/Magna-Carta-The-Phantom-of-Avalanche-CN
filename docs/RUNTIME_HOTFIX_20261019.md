# 2026-10-19 显示／混合动画运行模块热修候选

旧版统一测试包 `MagnaCarta-unified-test-20261017` 的小型更新，不需要重新复制游戏。
本机已更新8份自有DLL与runtime.json，存档、增强设置和商业游戏资源未改。

## 玩家使用

解压 `MagnaCarta-display-motion-hotfix-20261019.zip`，运行 `Update.cmd`，
输入原测试包安装目录（该目录直接包含 `runtime.json`、`Play.cmd`）。
它不是 `data` 子目录，也不是原版安装目录。未知版本或模块/开场资源变化时整批拒绝。
也可执行 `Update.cmd -Target "D:\MagnaCarta-PlayerTest"`。
回滚：`Update.cmd -Action Rollback -Target "D:\MagnaCarta-PlayerTest"`。
仅在 `.runtime-updates/display-motion-20261019` 保存9份小型运行文件，保留存档和设置。
使用本包 `-Action CheckInstalled` 校验热修；旧安装器的payload摘要仍代表旧版，不是热修校验器。

## 修改及证据边界

- [混合动画相位](RIGID_MOTION_PHASE.md)：补齐刚性动画renderer，身体与部件的33个余数相位一致。
- [开场居中](OPENING_CENTER_REPAIR.md)：locale元数据源锁，两套FDI按实际画布水平/垂直中心平移。
- 默认、固定配方和手柄组合使用同一新版源码；原33ms逻辑计时、游戏资源与设置不改。
- 14个共享入口VerifyOnly通过，非实际启动；guard-page刚性布局、SEH恢复、源漂移拒绝、独立回滚均通过。
- 热修脚本用自有微型文件执行安装、检查、撤销；未知输入、资源变化和安装后新改动均整批拒绝。
- 真实眼球资源归属和笔记本最终图像尚未验收；保留60帧，原存档走动/转身/停止，再新游戏检查两套开场文字。

## 重建

按BUILDING.md生成locale开场头文件并配置Win32构建，再构建workspace_profile。
先按runtime.json预检全部旧模块；将所有8份modules/*.dll替换为本次workspace_profile.dll，
更新runtime.json对应摘要并加入locale opening-layout.json的resource SHA256源锁。
变更记录格式沿用update_configuration_runtime.py的changes.json（before/after），原文件位于original/。
本机记录为build/eye-vow-repair/runtime-deployment；它只包含9份小型运行文件。

```powershell
python tools/build_runtime_hotfix.py --runtime runtime --record build/eye-vow-repair/runtime-deployment --metadata locales/zh-CN/opening-layout.json --output dist/NEW_HOTFIX
python -m unittest discover -s tests -p test_runtime_hotfix.py
```

生成器整批校验原备份、新模块和开场资源后才创建输出，ZIP再次读回验证。
运行包不含原版完整游戏文件、存档或当前设置，只含自有模块、摘要和更新器。
