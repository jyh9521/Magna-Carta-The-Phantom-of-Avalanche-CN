# 图片边框、拼接标题与背景修复

## 已验证（2026-10-20）

信息框顶部方角并非原版设计。CD1 的 `BGR/0163.BGR`、`0164.BGR` 保留透明圆角，
原题头 `INFORMATION` 跨两块纹理拼接。旧候选把两块分别写成“信息”，并把清理框
内的透明圆角、黑色边沿一起填成橙色，造成两个标题和两端凸出。

全量读取 CD1 `/SETUP/BGR`，按 1.04 补丁中的同名文件覆盖，得到 **422 份 BGR**。
与共享运行目录逐份比较文件集合、来源摘要、结构、包装、头、尾、尺寸、全部 RGBA
差异及批准范围；原版镜像不挂载、不解包整套游戏。

- 204 份图片属于当前文字计划：161 单图、15 组 43 块纹理。
- 12 份已接受的 4K 标题背景按完整目标摘要、尺寸及原版摘要核验，不让旧低清
  组图输出覆盖；其中 6 份与文字组图资源标识重合。
- 其余 212 份 BGR 与原始输入一致，包括此前决定保留的 24 份低清/装饰图。
- 原图/旧候选全量预览复核，修正后的 101 份变化图另作同坐标前后对照；
  五组信息框按完整 512 像素拼合检查，不把单块的半个标题误判为缺字。

这是全部 BGR 的静态审计和图片文字改动检查，不等于所有游戏状态的动态画面验收；
TXRS 场景纹理、视频帧和未知 UI 调用路径不据此宣称已完成视觉验收。

## 修改

| 资源 | 问题与修正 |
|---|---|
| 0155–0164 | QUESTION、ANSWER、CAUTION、BATTLE ALERT、INFORMATION 是五个跨块标题，不是十个独立标签。各排版一次；删除“任务/问题”“答案/武器”等误拆，补齐 CAUTION 左半；恢复圆角和黑边 |
| 0084–0095 | 战斗按钮上沿铺平、下半挖空及旧字下伸部。以干净行重建背景，同源上角镜像恢复下角；绿灯、左轮廓保持源像素 |
| 0181–0190、0265–0276、0294–0297、0393–0394 | 菜单底板、装饰条和绿线被宽泛清理/错误采样破坏。清理轮廓与排版框分离，保留干净上沿，恢复绿线，全色背景重建消除彩色抗锯齿残痕；文字保留右边距 |
| 0219–0228、0410–0411 | 横向透明渐变被行采样变成矩形色块。改用干净的列向模板，并以源绑定的干净绿线恢复被字母下伸部遮住的部分 |
| 0284–0290、0423–0424 | 翻页底板被清空，排序文字超出原 91×21 可视跨度；恢复黑底和源 alpha 圆角，按真实区域排版 |
| 0333–0348 | HP 名牌锚点取到边框/透明区，产生黑洞、长条和缺角；改用干净行，收窄旧字清理，保护指示孔、外轮廓 |
| 0215–0218、0431–0436 | 连击/判定文字越出背景、采样黑条和孤立渐变块；修正真实宽度、干净模板，保留原渐变下部。0436 上半光晕从本图无字的 70–121 行镜像重建，与下半衔接，主提示/说明分开排版，不生成替代图片 |
| 0427–0430 | 原生数字/橙色计数标记被误删，译文又重复数字；保护数字和三个蓄力格，文字只写“破击蓄力/层就绪”，清除完整旧 OVERCRASH 上沿 |

来源、坐标、捐赠图摘要及保护区均为语言数据，通用构建器不包含中文资源编号分支。
旧 EA 徽标、音效栏线、正立竖排、字幕、C 字模、原生 Loading 和 4K 标题背景保留。

## 构建器与回归

`build_image_text.render` 的显式 `erase_rects_xyxy` 曾绕过 `erase_mode`，与隐式清理不同。
透明圆角与彩色边框的两个最小回归在旧代码下均失败（退出 1），修正后通过。

