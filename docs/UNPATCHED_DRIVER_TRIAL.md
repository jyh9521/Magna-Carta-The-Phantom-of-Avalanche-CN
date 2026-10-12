# 未更新驱动对照

## 调查依据

模型、森林几何及纹理消失的相似报告见 [GameFAQs 原讨论](https://gamefaqs.gamespot.com/boards/582633-magna-carta-the-phantom-of-avalanche/79418682)。[英文项目指南](https://github.com/Nejuf/magnacarta-installguide/blob/main/InstallGuideForMagnaCartaThePhantomOfAvalanche.md#applying-the-patch) 收录恢复补丁前 Drv 的方法。外部成功报告为候选依据，不作为当前环境的修复证明。

HAL 对照已收到无改善反馈，DISPLAY-01 保持未修复，不继续调整同组设备参数。下一项只比较驱动版本。

## 来源与版本

参考项目 Nejuf/magnacarta，维护者 Nejuf；固定 commit `9ce77cace0d717f5ad75bb2910517802e55932c8` 的 [Drv_unpatched 目录](https://github.com/Nejuf/magnacarta/tree/9ce77cace0d717f5ad75bb2910517802e55932c8/Drv_unpatched) 提供两个文件。本轮只读取该仓库，不更改上游、不将游戏 DLL 纳入版本控制或发行包。

| 文件 | 当前补丁驱动 SHA-256 | 上游未更新驱动 SHA-256 |
|---|---|---|
| AsrD3DDrv.dll | 27db21dee7dde8ca3463e11fab57cc0b7cf6a7ed3338c950b6b1181eed7959ed | 00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29 |
| AsrGlDrv.dll | ad6b5cafdcebcecf41754dbd0b225fe898a08282b917c2205a00da4317ca4e46 | 54d037a13d2e76dc06b6eff47219ca25f0af8cc1ec66683bd856b07088a518fc |

两组文件大小分别为 155648 和 45056 字节，内容不同。PE32/x86、六项导出名称与序号一致。新候选对本地 Core、Asura、MSVCP60、MSVCRT 的全部导入均在当前依赖导出表中找到；AsrD3DDrv 对 Asura 的 267 项导入均匹配。导出存在不证明对象布局、语义或运行兼容，仍需游戏验收。

四张原版镜像中未发现裸露的 Drv DLL。CD1 安装数据为 InstallShield CAB/HDR，现有 NanaZip 无法将 DATA1.CAB 作为 Microsoft CAB 打开。尚未完成安装包驱动提取，因此本轮候选只能称为上游标记的未更新驱动，不宣称已与原版镜像驱动逐字节一致。

## 隔离方案与重建

从无层工作基线复制至独立 build/runtime/unpatched-game，原安装及其他候选副本不变。复制前后核对全部文件哈希。仅替换 Drv 中上述两个文件；EXE、MCAlpha、Asura、Core、存档及资源不更换。

```powershell
python tools/prepare_workspace.py --source build/runtime/game --target build/runtime/unpatched-game --manifest build/unpatched-driver-evidence/game-copy-manifest.json
python tools/driver_candidate.py apply --workspace build/runtime/unpatched-game --source build/unpatched-driver-evidence/upstream
python tools/driver_candidate.py rollback --workspace build/runtime/unpatched-game
```

source 目录须包含固定 commit 下 Drv_unpatched 的两个文件，工具按固定哈希验证，不下载动态最新版。未知游戏或引擎哈希、未知驱动、链接路径、现有兼容层和已有试验历史均拒绝应用。修改前在副本的 .driver-trial-original 保存原驱动，.driver-trial.json 记录来源、状态及两组哈希。
恢复先验证全部候选及备份，才恢复两项原字节；更改过的文件保留并停止恢复。备份和 restored 状态保留作审计，不在同一目录静默重复应用。写入失败尽量恢复同组文件；电源或进程中断后必须重新核对记录和哈希。

本地 LaunchUnpatchedDriver.cmd 显式选择该副本及 Direct3D 配置，启用异常采集但不启用 TextureLifetime。旧候选的槽地址只适用于补丁驱动，不能套用到本次驱动。副本没有 ddraw 等额外图形 DLL；图形路径为系统 DirectDraw，显示模式可能与兼容层无边框方案不同。

## 验证与验收

自动样本覆盖两驱动往返、未知输入、图形层冲突、已有历史、候选/备份被改动及写入失败恢复。65 项单元测试通过。隔离回滚对照使用另一份副本，不恢复待测试副本。

## 首次实际验收结果

2026-10-12 测试反馈确认画面恢复正常。对应会话 `session-20261012-122543-833`，PID 37588，工作目录为 build/runtime/unpatched-game；日志确认加载该副本 Drv/AsrD3DDrv.dll，自然退出码为 0。图形输入记录为空，未启用 TextureLifetime；候选驱动文件哈希与固定来源一致。

当前读档场景的模型显示问题按实际反馈通过首轮验收，证据为测试反馈及对应运行记录，而非自动图像比较。恢复未更新驱动是有效处理方案；尚未定位补丁驱动中导致问题的具体指令，不将其称为完整根因证明。

该副本保留为当前可用显示基线，继续使用 LaunchUnpatchedDriver.cmd。原安装、无层补丁驱动对照及历史实验保留，后续无边框、高分辨率和输入增强另建副本，不直接叠加到可用基线上。

连续观察时间、多场景切换、长时间运行、新游戏、媒体、无盘和中文资源尚未完成系统验收。后续仍按相同存档和操作记录场景、时长与退出码，不能将本次画面恢复扩展为全部功能通过。
