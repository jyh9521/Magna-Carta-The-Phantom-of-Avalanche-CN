# 《真名法典：冰之魅影》本地化工程

初代 PC 版《真名法典：冰之魅影》（마그나카르타: 눈사태의 망령）的简体中文汉化与现代 Windows 兼容性工程。

## 当前状态

- 当前源码对应编译式桌面入口 **revision 4**：根目录设置、按需 UAC、完整运行输入校验和旧安装兼容计划。
- 汉化结构目录包含 4,137 个字段：4,091 条译文、46 条明确保留项；保留图片、视频、字体及运行模块的重建工具。
- 2026-10-25 收到此前完整补丁的通关反馈；后续地图和桌面入口修订分别记录离线检查与游戏验收。
- **2026-10-26 已核对：GitHub 尚无 Release 或标签。本轮只整理源码与构建文档，不发布附件。** 本地 ZIP 不等于 GitHub 下载。

## 开发与重建

从[构建说明](BUILDING.md)开始。该文档区分三个层次：

1. **干净源码检出验证**：安装公开 Python 依赖，运行源码检查和自有微型数据测试；无需游戏或旧构建缓存。
2. **最新桌面封装重建**：从当前源码编译 Configure.exe、Game.exe 和 DesktopRuntime.dll；完整补丁打包另需明确的摘要锁定外部输入。
3. **原生与资源管线**：原版资源、字体、生成头和本地验收输入分别准备；不把忽略目录视为克隆后自带内容。

当前完整本地包名为 `MagnaCarta-zh-CN-v1.0-unified-uac-20261026.zip`。其外部构建输入尚未发布，因此**当前 GitHub 源码本身不是完整玩家包，也不是无需额外输入的一键完整重建包**。

最新封装用法：Configure.exe 修改游戏根目录的 `enhancements.json`，Game.exe 启动；日志保存在当前用户缓存目录。旧用户目录设置和旧 config 设置仅用于首次迁移，已有根目录设置优先。详细行为见[编译式桌面入口](docs/COMPILED_DESKTOP_RELEASE.md)。

## 仓库内容

| 目录 | 内容 |
| --- | --- |
| `locales/zh-CN/` | 源绑定译文、术语、语言配置与美术源素材 |
| `tools/` | 提取、校验、字体、资源重建与打包工具 |
| `src/` | 原生模块、桌面入口及配置界面源码 |
| `patches/`、`assets/` | 补丁计划、项目素材与来源/许可记录 |
| `tests/` | 自动化回归、自有微型样本及可选原生资源回放 |
| `docs/` | 格式、逆向、专项验证与历史构建记录 |

`build/`、`dist/`、`out/`、`runtime/`、`game/` 为本地输入或生成目录，不提交完整游戏、存档、缓存或构建产物。

## 文档入口

- [构建与依赖](BUILDING.md) · [贡献与版本管理](CONTRIBUTING.md)
- [翻译规范](TRANSLATING.md) · [术语表](GLOSSARY.md)
- [技术说明](TECHNICAL.md) · [文件格式](docs/FILE_FORMATS.md) · [技术陷阱](docs/PITFALLS.md)
- [全文管线](docs/FULL_TRANSLATION_PIPELINE.md) · [媒体管线](docs/MEDIA_LOCALIZATION.md)
- [已知问题与历史证据](docs/KNOWN_ISSUES.md) · [历史构建记录](docs/BUILD_HISTORY.md)

历史研究工具与回归保留，避免丢失格式、失败路径和修复依据；历史候选命令不作为当前默认操作。新增语言使用独立 locale 数据，不重写通用工具。

## 许可与致谢

项目使用独立仓库与历史。英文汉化工具参考 [Nejuf/magnacarta](https://github.com/Nejuf/magnacarta)，署名 Talbain（Lakuuna）、Sobodash、Nejuf；固定来源及验证范围见[运行调查](docs/RUNTIME_RESEARCH.md)。

原创代码与文档采用 MIT，原创译文采用 CC BY-SA 4.0；字体和第三方组件遵循各自许可。原始游戏文本与商业资源不属于上述原创授权。详见[许可与来源](LICENSING.md)及[译文许可](LICENSE-translations.md)。
