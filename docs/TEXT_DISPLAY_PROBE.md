# 最小中文显示探针：资源回写

## 范围与状态

状态：资源定位、版本锁定、实际结构往返、原版字形覆盖、差异限制和隔离回滚已静态验证；Status 武器栏完整“中文”字符串已取得实际截图及测试确认。Item 列表与其他字体/场景分别验收仍待完成。

此前 [字形探针](GLYPH_DISPLAY_PROBE.md) 在武器名中显示了 `中`。本阶段不再替换韩文字形，而将同一武器的候选显示名资源写入明确的 `中文` 两字。字体保持原版六字库。该字符串是诊断标记，不是正式武器译名，不计入术语表或翻译进度。

## 定位证据

- 截图中的原武器名为 `소울 블레이드`。只读扫描在 `Sgi/0000.sgi` 找到对应完整 CP949 字节，位于 ordinal 0、ID 5 的名称位置，绝对文件偏移 12。
- `Itm/0000.itm` 不包含该完整武器名；其中另有包含“블레이드”的装备名，不据词汇相似度合并。
- SGI 样本为 14,276 字节，87 条 164 字节记录，头为 `5700000010000000`。原始 SHA-256：`13adf18b88d94bcddd1c444e4ce11175c1a0390396ee475ccae94a17f62fa0a8`。
- 名称字段线索参考 Nejuf/magnacarta 的 `sgi2txt.rb`、`txt2sgi.rb`，固定 commit `9ce77cace0d717f5ad75bb2910517802e55932c8`。独立 Python 实现验证结构和原样往返，不执行上游重建器，不复制其硬编码头部或整体统计字段重写方式。
- 已验证：87 条记录原样往返字节一致；名称可在记录内偏移 4 的 100 字节候选区找到零终止符。ID、头部、其余 86 条记录及当前记录的其他字节保持不变。
- 高置信推断：该名称是截图中装备显示名的资源来源。资源实际读取路径、显示名是否缓存到存档及运行时最大名称长度仍待确认，不将结构匹配当成游戏验收。

## 最小修改

旧名 13 字节及一个零终止符占用偏移 `[12,26)`。仅在这段写入 `F1 E9 D9 FE`（CP949 的 `中文`），剩余原字符串区域置零；不扩大到整个 100 字节候选字段。两套原版 Chi 字库均具有对应有效字形，宽度与字节消费静态核对通过。

修改后的 SHA-256：`2da691ceb5a3faae1b5c264be5a66a13178073ce44280beecf3a347a981d7f4f`。不修改 ID 5、记录顺序、武器属性、资源引用、程序、字库、图形配置或存档。

通用工具位于 `tools/resource_sgi.py`、`tools/build_text_probe.py`；目标语言数据位于 `locales/zh-CN/probes/text-display.json`。仅支持当前版本的受控探针，不开放任意长度 SGI 名称导入或全量翻译。

## 可重复构建与恢复

Python 3.12 以上，无新增依赖。SOURCE 为原字库、已验证运行配置的独立基线；输出目录必须为新目录。

```powershell
python tools/build_text_probe.py build --source SOURCE --spec locales/zh-CN/probes/text-display.json --output build/text-probe
python tools/prepare_workspace.py --source SOURCE --target build/runtime/text-probe-game --manifest build/text-probe-evidence/workspace-copy.json
python tools/build_text_probe.py apply --package build/text-probe --workspace build/runtime/text-probe-game
python tools/build_text_probe.py verify --package build/text-probe --workspace build/runtime/text-probe-game
python tools/build_text_probe.py restore --package build/text-probe --workspace build/runtime/text-probe-game
```

实际来源为 `build/runtime/render1080-game`，不是旧字形探针副本。六份字库及程序哈希锁定，不接受仍存在韩文字形覆盖的输入。原安装不作为写入目标。所有商业输入、输出、备份及运行副本只保留在忽略的 build/ 下。

包内保存原始/修改 SGI、版本与定位元数据。应用、验证、恢复重新核对程序、字库、资源哈希、记录 ID、旧名称及候选差异；即使修改包内哈希，越界改动仍拒绝。恢复前有内容漂移时不覆盖；普通部分复制异常恢复操作前文件和标记，持续不可写或断电使用完整基线重建。

## 手动验收

独立入口：`build/runtime/LaunchTextProbe.cmd`，创建入口不执行入口。入口先校验探针，再使用既有隔离启动、FocusGuard、异常记录与只读窗口观察。

1. 手动运行新入口，读取此前存档，不覆盖存档。
2. 打开 Status 的武器栏，再打开 Item 的装备列表；预计原武器名位置完整显示 `中文`，而非韩文混入单字。
3. 核对两字是否完整、间距正常、无裁切或残影；其余名称与标签应保持原文，提供两个界面截图。
4. 核对场景模型与 Alt+Tab 没有回归，正常退出。
5. 名称未变化时记录未命中；不扩大替换范围，继续确认 SGI 加载及存档缓存路径。

此次只验收装备名，不能据此宣布对话、全体 UI、完整简体字覆盖或大规模翻译条件已满足。无需再次遍历所有设置菜单。

## 自动检查

原有 103 项通过，新增 16 项覆盖 SGI 往返、字段保护、ID/原字节不匹配、越界、控制字节、编码、字库覆盖、旧字形覆盖拒绝、构建一致性、应用/恢复、包内越界篡改、漂移及部分复制异常。合计 119 项通过。

实际副本完整清单核对仅允许 `Sgi/0000.sgi` 与探针标记两处差异；隔离回滚恢复原版 SGI，运行探针副本保持修改。静态检查命令均不启动游戏。

## 首轮资源回写验收

2026-10-12 截图确认 Status 武器名称区域完整显示 `中文`，没有可见的缺字或残余韩文尾部。会话 `session-20261012-163140-743` 核对副本驱动加载、PID 45920、自然退出码 0。日志只读核对，不重新运行游戏。

该结果确认本处 SGI 名称候选的实际加载、CP949 双字节消费与中文字形绘制链路，推翻“此存档完全不读取该名称资源”的候选假设；不能据单一截图确定存档内部结构或所有路径。Item 列表未提供本轮截图，对话和两字体组也不据此扩展验收。

接续 [跨作品术语对照](SERIES_TERMS_AUDIT.md) 与结构化名称 catalog。诊断标记保持在独立测试副本，不写为正式译名。
