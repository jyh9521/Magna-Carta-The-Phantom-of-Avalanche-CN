# 真名法典：冰之魅影 简体中文汉化

初代 PC 版《Magna Carta: The Phantom of Avalanche》的简体中文汉化与现代 Windows 兼容性工程。

当前本机运行布局为[单份游戏数据＋独立模块和配置](docs/SHARED_RUNTIME_LAYOUT.md)。
统一入口是 `runtime/Play.cmd`，设置入口是 `runtime/Configure.cmd`；历史 `build/*-game` 测试入口已由新布局取代。

## 当前状态

已补齐当前提取目录的 4,137 个结构字段：4,091 条译文、46 条明确保留的空值、测试或内部对象字段。427 份资源与两套字库已在独立目录完成重建、逆解码及重复构建验证。
图片文字、视频烧录文字和系统消息等显示域仍未完成，结构目录完成不等于全文汉化完成；目前没有玩家发行包。构建范围与后续缺口见 [全文管线](docs/FULL_TRANSLATION_PIPELINE.md)。

首轮结果见 [样本与启动错误调查](docs/SAMPLE_AUDIT.md)。

## 文档

- [技术说明](TECHNICAL.md)
- [技术路线](docs/MODERNIZATION_ROADMAP.md)
- [运行调查](docs/RUNTIME_RESEARCH.md)
- [副本启动隔离](docs/RUNTIME_ISOLATION.md)
- [验收清单](docs/RUNTIME_TESTING.md)
- [构建说明](BUILDING.md)
- [翻译规范](TRANSLATING.md)
- [贡献与版本管理](CONTRIBUTING.md)
- [许可与来源](LICENSING.md)

## 上游

本项目使用独立仓库与独立提交历史。
英文汉化工具参考来自 [Nejuf/magnacarta](https://github.com/Nejuf/magnacarta)，署名 Talbain（Lakuuna）、Sobodash、Nejuf。来源版本与验证范围见运行调查。
原始游戏与商业资源归原权利人所有，不发布完整原版游戏文件。
