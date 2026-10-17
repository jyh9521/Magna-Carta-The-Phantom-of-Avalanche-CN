# 《真名法典：冰之魅影》本地化工程 / Magna Carta: The Phantom of Avalanche Localization

## 项目简介

初代 PC 版《真名法典：冰之魅影》（마그나카르타: 눈사태의 망령）的简体中文汉化与现代 Windows 兼容性工程。

当前目标语言为简体中文 `zh-CN`。仓库保存结构化译文、术语、资源提取与重建工具，以及显示、输入等增强模块；语言数据与通用工具分离，保留后续适配其他语言的基础。

## 支持版本与当前状态

当前针对项目已记录指纹的 PC 安装样本开发，未知版本会被校验工具拒绝。样本与所提供 1.04 补丁的差异见[版本调查](docs/SAMPLE_AUDIT.md)，不将所有标为 1.04 的安装视为相同版本。

- **文本与字体**：当前结构目录共 4,137 个字段，包含 4,091 条译文和 46 条明确保留项；427 份结构资源与两套原生字库已完成重建、逆解码及重复构建验证。
- **图片、视频与系统提示**：已有中文候选并纳入增量构建；SOFTMAX 开头 Logo、开发人员名单、指定保留图及旧存档名字不作汉化或改写。
- **兼容性与增强**：已有共享运行目录、图形兼容层、4K/宽屏、动作与手柄、自由视角、地图等候选。各功能的验收状态不同，测试通过不等于全部场景可用。
- **发布状态**：已建立统一玩家测试补丁包构建流程，尚非完成整体验收的正式汉化发行版。

结构目录完成不等于全文汉化完成，离线重建和自动测试也不代替完整游玩。详细范围见[全文候选与增量包](docs/LOCALE_PACKAGE.md)，当前限制见[已知问题](docs/KNOWN_ISSUES.md)。

## 下载与使用

仓库提供源码、译文和构建工具，不包含游戏本体，也不包含本机 `runtime/` 运行目录。测试包说明见[统一玩家测试补丁包](docs/PLAYER_TEST_PACKAGE.md)。

### 测试包

使用已构建测试包中的 `Install.cmd`，选择匹配的原版目录与新的目标目录；安装工具校验原版后，在新副本中生成补丁资源，不覆盖原安装。

安装后，从新副本根目录运行 `Configure.cmd` 调整增强设置，使用 `Play.cmd` 启动。其他 `Play-*.cmd` 是独立候选入口，不代表相应功能已合入默认配置。校验、恢复原版资源与验收边界见[测试包说明](docs/PLAYER_TEST_PACKAGE.md)。

### 本地开发运行目录

已准备好的共享运行目录使用 `runtime/Configure.cmd` 与 `runtime/Play.cmd`，各入口共用一份游戏数据与存档。历史 `build/*-game` 入口不再作为当前使用入口，目录准备与原生重建见[共享运行布局](docs/SHARED_RUNTIME_LAYOUT.md)。

## 从源码重建

依赖、版本校验、译文检查、字体生成、资源重建及原生模块编译见[构建说明](BUILDING.md)。原版游戏和字体等输入须按文档单独准备；克隆仓库并不包含这些输入。

在已有、摘要校验通过的共享运行目录基础上，构建统一测试包：

```powershell
python tools/build_player_test_bundle.py --source ORIGINAL_GAME --runtime runtime --output dist/NEW_TEST_PACKAGE
```

`ORIGINAL_GAME` 指匹配的原版目录，`NEW_TEST_PACKAGE` 须为新的输出目录。该命令打包已有候选，不替代前置资源与模块构建。生成物保存在 `build/`、`dist/` 或 `out/`，不进入源码仓库。

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
