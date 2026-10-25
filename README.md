# 《真名法典：冰之魅影》本地化工程 / Magna Carta: The Phantom of Avalanche Localization

编译式桌面封装修订（本地 v1.0 ZIP）：配置器、启动和校验逻辑编译，静态资源内嵌，玩家设置迁入用户数据目录，快捷键提示改为紧凑横排。构建、迁移与验收边界见 [编译式桌面入口](docs/COMPILED_DESKTOP_RELEASE.md)。既有 GitHub 发布附件不在本轮自动替换。

## 项目简介

初代 PC 版《真名法典：冰之魅影》（마그나카르타: 눈사태의 망령）的简体中文汉化与现代 Windows 兼容性工程。

当前目标语言为简体中文 `zh-CN`。仓库保存结构化译文、术语、资源提取与重建工具，以及显示、输入等增强模块；语言数据与通用工具分离，保留后续适配其他语言的基础。

## 发布版本 v1.0

当前针对项目已记录指纹的 PC 安装样本开发，未知版本会被校验工具拒绝。样本与所提供 1.04 补丁的差异见[版本调查](docs/SAMPLE_AUDIT.md)，不将所有标为 1.04 的安装视为相同版本。

- **文本与字体**：当前结构目录共 4,137 个字段，包含 4,091 条译文和 46 条明确保留项；427 份结构资源与两套原生字库已完成重建、逆解码及重复构建验证。
- **图片、视频与系统提示**：已完成中文资源并纳入发布构建；SOFTMAX 开头 Logo、开发人员名单、指定保留图及旧存档名字不作汉化或改写。
- **兼容性与增强**：集成图形兼容层、高清标题、1080P/2K/4K/自适应、窗口模式、30/60 帧、地图、连招辅助及最终修复。手柄与自由视角研究功能已归档，不列入正式功能。
- **发布状态**：**Release v1.0 已发布**。2026-10-25 收到完整流程通关、测试无误的验收反馈。汉化与最终修复合并为单一 ZIP。

发布验收以完整流程通关反馈为依据；新增桌面入口与紧凑配置界面另经离线验证。详细范围见[全文候选与增量包](docs/LOCALE_PACKAGE.md)，历史问题与调查见[已知问题](docs/KNOWN_ISSUES.md)。

## 下载与使用

仓库提供源码、译文和构建工具，不包含游戏本体，也不包含本机 `runtime/` 运行目录。测试包说明见[统一玩家测试补丁包](docs/PLAYER_TEST_PACKAGE.md)。

### 正式发布包

