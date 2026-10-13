# 高级显示候选：玩家验收

本轮冻结汉化，暂停手柄开发。候选使用键鼠；入口不启用现代手柄参数。
以下是验收方法，不是实机验收通过声明。

## 准备（开发者）

新原生模块编译到 `build/advanced-display-native/Release` 后执行：

```powershell
python tools/prepare_advanced_trial.py --source build/disc-gate-game --native build/advanced-display-native/Release --output build/advanced-display-game
powershell.exe -NoProfile -ExecutionPolicy Bypass -File build/advanced-display-game/.advanced-runtime/StartAdvanced.ps1 -Mode combined -PrepareOnly
```

输出目录必须是仓库 build 下的全新独立目录。准备工具复制并逐文件验证原资源；不启动游戏。
PrepareOnly 取得既有 Direct3D 配置并选择对应 INI，也不启动游戏。
原 `build/disc-gate-game`、汉化资源、原存档和旧启动工具不改。
候选带有开始时复制的存档；玩家在候选内保存会产生自己的进度，回滚不覆盖任何存档。

## 玩家入口

在 `build/advanced-display-game` 内，逐个双击以下文件。每次先退出游戏，再换入口：

| 文件 | 作用 | 本轮验收重点 |
|---|---|---|
| `Play-baseline.cmd` | 原1080行、4:3对照 | 同存档、同场景截图与计时 |
| `Play-render4k.cmd` | 2160行、4:3 | 预计2880×2160内部画面，不等于3840×2160真宽屏 |
| `Play-wide4k.cmd` | 4K与16:9投影候选 | 预计3840×2160；两侧视野增加、主体比例不变 |
| `Play-fps60.cmd` | 原分辨率、60Hz呈现候选 | 动作/计时不翻倍，输入、对话与视频不失常 |
| `Play-combined.cmd` | 真宽屏4K与60Hz呈现组合 | 单项无异常后再测组合 |
| `Rollback.cmd` | 恢复候选基准INI | 不卸载原汉化，不回写原副本或存档 |

双击入口失败时窗口暂停；把报错截图和日志发回即可。不要手动改候选INI。
入口验证源版本、候选标记、原生模块和五种已知INI，运行中的同目录游戏会阻止切换。
源码中宽屏INI原本仅是门禁草稿；本交付只通过明确的原生 `--display-profile` 投影集成启动，单独复制INI不构成真宽屏。

## 验收顺序与标准

1. 基准：加载固定存档，不移动镜头，拍截图。记录移动到固定目标的耗时。
2. 4K：同场景对照；字/UI清晰、正常换行，鼠标点击位置与画面一致。核对日志中的实际尺寸；只看桌面或截图分辨率不算内部渲染验证。
3. 真宽屏：与基准相同站位、镜头，人物宽高比例不变，左右出现更多场景，而不是把4:3横向拉伸或裁掉上下画面。菜单、字幕、视频也要逐项检查。
4. 60Hz：分别测试探索、菜单、对话、战斗、视频；重复相同路径并计时，游戏逻辑不应加速。核对日志中的呈现/逻辑计数。
5. 组合：重复以上测试，加测存读档和至少五次Alt+Tab。双指针、点击失效、闪屏或崩溃均记录，旧鼠标故障不默认为已修复。

当前计时设计是约60Hz呈现、约33ms逻辑步长，尚无运动插值；画面呈现频率不等于人物动画已完整60FPS化。
REA/夹具可以验证投影参数与计时分支，不能代替全流程游玩，也不能证明全部已知游戏Bug解决。

## 日志和恢复

每次入口创建 `.advanced-runtime/session-*`：准备输出、选用INI哈希、配置副本、原生 `profile.log`、启动器标准输出/错误和退出码。
失败还记录 `failure.txt`。反馈：入口名、存档/地点、表现、截图、该session整个目录。

退出候选后双击 `Rollback.cmd` 恢复基准；或者直接用原来的游戏入口继续玩原副本。
回滚遇到未知哈希会停止，避免盲目覆盖。原副本始终保持原样。
