# 场景缺失与模型闪烁：图形兼容候选

## 问题与适用版本

2026-10-12 测试反馈报告模型消失后重新出现；截图还显示大面积黑色场景缺失、突兀三角形边界和孤立场景块。截图证明显示异常，不确定深度、裁剪、资源或渲染状态中的具体原因。问题编号 DISPLAY-01。

当前候选只适用于 SAMPLE_AUDIT.md 记录的 MagnaCarta.exe、MCAlpha.dll 和 AsrD3DDrv.dll 哈希组合；未知版本拒绝应用。原有游戏 EXE、Drv 和保护模块均不修改。

## 已采用的候选

单独使用 DDrawCompat v0.7.1，固定 commit `2c9a07fdf9308e2b0b117886a7e363b149ee1bc7`。该版本标记为预发布，不作为正式稳定发行包。来源：

- [固定发行页](https://github.com/narzoul/DDrawCompat/releases/tag/v0.7.1)
- [固定源码与许可](https://github.com/narzoul/DDrawCompat/tree/2c9a07fdf9308e2b0b117886a7e363b149ee1bc7)
- [官方配置说明](https://github.com/narzoul/DDrawCompat/wiki/Configuration)

发行 ZIP SHA-256：`0c33ecb1c01c1c779063b490a2e818f6d9227b3b4ee827c51790fb0fd59b17c5`，与 GitHub 发行资产 digest 一致。
x86 ddraw.dll SHA-256：`f75f0ac48d2782f225c483dc2f1142303a513e8dd8a60793891ade89f64755ea`。
许可为固定源码的 0BSD；候选仅下载到本地研究目录，当前仓库不提交第三方二进制。

只增加 `ddraw.dll`、`DDrawCompat-MagnaCarta.ini` 与 `.graphics-compat.json`。配置采用 borderless、app 比例、app 渲染尺寸和 info 日志；没有强制宽屏、高分辨率、60 FPS、深度格式或设备类型。
无边框属于配置候选，完整窗口与输入验收尚未通过。现存兼容层或配置拒绝覆盖，单层试验不叠加 dgVoodoo2、DxWnd 等组件。

## 应用与恢复

原版安装不是修改目标。先退出游戏及设置程序，再对 build/ 下的隔离工作副本操作；路径链接、未知原件、未知包和已有图形层均拒绝。

```powershell
python tools/graphics_compat.py apply --workspace build/runtime/game --package build/graphics-research/DDrawCompat-v0.7.1.zip
python tools/graphics_compat.py remove --workspace build/runtime/game
```

应用只新增候选文件。恢复先核对三个候选文件的受控内容，删除新增文件，不触碰原有资源和存档；新增 DLL 或配置被改动时停止恢复并保留文件。manifest 中的任意路径不用于删除。
游戏测试收到明确确认后才启动，已有副本快捷入口自动使用新增候选；持续开发不自动调用该入口。发生回归时关闭游戏并移除候选即可恢复无图形层基线。

## 已完成的测试

1. 26 项 Python 单元测试通过，包括版本不匹配、已有图形层、错误包、根目录越界、配置被改动、manifest 路径穿越和独立回滚。
2. Win32 Release 构建通过；独立 graphics_probe 使用隐藏窗口和 64×64 离屏目标，不显示窗口、不启动游戏、不调用 SetDisplayMode。
3. 原生 DirectDraw 与 DDrawCompat 各执行 120 帧 16 位深度测试。交替绘制顺序，近处绿色三角形在两条路径下均 120/120 可见，退出码均为 0。简单样本未复现故障，不作为游戏修复证据。
4. 本次明确测试指令后执行一次 20 秒副本启动采样：6 次进程采样均响应，实际加载副本 ddraw.dll。兼容层日志确认 v0.7.1、Direct3D hooks、IDirect3D7、D16 深度缓冲及 T&L HAL 设备。进程按限时结束，退出码 124，不作为自然闪退。

兼容层加载已验证，原始游戏场景的模型与地形显示修复仍待同场景对照。未验证存读档、媒体、全过程、无盘或其他平台兼容性；不将进程响应正常当作图形验收。

## 下一项游戏验收

使用反馈截图对应场景和相同操作，连续观察至少 60 秒，记录地形黑块、角色可见性和镜头变化；保存截图或录像以及兼容层日志。先比较当前单层候选与无层基线，失败后再研究设备类型、裁剪或深度状态，避免同时改变多项设置。

上游未修补驱动与当前驱动虽大小、导出名相同，但逐字节差异显著；未确认引擎 ABI 与版本兼容性，不作为可直接替换文件。
