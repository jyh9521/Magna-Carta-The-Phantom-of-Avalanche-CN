# 增强配置工具

> 当前共享布局的入口连接修正、现用配置入口与验证边界见 [共享配置入口](CONFIGURATION_SHARED_ENTRY.md)。以下独立副本路径是历史实验记录，不用于新交付。

2026-10-14。Windows自带PowerShell与Windows Forms界面，独立运行副本，不引入额外GUI运行库。通用设置逻辑在`src/configuration`，界面语言数据在`locales/<locale>/configuration-ui.json`；不修改游戏汉化数据。

## 有效选项

- 五个既有显示配置：1440×1080原比例、2880×2160原比例、3840×2160宽屏，以及1080行/宽屏4K的60Hz呈现候选。
- 完整动作插值候选：仅在两个60Hz配置可选，其他模式自动关闭并禁用勾选。
- 现代XInput候选：独立开关，默认关闭；关闭不卸载汉化或改变显示选择。
- 高清标题和无边框保留既有组合，不显示尚未实现的抗锯齿、材质替换等占位开关。

实际内部尺寸仍须以会话日志与游戏验收为准；不把显示器尺寸或预检结果等同内部渲染证据。候选文字在界面显式保留。

## 保存与启动

`enhancements.json`包含严格四字段：schema、display_profile、motion60、native_gamepad。未知字段、非布尔开关、未知模式和30Hz模式启用动作插值会拒绝。文件写入先生成临时文件，再原子替换、回读验证；未知原设置不盲目覆盖。设置不存到全局安装注册表。

“保存设置”只保存本副本设置。“恢复默认”恢复4K宽屏、30FPS和键鼠；不修改存档。“检查入口”执行版本/配置预检，不启动游戏。“启动游戏”才启动匹配的原生入口。入口进程运行时控件禁用，退出后显示状态；失败保留退出码与会话日志。

游戏启动是否成功以原生会话实际记录为准。配置脚本的结果区分launcher_invoked、verify_only与game_started；实际启动分支没有观察依据时game_started保留null，而不是把调用启动器当作游戏已启动。

## 构建

```powershell
python tools/prepare_configuration_trial.py --source build/disc-gate-game --native build/advanced-display-native/Release --locale locales/zh-CN --output build/configurable-modern-game
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File build/configurable-modern-game/.advanced-runtime/Configure.ps1 -SelfTest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File build/configurable-modern-game/.advanced-runtime/StartEnhanced.ps1 -VerifyOnly
```

源、副本、原生模块和标题资源沿用前两阶段版本锁。运行副本必须全新；正常画面、动作测试和手柄测试副本不回写。

## 玩家入口与验收

入口目录：`build/configurable-modern-game`。

1. `Configure.cmd`打开配置界面；选择模式、勾选候选、保存后关闭，再打开，选择应保持。
2. 选择30FPS配置时，动作插值开关应关闭且不可勾选。
3. 点击“检查入口”，游戏不应启动；结果与会话目录应生成。
4. 点击“启动游戏”，或者双击`Play-configured.cmd`，应使用保存的模式与开关。
5. 退出后点击“恢复默认”，重新打开应显示4K宽屏、30FPS、键鼠；存档仍保留。
6. `Rollback-configured.cmd`只恢复本副本的基准INI；旧正常入口始终保留。

隐藏表单自检验证12个控件、五个选项、值转换与功能门槛；离屏控件预览只作布局检查。五个真实副本配置分别执行VerifyOnly，均不启动游戏。实际显示、按钮点击、DPI与游戏启动仍待玩家验收。
