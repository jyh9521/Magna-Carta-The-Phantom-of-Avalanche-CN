# 共享运行入口与当前候选打包

## Verified：旧入口和打包缺口

数据移动到`runtime/data`后，其中常用cmd仍指向`.advanced-runtime`中的历史
StartMotion/StartGamepad脚本及旧DLL。当前`runtime/Play-motion.cmd`则使用
摘要锁定的新模块。这两条路径不同，不能用当前源码测试结果支持旧入口验收。
未证明玩家此前具体使用了哪条路径，不能据此断言所有反馈都来自旧版本。

源码打包器原来将动作、手柄和组合固定映射到`modern`，即使明确提供
`motion-space`与`input-diagnostics`也不选择上述模块。旧源码的新回归失败：
`AssertionError: 'modern' != 'motion-space'`，另缺少`motion-gamepad`配方。

## 修正

- `prepare_shared_runtime.py`新增可选`--motion`、`--gamepad`，分别打包到
  `motion-space.dll`与`input-diagnostics.dll`，配方与配置映射跟随明确输入。
  未提供时保留显式legacy modern输入的原兼容路径，不声称会自动发现最新版DLL。
- 新配方`motion-gamepad`选择组合显示、完整动作候选及手柄，不开启自由视角或地图。
  接受的默认配置没有修改。
- `retarget_shared_entries.py`验证共享清单摘要、已知脚本字节及固定目标路径，
  在所有入口检查通过后才写入。未知用户脚本保持原样并阻止本次迁移。
  支持只读规划、幂等迁移；既不复制游戏，也不启动游戏。
- 实际迁移11个Play入口和1个Configure入口，均转到共享运行器/配置工具。
  完整60fps入口→motion；Xbox入口→motion-gamepad；Xbox30fps入口→gamepad。
  fps60/combined仍是原显示对照，不冒充完整动作插帧；明确LegacyPose与历史Rollback
  入口本轮未迁移，上述入口不作为当前验收入口。
- 已迁移脚本纳入运行清单摘要；常用旧入口不再加载历史`.advanced-runtime`DLL。

8项打包/迁移测试通过，覆盖候选选择、组合开关、源文件不复制、只读规划、幂等性、
未知脚本及模块漂移的写入前拒绝。独立源回滚恢复原3项打包检查。
实际两个cmd携带`-VerifyOnly`均预检成功，没有商业游戏启动。

## 维护命令

```powershell
python tools/prepare_shared_runtime.py --source USER_LOCALIZED_GAME --display build/native/Release/workspace_profile.dll --modern runtime/modules/modern.dll --motion build/native/Release/workspace_profile.dll --gamepad build/native/Release/workspace_profile.dll --texture runtime/modules/texture.dll --camera build/native/Release/workspace_profile.dll --maps build/native/Release/workspace_profile.dll --launcher build/native/Release/workspace_launcher.exe --atlas USER_MAP_ATLAS --output NEW_SHARED_RUNTIME
python tools/retarget_shared_entries.py --runtime runtime
python tools/retarget_shared_entries.py --runtime runtime --apply
```

首条命令仅生成小型运行包，输入需满足工具已有版本/本地化/标题摘要前置条件；
不复制游戏数据、不覆盖已有运行目录，不是对原始商业安装的自动完整迁移命令。
后两条只重定向已识别的自有脚本。未知旧布局和自定义入口不强行转换。

## 玩家验收

- 完整动作：`runtime/Play-motion.cmd`。
- 手柄单独对照：`runtime/Play-gamepad.cmd`。
- 动作加手柄：`runtime/Play-motion-gamepad.cmd`。

测试前退出旧游戏；三个入口共享`runtime/data`。先动作待机/行走/转身，再按用户
顺序验收Xbox的开头跳过、主菜单上下/确认/取消、游戏内菜单，以及A/X误绑定。
本轮修复的是入口与打包，不宣称解决新的手柄或画面问题。
游戏启动0次，完整游戏复制0份；仍保留源回滚证据，见
`runtime/maintenance/shared-entry-repair/VERIFICATION.txt`。
