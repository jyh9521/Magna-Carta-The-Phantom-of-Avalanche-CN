# 单份游戏数据与共享运行模块

2026-10-14。此布局取代历史 `build/*-game` 验收副本。历史文档用于研究记录，
其中旧本机入口、调试输出和回滚副本不再保留，也不再作为功能更新依赖。

## 本机目录

```text
runtime/
  data/                   唯一可运行游戏数据，含当前使用的存档
  modules/                自有launcher和显示/现代输入动作/纹理/相机/地图模块
  config/                 可编辑增强设置、GUI、五种显示配置、52字节基础设置
  maps/                   地图功能实际使用的169份图层和元数据，不是调试截图
  art/                    当前4K标题资产母版与对应资源摘要，供重建/后续美术修改
  saves-import/           旧副本中去重后的独有存档及来源索引，不是游戏回滚副本
  build-inputs/           重建原生字体/系统消息所需的两个生成头文件
  dependencies/           原研究/验证Python依赖的一份副本
  cache/                  最近一次运行所需的小型设置/日志，覆盖使用，不创建session副本
  maintenance/            小型迁移/清理验证记录，无完整游戏备份
  Play.cmd
  Configure.cmd
  Play-motion.cmd
  Play-gamepad.cmd
  Play-texture.cmd
  Play-camera.cmd
  Play-maps.cmd
```

不同功能入口始终指向 `runtime/data`。各模块独立保留版本和文件摘要；
动作与手柄使用相同的现代化模块，但通过独立配置选择功能，不复制游戏数据。
其它模块维持已有候选版本，本轮仅迁移，不把目录整合当作功能Bug修复。
已知A/X绑定、相机移动、地图实用性及剩余60FPS问题仍按玩家反馈推进。

`Play.cmd`读取当前增强配置；`Configure.cmd`修改同一份配置。
`Play-baseline.cmd`关闭现代动作/手柄候选。
显示入口 `Play-render4k/wide4k/fps60/combined.cmd` 可单独对照显示。
纹理、相机和地图入口分别选择对应模块及功能开关。环境变量在启动结束后恢复。
所有入口共用游戏运行检查和互斥锁；不同功能不可同时启动同一数据。

## 校验和升级

启动器校验支持的游戏版本、标题资源、模块、配置代码和显示配置；
只修改已知显示INI，不绕过未知版本守卫。不再依赖第二份原版游戏目录的实时校验。
实际游戏和模块版本摘要在本机 `runtime/runtime.json` 中。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -Recipe configured -VerifyOnly
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -Recipe motion -VerifyOnly
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -Recipe maps -VerifyOnly
```

`VerifyOnly`不启动商业游戏。启动守卫通过不代替实机验收。
每次新增或修正功能，只构建相关源代码、更新对应自有模块及摘要、运行预检；
禁止为每个功能重新复制整套游戏。`tools/prepare_shared_runtime.py`只生成小型运行包，
不复制或删除游戏数据；唯一数据的迁移单独执行。

原生重新构建：

```powershell
cmake -S src/runtime -B build/native -A Win32 -DNATIVE_FONT_DATA_HEADER="$PWD/runtime/build-inputs/native_font_data.h" -DSYSTEM_MESSAGE_RULES_HEADER="$PWD/runtime/build-inputs/system_message_rules.h" -DWORKSPACE_EXE_SHA256=6046b29600b5e009903b3495bd11df0b4d89fc3545adde028193ea9fbff8d4de -DLOCALE_ENGINE_SHA256=5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427
cmake --build build/native --config Release --target workspace_profile workspace_launcher
$env:PYTHONPATH="$PWD/runtime/dependencies"
python -m unittest discover -s tests
```

原安装光盘镜像/升级补丁 `game/` 是重建来源，不是第二份可运行游戏目录；保留。
源码、语言数据、依赖许可和美术源资产保留；完整商业数据和自有生成DLL不推到GitHub。

## 清理边界

用户已明确要求直接释放空间，不保留历史调试、截图和游戏回滚副本。
先推送源码并确认远端HEAD一致，迁移必要数据和独有存档，再删除
`build/`、`out/`、`dist/` 中除最新统一测试 ZIP 外的产物，以及唯一游戏目录中废弃的旧入口、session、备份运行目录。
不建立另一份全量备份。删除后的旧副本及调试证据不可从本机恢复；
源码历史仍在GitHub，必要的构建输入和当前数据留在新布局。

## Shared launcher log reuse (2026-10-14)

Verified: StartShared reused cache/profile.log, while workspace_launcher refuses an existing log. Its verify-only branch returns before that check, so engine hash preflight did not prove launch readiness. The shared entry now removes only that single prior session log under the existing session mutex and running-game exclusion, before real launch. Verify-only preserves it. Directories and reparse points are rejected; other logs, saves and game assets are untouched. Repeated-cache tests execute the actual PowerShell preparation block without launching the game. Game startup remains manual acceptance.

## 单份最新测试包清理（2026-10-19）

`Clean-generated.cmd` 保留 `dist/MagnaCarta-unified-test*.zip` 中修改时间最新的一份，
删除旧包、已解压包、构建/隔离测试/回滚副本与工具、测试的 Python 缓存。
同时间按名称升序选择，找不到统一测试 ZIP 时停止；删除前统一检查路径、链接和已跟踪文件。
原版 `game/` 光盘与补丁、当前 `runtime/data`、存档、配置、模块、依赖及研究记录保留。
运行清单引用的 `data/*.cmd` 等入口同样保留，不按扩展名判作旧文件。

预览：`powershell -NoProfile -ExecutionPolicy Bypass -File tools/CleanupGenerated.ps1 -PlanOnly`。
执行仍要求源码已提交并与远端 main 一致、游戏和启动器已退出、运行资源与存档摘要通过。
预览不删除文件；执行记录保留测试包路径和 SHA-256，清理后再次核对包摘要。
验证：`python -m unittest discover -s tests -p test_cleanup_generated.py -v`，
在临时本地 Git 仓库验证保留一包、存档保护、预览、无包停止和已跟踪文件保护，不启动游戏。
