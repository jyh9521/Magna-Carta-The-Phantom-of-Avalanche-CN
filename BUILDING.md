# 构建说明

## 高级显示第二轮运行工具

既有Win32原生构建配置增加 `wide_ui_fixture`、`menu_visibility_fixture`、`motion60_fixture`；继续使用原字体覆盖与系统消息生成头文件，不重新生成或更改翻译资源。`workspace_profile`增加三个源文件；`workspace_launcher`及准备脚本增加Asura.dll全文件源锁。CMake配置和原有字体/系统消息生成流程仍按后文执行。

在已配置的Win32构建目录中，构建 `workspace_profile workspace_launcher wide_ui_fixture menu_visibility_fixture motion60_fixture advanced_display_fixture`，逐个运行四个fixture后运行Python完整测试。所有夹具使用自有映像/调用桩，不启动商业游戏。

首次副本仍使用 `tools/prepare_advanced_trial.py`。对现有、哈希匹配的独立验收副本更新自有运行工具：

```powershell
python tools/refresh_advanced_trial.py --workspace build/advanced-display-game --native build/advanced-display-native/Release
```

更新器持有与启动入口相同的互斥锁，拒绝正在运行的同目录游戏、未知哈希和改动的启动脚本。先备份四个旧运行文件及摘要，再更新DLL、launcher、清单和启动脚本。`Restore-previous.cmd`在退出游戏后恢复上一轮自有运行工具，未知状态拒绝，存档不覆盖；`Rollback.cmd`仅恢复基准INI。更新前后完整游戏模块磁盘字节及资源保持原样。

字形构建的固定来源、依赖和确定性映射见 [NATIVE_GLYPH_MAPPING.md](docs/NATIVE_GLYPH_MAPPING.md)；文本框步长模块的版本、独立夹具和只读检查见 [TEXT_LAYOUT_COMPATIBILITY.md](docs/TEXT_LAYOUT_COMPATIBILITY.md)。全量回写尚未完成，不在此阶段提供游戏运行验收指令。

已建立隔离复制、只读调查、输入比对和 FPB 原样往返工具；中文回写、字体生成及发布构建入口尚未完成，没有可安装汉化包。样本哈希见 docs/SAMPLE_AUDIT.md。

最小中文显示的字形层诊断构建、独立副本及恢复命令见 [显示探针](docs/GLYPH_DISPLAY_PROBE.md)。仅修改四个字形槽，不构成完整中文回写方案，游戏验收待执行。

下一阶段 [资源显示探针](docs/TEXT_DISPLAY_PROBE.md) 仅回写一个 SGI 武器名称为诊断字符串，原版六字库不变。已有受控回写入口，但完整中文导入、字体生成和发行构建仍未完成。

Status 已取得完整中文字符串的实际截图。SGI 名称 catalog、参考术语表版本锁定及跨作品一致性检查命令见 [术语对照](docs/SERIES_TERMS_AUDIT.md)，此阶段只读取原始资源和参考文件，不执行游戏。

全量目录清点、统一文本 catalog、图片文字覆盖及最终统一测试流程见 [全文管线](docs/FULL_TRANSLATION_PIPELINE.md)。当前结构提取 3,992 字段，不将未解析资源静默计为已完成。

预定流程：版本验证 → 提取 → 导入译文 → 控制符/编码校验 → 字体覆盖 → 重建 → 结构验证 → 游戏验收 → 增量发布。
原始文件保留只读基线，修改作用于副本；未知版本、预期字节不匹配或资源结构错误时停止。
生成产物使用 build/、dist/ 或 out/，不进入源码目录。

当前文档检查：安装 Python 3 后执行 `python tests/check_runtime_docs.py --expect modified`。此检查不证明游戏功能。
构建输入、来源、依赖和命令必须记录，不依赖私人目录或手工中间文件。发布前在干净检出重建，验证哈希、安装、卸载和回滚。
完整商业资源不进入仓库或发布包，第三方组件单独记录版本和许可。

## 样本调查命令

工具使用 Python 3.12 或更新版本；本轮验证版本为 3.12.14。安装研究依赖：

```powershell
python -m pip install -r tools/requirements-research.txt
python tools/prepare_workspace.py --source ORIGINAL_DIR --target build/runtime/game --manifest build/runtime/installation-manifest.json
python tools/inspect_game.py --workspace build/runtime/game --images game --report build/runtime/static-survey.json
python tools/compare_inputs.py --workspace build/runtime/game --iso "game/Magna Carta CD 4.iso" --patch game/MCV104a.exe --report build/runtime/input-comparison.json
python tools/resource_fpb.py --source build/runtime/game/Fpb --report build/runtime/fpb-roundtrip.json --catalog build/runtime/fpb-catalog.json
python -m unittest discover -s tests -p "test_*.py"
```

