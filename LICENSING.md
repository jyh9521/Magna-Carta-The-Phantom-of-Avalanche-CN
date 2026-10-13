# 许可与来源

仓库使用独立历史。项目原创代码与文档采用 LICENSE 中的 MIT 许可证，单独声明优先。
原创译文见 LICENSE-translations.md。原始文本和商业资源的权利不因提取、修改或生成而转移。
英文工具参考为 Nejuf/magnacarta，版本和署名见运行调查，其 BSD-2-Clause 不自动覆盖商业游戏驱动。
字体、图形层、输入库与工具分别记录来源、版本、许可和再分发条件，保留署名。
dgVoodoo2 不作为开源组件描述，其作者条款单独适用；未经具体许可核实的组件不打包。
优先分发源码、译文、补丁和增量变换数据，不分发完整商业 EXE、DLL、档案、媒体或专有字体。
参考术语表只读，继承译名记录来源和 commit。

字形构建参考 Noto Sans SC 的固定 Google/fonts 来源，来源锁见 assets/font-sources/noto-sans-sc.json，完整SIL Open Font License 1.1见 assets/licenses/NotoSansSC-OFL.txt。未提交轮廓字体或商业字库；衍生字体采用 Locale Glyph Overlay 名称并保留来源许可与版权声明，不使用保留字体名称声明原创。

已撤回的图形候选使用 DDrawCompat v0.7.1，固定源码 commit、0BSD 许可、发行资产 SHA-256 和使用范围见 docs/GRAPHICS_CANDIDATE.md。第三方 DLL 仅置于忽略的本地研究与运行副本目录，当前不加入仓库或玩家发行包。
后续独立试验使用 dgVoodoo2 2.87.5，作者专有条款、来源和固定哈希见 docs/D3D11_CANDIDATE.md；未纳入项目 MIT，也未作为通用多应用框架捆绑或公开发行。

未更新驱动对照读取 Nejuf/magnacarta 固定 commit 下的 Drv_unpatched，来源与哈希见 docs/UNPATCHED_DRIVER_TRIAL.md。商业游戏驱动不因上游仓库包含文件而视为本项目 MIT 内容；候选仅保存于忽略的本地研究和测试副本，不提交或再分发。

Bink1离线压缩研究使用RAD官方RADTools.7z（https://www.radgametools.com/bnkdown.htm），归档SHA1 dace86bb00b755fea8a0002538fad79e3faebdd6，1,101,490字节；2026.09工具签名为Epic Games Inc.且验证有效，radvideo64.exe SHA256 b405986b11fdc214033bcf385f4c7c3d126a9899815391b96af955618139a1ce。只从归档提取本地压缩器，未运行安装器，不捆绑或再分发工具及商业视频。命令参数依据官方帮助与FAQ（https://www.radgametools.com/binkhlp2.htm，https://www.radgametools.com/binkfaq.htm），/V100选择Bink1、/#不等待Done窗口。第三方工具不属于项目MIT。字幕字体实例改名Locale Video Overlay，并保留来源版权/OFL记录。
