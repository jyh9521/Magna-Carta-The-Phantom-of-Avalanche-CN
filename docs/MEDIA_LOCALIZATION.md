# 图片、模块与视频文字候选

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

剩余范围：第一套誓言tile实际布局；片尾字幕；9处MessageBoxA诊断；旧存档人物名显示适配；完整候选组装及游戏内验收。作者姓名、品牌、版权声明与标准属性缩写不自动删除或冒充原创。

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