ORIGINAL_DIR 为只读来源路径；复制工具拒绝已有目标及嵌套源/目标，不覆盖已有实验。原文 catalog 与完整报告保持在忽略的 build/ 中。
上述命令不启动游戏、不应用补丁、不挂载镜像，也不写注册表。图形配置候选工具只生成独立文件，不能视为已生效设置。

## 原生启动隔离工具

Win32 构建、配置隔离测试与运行入口见 [副本启动隔离](docs/RUNTIME_ISOLATION.md)。该原生启动工具与前述只读调查命令分开：只读命令不启动进程，启动工具新建独立 HKCU 会话并启动副本，但不改写原安装登记或文件。

同一 CMake 工程新增 `graphics_probe.exe`，接受显式绝对路径的 DirectDraw DLL，使用非交互离屏目标测试深度遮挡，不启动游戏、不改变桌面模式。图形层安装、单层约束和恢复命令见 [图形候选](docs/GRAPHICS_CANDIDATE.md)。

完整异常采集和模拟回归见 [转储分析](docs/CRASH_ANALYSIS.md)。构建中的 `capture_core_fixture` 输出模拟 Core.dll，只用于自建故障样本，不复制到游戏副本；实际游戏 Core.dll 保持版本校验。非交互采集测试命令为 `python tests/check_exception_capture.py --bin build/runtime-native/Release --output build/capture-test`，输出目录须为新目录。


## 结构译文候选重建

完整原始catalog和coverage由只读提取生成，实际游戏资源不进入仓库。`TARGET_FILES`为UTF-8源绑定译文文件列表，收集工具按稳定ID生成字库输入；字库命令读取文件，不将全文放入命令行。

```powershell
python tools/translation_data.py --catalog CATALOG --translations TARGET_FILES --terms locales/zh-CN/terms.json --links locales/zh-CN/linked-text.json --require-complete --report NEW_REPORT
python tools/collect_translation_corpus.py --catalog CATALOG --translations TARGET_FILES --terms locales/zh-CN/terms.json --links locales/zh-CN/linked-text.json --output NEW_CORPUS_PACKAGE
python tools/build_font_overlay.py --source SOURCE_GAME/Font --font OUTLINE_FONT --font-sha256 LOCKED_FONT_SHA --translations NEW_CORPUS_PACKAGE/corpus.json --output NEW_FONT_PACKAGE
python tools/build_text_resources.py --source SOURCE_GAME --catalog CATALOG --coverage COVERAGE --translations TARGET_FILES --font-package NEW_FONT_PACKAGE --terms locales/zh-CN/terms.json --links locales/zh-CN/linked-text.json --output NEW_RESOURCE_PACKAGE
```

各占位路径指实际独立输入/输出。源游戏须匹配提取哈希，轮廓字体须匹配来源锁。输出目录必须不存在，字体包与资源输出分离。局部研究可显式追加`--allow-partial`，不得将该产物当作全文发布或直接覆盖运行副本。FPB控制标记、记录ID及数值属性不翻译；固定表回写追加`--fixed-decisions locales/zh-CN/fixed-field-decisions.json`，逐字段验证显示用途、源摘要、字段容量与格式化预算，支持ITM、ABI、SGI和CHA；图片写入仍未完成。详见[全文流程](docs/FULL_TRANSLATION_PIPELINE.md)。

## 图片、模块与视频文字

源绑定语言数据、独立候选重建命令和验证范围见 [媒体汉化](docs/MEDIA_LOCALIZATION.md)。图片与模块生成器保持通用，语言数据单独存放；不启动游戏。

系统提示Unicode候选新增9字段6消息、默认关闭的版本锁定MessageBoxA导入适配及自建无窗口回归；详见docs/SYSTEM_MESSAGES.md。未启动游戏、未部署到安装目录；完整候选结合及动态私有字槽参数仍待处理。

最新范围与全文结合：旧存档名字、开发人员名单明确不处理；名单PAK整份保护原字节。第一套誓言可读tile、候选模块和1,898字形系统参数转换已进入增量包；完整结合、安装/回滚及未执行的游戏QA见docs/LOCALE_PACKAGE.md。

开头SOFTMAX Logo按直接用户决定整段原样保留，MOV/0023.BMC不进入补丁清单；曾含Logo译文的未发布候选已撤回。

无盘启动候选：5字节源摘要锁定补丁、光驱检查模型、隔离入口及独立副本回滚见[DISC_GATE.md](docs/DISC_GATE.md)。游戏未启动，完整无盘游玩尚未验收；未挂载镜像或修改保护驱动。

灰度覆盖和存档地点的可复现构建、原生模块参数及受控测试见[显示反馈修正](docs/UI_READABILITY_FIX.md)。完整字体映射保持既有版本，新增Field包进入完整增量候选列表。

图片正立竖排与原生字形统一字号/基线构建见[UI_ALIGNMENT_FIX.md](docs/UI_ALIGNMENT_FIX.md)，改动灰度头后须重新编译profile。
