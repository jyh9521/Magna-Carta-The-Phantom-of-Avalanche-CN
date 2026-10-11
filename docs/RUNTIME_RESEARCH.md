# 运行环境、兼容层与无盘运行静态调查

日期：2026-10-12。证据等级：已验证 / 高置信推断 / 未验证假设。
“已验证”在本文可以指文档确实如此记载，不自动表示本项目复现了运行行为。

## 版本与来源

| 来源 | 固定版本 | 阅读范围 |
|---|---|---|
| Nejuf/magnacarta-installguide | `0e998f6ab759a6c12c21d07e90c52d188a9b727c` | README、安装指南、GitHub 元数据与文件树 |
| Nejuf/magnacarta | `9ce77cace0d717f5ad75bb2910517802e55932c8` | README、LICENSE、文件树；本轮未完整审计转换脚本 |
| narzoul/DDrawCompat | `2c9a07fdf9308e2b0b117886a7e363b149ee1bc7` | README、官方配置 Wiki |
| FunkyFr3sh/cnc-ddraw | `279a057ee7e1e4d584b56141c014ab01f3c6ee6d` | README、仓库许可证元数据 |

初步调查使用的旧中文仓库 fork 自 `Nejuf/magnacarta-installguide`，不是工具仓库 `Nejuf/magnacarta`。2026-10-12 同名远端重建为独立仓库，新历史不继承安装指南；旧历史仅作本地归档。上述指南 commit 已在原上游核对。
主机注册表报告 build `26300.9550`、DisplayVersion `26H2`，ProductName 仍为 Windows 10 Home；标签存在歧义，不据此声称 Windows 10/11 双平台验收。
初步调查时源码/工具目录只有占位文件；随后新增文档检查脚本。三个候选安装目录检查均不存在，不代表已扫描整个硬盘。

## 游戏运行依赖

固定版本安装指南仍要求运行时挂载 MC_PLAY，因此这份指南没有证明无盘运行。MCV104a.exe 的来源、是否官方、内部修改和保护行为均待样本核实；英文工具仓库也没有提供游戏启动 EXE 的运行证据。

指南包含 Direct3D 选择、Drv 恢复及存档位于安装目录的说明。这些属于上游运行记录，提示优先调查驱动差异和写入权限，不属于本项目 Windows 10/11 复现结果。
`Drv_unpatched/AsrD3DDrv.dll` 和 `AsrGlDrv.dll` 的存在给出 Direct3D / OpenGL 驱动线索，但具体 API 版本与实际加载分支待 PE 和运行日志确认。

| 问题 | 当前判断 | 所需证据 |
|---|---|---|
| MC_PLAY 是否只有检查用途 | 未验证 | 盘文件清单、安装清单、全过程文件访问 |
| 盘上是否含必需媒体/资源 | 未验证 | 文件哈希、读取路径、媒体播放和场景测试 |
| 完整硬盘安装/原生路径机制 | 未验证 | 安装选项、配置/注册表、同输入有盘与无盘对照 |
| 原版或更新是否已有无盘功能 | 未验证 | 原版和更新来源、版本哈希、变更说明、实测 |
| 启动条件是否涉及保护 | 未验证 | 报错、启动流程、版本和访问证据；先记录限制 |

采用方案：尚未选定；使用与安装步骤：尚未发布；适配范围：没有已验收游戏版本。

## 兼容层评估

| 候选 | 官方能力与适用条件 | 本作结论 | 许可与分发 |
|---|---|---|---|
| DDrawCompat | DirectX 1–7；配置支持 `FullscreenMode=borderless`；须确认游戏加载相应 API | 无边框有官方功能依据，游戏可行性待测；不覆盖 OpenGL 或 DX8+ 分支 | 当前 0BSD，旧版二进制条款不同；固定实际使用版本 |
| dgVoodoo2 | 将旧 Glide / DirectX 1–9 API 转到 D3D11/12，提供分辨率覆盖与缩放 | Direct3D 分支候选；不据此断言原生分辨率或真实宽屏 | 作者专有分发条款，不称为开源；当前文档为 2.87.5，打包前按实际版本核对 |
| cnc-ddraw | 面向经典 2D 游戏的 DirectDraw 重实现 | 纯 2D DirectDraw 分支候选，不能据此假定适合本作 3D 渲染 | 当前 MIT；保留声明 |
| DxWnd | 官方项目定位为窗口化/兼容性工具 | 独立候选；版本、钩子范围和输入/焦点副作用待评估 | 尚未完成具体发行包许可证核查，不打包 |

DDrawCompat 官方明确不支持与其他 wrappers/hooks 组合。本项目也统一采用单兼容层隔离测试。
SDL3 Gamepad 是输入候选，其设备管理能力不意味着已接入本游戏；具体 SDL 版本、许可和映射数据许可在选型时另锁定。

无边框阶段性结论：可以设计单兼容层试验，但目前没有运行游戏的验证。安装指南未给出足以确认原始比例、内部分辨率、计时或输入 API 的证据。

## 测试输入需求

- 合法持有的韩文原版安装文件、MC_PLAY 内容清单及需要的安装盘；本地保存原件，提交哈希和研究记录而非完整资源。
- 实际主程序、启动/设置程序、Drv、配置文件、安装登记与依赖 DLL。
- 官方更新包、来源和版本说明；英文补丁包及清单，用于独立对比，不直接覆盖基线。
- 新游戏和多个剧情阶段存档、背景音乐/语音/视频样本，以及最小中文资源样本。
- Windows build、CPU/GPU/驱动、显示器/DPI/刷新率、设备型号；图形层版本及其哈希。

## 官方及项目来源

- [固定版安装指南](https://github.com/Nejuf/magnacarta-installguide/blob/0e998f6ab759a6c12c21d07e90c52d188a9b727c/InstallGuideForMagnaCartaThePhantomOfAvalanche.md)
- [英文工具及署名](https://github.com/Nejuf/magnacarta/tree/9ce77cace0d717f5ad75bb2910517802e55932c8)；LICENSE 为 BSD-2-Clause，署名 Derrick Sobodash（2003, 2012）；不把该许可证自动套用于商业游戏 DLL。
- [DDrawCompat 固定版](https://github.com/narzoul/DDrawCompat/tree/2c9a07fdf9308e2b0b117886a7e363b149ee1bc7) / [官方配置 Wiki](https://github.com/narzoul/DDrawCompat/wiki/Configuration)，Wiki 为 2026-10-12 查阅的动态页面。
- [cnc-ddraw 固定版](https://github.com/FunkyFr3sh/cnc-ddraw/tree/279a057ee7e1e4d584b56141c014ab01f3c6ee6d)
- [dgVoodoo2 作者说明与分发条款](https://dgvoodoo2.dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/)
- [DxWnd 官方项目](https://sourceforge.net/projects/dxwnd/)
- [SDL3 Gamepad 官方文档](https://wiki.libsdl.org/SDL3/CategoryGamepad)

上游信息是调查起点，所有本作运行行为仍需样本和实测。本轮未下载游戏、保护补丁或图形兼容二进制。
