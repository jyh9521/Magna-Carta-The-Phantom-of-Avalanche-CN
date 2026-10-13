# 贴图文字残痕清理

实际状态与存档页面截图显示旧字描边残留：身体部位标签上沿和存档提示上沿留下黑白碎片。问题来源是旧字清理范围与目标排版框混用，未覆盖旧字完整描边；部分源背景锚点还取到字形/边框或不透明黑像素。

当前单图170份248条译文和组图10组32tile共202资源完成离线复核。目标排版框与原文擦除轮廓分别保存；所有清理轮廓先处理，再统一绘制译文，邻接清理不会擦掉已绘制中文。源摘要、字体覆盖、布局和清理范围、包装/头/尾/尺寸及全部范围外RGBA逐像素受保护。透明文字资产按alpha合成复核，不将隐藏RGB误当实际残痕。

身体两页、保存/读取两页有独立检查配方`locales/zh-CN/image-cleanup-checks.json`。`tools/check_image_residue.py`只读检查目标字形之外的旧描边条带；原候选985个残留像素，修正后0。全部图片另有预览复核；这四处像素配方不冒充全部场景自动视觉验收。

开篇两套誓言已清理外侧模糊旧字重复带，六行中文内容和tile标识不变。原画、UI栏线、字库、结构文本、免CD补丁与现代化图形配置不改。开头SOFTMAX Logo、人员名单、旧存档名称和24份明确保留图继续保持原样。

`tools/update_image_candidate.py`仅升级带候选标记的独立副本。对202资源全部预检，旧/新集合必须一致，目标必须匹配旧构建摘要；写入前保存可核对备份，回滚先验证全部目标及备份。不会启动游戏、复制覆盖存档或修改原安装。

版本锁定与可复现回建：

```powershell
python tools/build_image_text.py --source SOURCE --plans locales/zh-CN/image-text-plans.json --font OUTLINE --font-sha256 FONT_SHA --output NEW_IMAGES
python tools/build_image_groups.py --source SOURCE --plans locales/zh-CN/image-group-plans.json --font OUTLINE --font-sha256 FONT_SHA --output NEW_GROUPS
python tools/check_image_residue.py --workspace NEW_IMAGES --plans locales/zh-CN/image-cleanup-checks.json
python tools/update_image_candidate.py apply --workspace LOCALE_COPY --old-packages OLD_IMAGES OLD_GROUPS --new-packages NEW_IMAGES NEW_GROUPS --backup NEW_BACKUP
python tools/update_image_candidate.py rollback --workspace INDEPENDENT_ROLLBACK_COPY --backup NEW_BACKUP
```

本轮没有启动游戏。用户反馈候选已可进入实际场景；若已卸载镜像并取出实体盘，该反馈支持无盘进入场景的首轮验收，不覆盖后续剧情、音乐、语音和视频。介质状态未独立记录，完整无盘运行不据此宣称全部通过。清理后的游戏内显示仍需后续观察。

317项自动测试通过。202资源完整预检后有81份实际字节变化，已更新现有独立汉化/免CD副本；其余121份保留已有字节。独立回滚202份资源恢复原候选，985像素失败状态可复现；待复测副本仍保留清理后的资源。