- 两条清理路径共享擦除策略；圆角底板可保留源 alpha，不把半透明边缘变成不透明。
- `background_repairs` 仅在批准清理区内执行精确 RGBA 拷贝、镜像或定向采样；
  跨图模板绑定显式资源和 SHA-256，来源一起检查漂移。
- 拷贝不重复 alpha 混合；新字覆盖保护区则拒绝发布，不靠裁字通过。
- 中性颜色筛选会留下彩色底板上的混合抗锯齿。本轮相关菜单采用收窄轮廓后的全色
  背景重建，`neutral_ink` 仅作为明确选择的通用策略保留。

源字体来源及摘要见 `assets/font-sources/noto-sans-sc.json`。重建只提取 204 份原 BGR，
不复制其它游戏数据。以下输出和报告须为新路径；`OUTLINE` 是该固定字体的实际路径。

```powershell
$e='build/NEW_IMAGE_EVIDENCE'
python tools/audit_image_resources.py --iso 'game/Magna Carta CD 1.iso' --patch game/MCV104a.exe --workspace runtime/data --plans locales/zh-CN/image-text-plans.json --groups locales/zh-CN/image-group-plans.json --checks locales/zh-CN/image-integrity-checks.json --report "$e/source-audit.json" --extract-to "$e/source"
python tools/build_image_text.py --source "$e/source" --plans locales/zh-CN/image-text-plans.json --font OUTLINE --font-sha256 a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da --output "$e/images"
python tools/build_image_groups.py --source "$e/source" --plans locales/zh-CN/image-group-plans.json --font OUTLINE --font-sha256 a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da --output "$e/groups"
python tools/audit_image_resources.py --iso 'game/Magna Carta CD 1.iso' --patch game/MCV104a.exe --workspace runtime/data --plans locales/zh-CN/image-text-plans.json --groups locales/zh-CN/image-group-plans.json --checks locales/zh-CN/image-integrity-checks.json --candidates "$e/images" "$e/groups" --retain-approved --report "$e/candidate-audit.json"
```

原版/4K 图片摘要不匹配时中止，不自动接受未知版本。未改 BGR 逐字节受保护；
原四项旧字残痕仍为 0，但这四项不能替代全量检查。

## 当前整合、基线及回滚

入口仍为 `runtime/Play.cmd`，仅替换 **101 份 BGR 和 runtime.json 中对应摘要**。
脚本、全部运行 DLL、字体、设置、INI 和存档保持原字节，不另设玩家测试入口。
事务取得共享入口互斥锁，整批预检摘要，原子写入、读回，失败恢复原状态。

原始 0159 从 CD 安装保留只读属性；首次整合在此被拒绝，回查 422 份图片均已恢复
旧摘要。更新器已增加保留属性的替换及只读文件回归，成功整合/回滚均保持原属性。

事务：`build/image-integrity-evidence/integration-verified/`，`original/` 只保留本轮变化
文件。旧基线、字体/Loading 事务、存档、设置和最新统一测试 ZIP 保留。撤销本轮时
先回滚图片，再按需要撤销更早的字体/Loading 事务：

```powershell
python tools/deploy_image_runtime.py rollback --record build/image-integrity-evidence/integration-verified
```

可复跑的三态验证，默认不回滚真实运行目录：

```powershell
python tools/check_image_repair.py baseline
python tools/check_image_repair.py modified
python tools/check_image_repair.py rollback
```

三条分别输出 `IMAGE_REPAIR_BASELINE/MODIFIED/ROLLBACK PASS`，图片数 422；旧基线
176 个静态检查违规、修正后 0、隔离回滚重现 176，命令均退出 0。176 是多项检查的
违规条目数，不是错误图片数。回滚仅在最小文件夹具调用真实 `ROLLBACK.sh`，核对
102 个文件前态摘要/属性，保护自有存档/设置哨兵；真实运行目录始终保留修正状态。

配置化 `Start.ps1 -VerifyOnly` 通过，仍选择 scaled-font、楼梯与 GUI 守卫。
完整回归、源保护和回滚属于离线证明，游戏未由本轮启动。手动验收沿用正常 Play，
查看五类信息框、战斗命令亮暗态、状态/物品/存档菜单、翻页和连击反馈，留意动态
缩放、渐显和接缝。新游戏画面仍待玩家观察。
