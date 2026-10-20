# 图片、模块与视频文字候选

2026-10-20 全量图片复核已更新单图/组图计划：161 单图、15 组 43 块，共 204 份。
圆角、完整跨块标题、底板/渐变、名牌和计数标记的修正已整合共享 Play；12 份已接受
的 4K 标题背景单独锁定，不使用旧低清组图输出覆盖。详见
[422 份图片结构审计与单项回滚](IMAGE_INTEGRITY_REPAIR.md)。以下数量为历史阶段记录。

所有命令只读取原始文件，生成新的独立输出目录；不启动游戏、商业驱动或播放器，不修改安装目录、注册表和存档。原资源、字体、DLL、视频和工具留在忽略的build目录，不提交完整商业资产。

## 重建

```powershell
python tools/build_image_text.py --source SOURCE_GAME --plans locales/zh-CN/image-text-plans.json --font OUTLINE --font-sha256 FONT_SHA --output NEW_IMAGES
python tools/build_image_groups.py --source SOURCE_GAME --plans locales/zh-CN/image-group-plans.json --font OUTLINE --font-sha256 FONT_SHA --output NEW_IMAGE_GROUPS
python tools/patch_text_domains.py --source SOURCE_GAME/MCAlpha.dll --plans locales/zh-CN/text-domain-plans.json --font-package COMPLETE_FONT_PACKAGE --output NEW_MODULE
python tools/build_video_text.py --source SOURCE_GAME --plans locales/zh-CN/video-text-plans.json --font OUTLINE --font-sha256 FONT_SHA --encoder PORTABLE_BINK1_ENCODER --encoder-sha256 ENCODER_SHA --output NEW_VIDEOS
```

Python依赖Pillow、fontTools、pefile；视频另需FFmpeg/ffprobe和显式提供、锁定摘要的Bink1压缩器。构建器不下载、安装或捆绑这些组件。输出必须是新的独立目录。模块原生字槽必须配套同一完整字库映射，不能混用旧批次。

源摘要、人工转录/显示域依据、遮罩和排版参数参与构建。未知源版本、重复目标、遮罩重叠、输入漂移、字体缺字、越界与容量溢出拒绝发布。单图与组图在最终发布前完成全部输入校验；视频的中间压缩文件会留在失败目录，只有存在完整build.json且全部解码通过才是成功候选。

## 已验证

- 单图170份、248处目标文字，覆盖菜单、存取档、音量、技能、装备、人物头像、战斗反馈等。跨页尾字由同组译文承担，资源ID不合并。
- 9组26个tile包含读取面板、武器成长、出战成员标题、第二套开篇誓言六行，以及标题、载入、Game over艺术图，共15处目标文字。显式坐标拼合、整句排版、裁回原tile；原包装、头、尺寸、尾部及遮罩外像素保留。静态相邻关系不是运行时位置证明。
- 13个已确定原生字库显示域字段在原槽内回写，格式参数及顺序保留。RT_DIALOG 101/1042的标题和28个控件使用UTF-16；32个控件的ID、类、位置、样式、字体及附加载荷保留。可执行节逐字节不变。
- 两段BMC覆盖开场词典/标题及Game over，共5,267帧。原压缩音频包、轨道参数和时间基保留，全部离线解码。双行字幕分开排版，并检测底部/水平安全区。
- 18段原始BIKi成员解析/重建逐字节一致；受控音视频样本换视频后，音频包与解码PCM一致。PAK成员支持原分配长度、后续成员偏移及未选成员保护；真实片尾PAK尚未回写。

## 未完成范围

`all_game_text_complete=false`、`deployed=false`、`game_started=false`保持明确。离线通过不等于游戏内字体、透明混合、缩放、tile位置、字幕时序及旧存档显示通过。现有启动隔离工具仍锁定原始MCAlpha摘要，不绕过入口校验接入本模块候选。

当前离线候选已结合并打包，仍待游戏内实际观察tile位置、字号/缩放、系统消息、字幕时序和稳定性。开发人员名单及旧存档名字按直接用户决定排除，名单视频档案整份原样保留。作者姓名、品牌、版权声明与标准属性缩写不自动删除或冒充原创。

低清小号英文及装饰书页/符号共24份资源，按直接用户回复“不做就行。”明确保留原图。源摘要和决策保存在`locales/zh-CN/image-text-preserve.json`，不计作译文，也不再列为待转录素材；回归保证它们不进入单图/组图修改清单。

## 实际复核修正

- 旧清单把0180当作Status，实际为红色小标记；状态按钮位于0181起，0180不改。
- 灰白笔画筛选留下彩色抗锯齿残影；经遮罩复核改为保留零alpha的擦除，再检查预览。
- 0409说明遮罩与标题发生重叠，门禁实际拒绝输出，修正后重建。
- 0171确认文字、0261标签末尾、0278/0279英文与0262竖排文字经逐图复核后补齐遮罩/目标。
- 首次视频双行字幕被底边裁切；最终逐行排版、显式安全区与600字重字体实例。失败预览不作为最终候选。

证据只证明记录中的输入和版本。候选及回滚副本不是完整发行包。

艺术图采用透明叠加中文标题，不擦除原英文品牌、原文或复杂背景；文字之外的像素逐字节保留。该双语呈现方式与一般菜单的替换式回写分开记录。

系统提示已有源绑定Unicode/IAT候选，9字段6消息及自建导入表拦截实测见[SYSTEM_MESSAGES.md](SYSTEM_MESSAGES.md)。当前版本仍绑定原MCAlpha，全文候选组装与私有字槽动态参数转换另计。

最新范围与全文结合：旧存档名字、开发人员名单明确不处理；名单PAK整份保护原字节。第一套誓言可读tile、候选模块和1,898字形系统参数转换已进入增量包；完整结合、安装/回滚及未执行的游戏QA见LOCALE_PACKAGE.md。

开头SOFTMAX Logo按直接用户决定整段原样保留，MOV/0023.BMC不进入补丁清单；曾含Logo译文的未发布候选已撤回。

实际截图中的旧字描边残痕已按完整清理轮廓修正；202份图像复核、985→0像素对照、源保护和独立回滚见[IMAGE_RESIDUE_FIX.md](IMAGE_RESIDUE_FIX.md)。不将静态清理通过称作完整游戏内验收。

主界面改为两行银白艺术字及横线，菜单提高对比度；前景英文撤换、尾字跨tile修复、源保护及可复现素材见[TITLE_ARTWORK.md](TITLE_ARTWORK.md)。当前图像203份、完整增量635资源，实际新标题显示待观察。