[下载 Release v1.0](https://github.com/jyh9521/Magna-Carta-The-Phantom-of-Avalanche-CN/releases/tag/v1.0)。
文件名：`MagnaCarta-zh-CN-v1.0.zip`。

将 ZIP 中全部文件解压到匹配的纯净游戏目录（`MagnaCarta.exe` 所在层），替换同名文件。
原版独立备份须保留。双击 **`Configure.exe`** 配置，双击 **`Game.exe`** 启动；不再使用 CMD 作为玩家入口。
两份 EXE 各约 8 KiB，依赖 Windows 自带 .NET Framework 4.x、Windows PowerShell 5.1 与 WPF。
`config/`、`modules/`、`fonts/`、`maps/` 与 `Start.ps1` 为外置运行组件，须完整保留。
默认 1080P、无边框、60 帧；配置工具支持切换 30/60 帧。
完整安装、校验、恢复与构建说明见 [v1.0 发布说明](docs/RELEASE_V1.0.md)。

### 本地开发运行目录

共享运行目录使用 `runtime/Configure.exe` 与 `runtime/Game.exe`，共用既有数据与存档。
历史 `Play-*.cmd` 与研究文档仅保留技术对照用途，不作为正式发布入口。
目录准备与原生重建见[共享运行布局](docs/SHARED_RUNTIME_LAYOUT.md)。

## 从源码重建

依赖、版本校验、译文检查、字体生成、资源重建及原生模块编译见[构建说明](BUILDING.md)。原版游戏和字体等输入须按文档单独准备；克隆仓库并不包含这些输入。

正式包基于摘要锁定的通关覆盖包构建：

```powershell
python tools/build_desktop_entries.py --output build/desktop-entries
python tools/build_release_v1.py --source dist/ACCEPTED_OVERLAY.zip --source-sha256 ACCEPTED_SHA256 --entries build/desktop-entries --output dist/MagnaCarta-zh-CN-v1.0.zip
```

输入身份与完整命令见 [v1.0 发布说明](docs/RELEASE_V1.0.md)。原始资源提取、增量重建及历史测试包流程仍保留在 [构建说明](BUILDING.md)，用于独立复现技术管线。生成物保存在 `build/`、`dist/` 或 `out/`，不进入源码仓库。

## 参与翻译 / 添加语言

翻译以韩文原版为语义基准，英文汉化仅作技术、定位与语义参考。译文按稳定 ID 与原文摘要绑定，保留控制码、占位符和内部标识。

- [翻译规范](TRANSLATING.md)：翻译、上下文校对与保护标记。
- [术语表](GLOSSARY.md)：由 `locales/zh-CN/terms.json` 生成；系列译名参考固定版本，词面相同不自动认定为同一概念。
- [贡献与版本管理](CONTRIBUTING.md)：提交、验证与协作约定。

新增语言应将数据放入 `locales/<locale>/`，并验证编码、字形覆盖、字段容量与游戏内排版；当前不声称其他语言已经完成适配。

## 仓库结构

| 目录 | 内容 |
| --- | --- |
| `locales/zh-CN/` | 译文、术语、语言配置与范围决定 |
| `tools/` | 提取、校验、字体、资源重建及打包工具 |
| `src/` | 原生运行模块与启动工具源码 |
| `patches/`、`assets/` | 补丁数据、项目素材与第三方来源记录 |
| `tests/` | 自动化测试与受控夹具 |
| `docs/` | 格式、逆向、构建、专项验收与限制说明 |
| `build/`、`dist/`、`out/`、`runtime/` | 本地生成物与运行数据，Git 忽略 |

## 技术与测试文档

- [技术说明](TECHNICAL.md) · [文件格式](docs/FILE_FORMATS.md) · [技术陷阱](docs/PITFALLS.md)
- [全文汉化管线](docs/FULL_TRANSLATION_PIPELINE.md) · [媒体汉化](docs/MEDIA_LOCALIZATION.md)
- [增强配置工具](docs/CONFIGURATION_MATERIAL.md) · [技术路线](docs/MODERNIZATION_ROADMAP.md)
- [运行调查](docs/RUNTIME_RESEARCH.md) · [验收清单](docs/RUNTIME_TESTING.md)

## 许可与致谢

本项目使用独立仓库与独立提交历史。英文汉化工具参考来自 [Nejuf/magnacarta](https://github.com/Nejuf/magnacarta)，署名 Talbain（Lakuuna）、Sobodash、Nejuf；来源版本与验证范围见[运行调查](docs/RUNTIME_RESEARCH.md)。

项目原创代码与文档采用 MIT，原创译文采用 CC BY-SA 4.0；字体和第三方组件遵循各自许可。原始游戏文本与商业资源不在上述授权范围内，不发布完整原版游戏文件。详见[许可与来源](LICENSING.md)及[译文许可](LICENSE-translations.md)。

## 配置与日志位置

增强设置与运行日志保存到当前用户的 `%LOCALAPPDATA%\MagnaCarta\Installations\<安装标识>`。
`enhancements.json` 保存设置，`cache/` 保存启动日志与运行配置；安装标识由规范化安装路径生成，不同安装互不覆盖。
首次运行导入游戏目录已有设置，旧文件保留；后续更新不覆盖已保存的用户设置。存档位置保持原样。
