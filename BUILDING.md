# 构建说明

## 通用移动碰撞修复候选（2026-10-24）

完整玩家物理提交保护、自有Win32夹具、编译后内核→真实BSP回放、共享14项安装/撤回及人工入口
见[通用碰撞候选](docs/COLLISION_GUARD.md)。MC_COLLISION_GUARD默认关闭，不与剧情黑幕或音效后端候选混用。

## 贴墙与连招声音可选诊断（2026-10-24）

`workspace_profile`、`contact_audio_trace_fixture` 与纯净版v2专用诊断增量包的构建、
源锁、字节级撤回和手动取证步骤见[碰撞与声音调查](docs/MOVEMENT_COMBAT_AUDIO_INVESTIGATION.md)。
只有专用入口开启探针；不是卡墙/缺声修复，不启动游戏，不复制完整游戏数据。

## F11 暴走辅助（2026-10-23）

生产输入桥、真实暴走计时/评分和8份原技能后续动作的离线闭环见
[F11暴走辅助](docs/RAGE_COMBO_ASSIST.md)。普通F10/R3与继续游戏修正保持不变，不启动游戏。

## 真实对白与Miles播放夹具（2026-10-23）

自有Win32目标`dialogue_audio_fixture`、`dialogue_voice_chain_fixture`及真实文字/
原声采样/剧情barrier回放见[真实对白链路](docs/DIALOGUE_REAL_CHAIN.md)。
夹具静音播放原声但不启动游戏或执行游戏DLL入口；本轮不更新共享模块。

## 战斗手柄输入链夹具（2026-10-23）

自有 Win32 生产输入与聚焦适配器 `battle_gamepad_chain_fixture`、
`battle_gamepad_focus_fixture` 的构建、源样本校验和离线验证见
[战斗手柄输入链修正](docs/BATTLE_GAMEPAD_CHAIN_REPAIR.md)。不启动游戏。

## 战斗反馈运行模块（2026-10-23）

复用既有Win32生成头与共享运行目录。构建新增`battle_input_fixture`、
`battle_rhythm_fixture`、`damage_projection_fixture`及`workspace_profile`，不复制游戏。
12份角色模块的整批更新、原始摘要校验、撤回和小更新包命令见
[玩家反馈调查](docs/PLAYER_FEEDBACK_20261023.md)。

## 图片结构与全量审计（2026-10-20）

422 份 BGR 的源绑定审计、204 份图片计划重建、原 Play 图片单项事务和精确回滚见
[图片结构修复](docs/IMAGE_INTEGRITY_REPAIR.md)。复用共享目录，仅备份变化图片，
不复制整套游戏；`check_image_repair.py` 的三态验证均不启动游戏。

## 高分辨率文字C方案（2026-10-20）

4倍覆盖、原生独立纹理桥、自有D3D7三态夹具、原Play入口及单项回滚见
[高清字模接入](docs/SCALED_FONT_COVERAGE.md)。离线GPU读回通过，游戏画面仍待手动验收。

## 换区前Loading呈现候选（2026-10-19）

该自绘占位候选已撤回，正常共享入口恢复原状态；目标改为提前显示游戏自带Loading。
以下目标及脚本仅保留研究与回滚记录，不作为当前玩家方案。
Win32目标`workspace_profile scene_loading_fixture`；共享目录重建支持`--scene-loading DLL`。
离线顺序验证、现有入口整合和单项撤回见[场景Loading呈现](docs/SCENE_LOADING_PRESENTATION.md)。
实机待验收；场景切换崩溃不计作修复。

## 启动GUI越界修正（2026-10-19）

启动GUI守卫沿用 Win32 构建 `workspace_profile gui_parent_guard_fixture`；验证、默认整合及回滚见 [GUI父节点守卫](docs/GUI_PARENT_GUARD.md)。共享目录重建支持 `--gui-parent-guard`，统一包要求此默认整合，场景崩溃未计作修复。

## 总部楼梯返回高度候选（2026-10-19）

沿用已有Win32生成头与CMake配置，构建`workspace_profile field_return_height_fixture`。
`--baseline`夹具预期退出1，候选及真实PE分页安装/回滚分别验证。
使用`tools/integrate_field_return.py`接入正常入口，保留原8份模块和游戏资源。
共享目录重建传`prepare_shared_runtime.py --field-return-height DLL`；统一包要求默认整合。
baseline与维护开关`-WithoutFieldReturnHeight`保留原路由，事务记录支持完整恢复。
完整命令、触发链、原生指令回放及实际软锁尚未验收的边界见
[楼梯退回高度](docs/STAIRWELL_RETURN_HEIGHT.md)。

## 提示文本与对话显示修正（2026-10-19）

提示文本规则保存在 `locales/zh-CN/prompt-punctuation-policy.json`，
审计入口为 `tools/normalize_prompt_punctuation.py`；普通人物对白不进入提示标点规则。
当前运行资源的增量重建与对话钩子证据见 [文本与对话修正](docs/TEXT_DIALOGUE_REPAIR.md)。
部署入口 `tools/deploy_text_runtime.py` 整批校验当前摘要及候选的前后摘要，
只备份和修改本次变化文件；存档、增强配置和其它游戏资源保持原样。
商业文件不作为完整载荷分发，玩家小更新使用 [增量更新包](docs/TEXT_RUNTIME_UPDATE_PACKAGE.md)。

## 统一玩家测试补丁包（2026-10-17）

`python tools/build_player_test_bundle.py --source ORIGINAL_GAME --runtime runtime --output dist/NEW_TEST_PACKAGE`

原版只读；共享运行目录须通过已有摘要清单验证。构建器将原版与当前共享游戏逐文件比对，
只为变化资源生成MCD1块增量，打包自有运行模块、地图候选、配置工具及固定版DDrawCompat许可。
不打包原版完整文件、存档、Python或本机注册表。Windows玩家端使用自带PowerShell；
`Install.cmd -Source ORIGINAL_GAME -Target NEW_TEST_GAME`在新目录复制并修改资源。
包内README列出配置、各独立候选入口和回滚命令。格式和验收边界见[统一测试包](docs/PLAYER_TEST_PACKAGE.md)。

增强配置界面与专用模块的当前构建、增量更新及回滚步骤见[配置工具构建](docs/CONFIGURATION_MATERIAL.md)。

## 清理生成产物（2026-10-19）

`Clean-generated.cmd` 仅保留最新统一测试 ZIP，清除旧包、解压副本、`build/`、`out/` 和工具/测试缓存。
原版光盘、共享运行目录、存档与重建依赖保留；预览、验证及边界见[共享运行布局](docs/SHARED_RUNTIME_LAYOUT.md)。

## 当前运行布局（2026-10-14）

功能更新采用[共享数据布局](docs/SHARED_RUNTIME_LAYOUT.md)：只更新运行模块与配置，不复制整套游戏。
历史 `build/*-game` 和调试/回滚产物清理后不再存在；后文旧命令仅作为历史研究流程。
当前原生重建命令、依赖位置和人工启动入口以共享布局文档为准。

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

共享目录重建可在原有 `tools/prepare_shared_runtime.py` 参数后追加
`--capture-helper build/native/Release/capture_helper.exe`。工具只接受 PE32 x86 EXE，
将自有采集器复制为 `modules/capture_helper.exe`，同时生成 `Play-diagnostic.cmd` 并登记两者摘要。
未提供该参数时不生成诊断入口；普通 `Play.cmd` 不默认开启捕获。
统一测试包沿用共享目录中的可选采集器和入口，不复制额外商业游戏资源或完整游戏副本。
诊断入口使用当前 configured 设置，仅显式 `-CaptureException` 才传入 `--capture-exception`；
`-VerifyOnly` 仍保留 launcher 预检路由，不启动游戏。


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

## 4K标题背景候选

独立、源摘要锁定的背景构建及验收见[4K标题背景](docs/TITLE_BACKGROUND_4K.md)。不覆盖已验收运行副本。

## 现代化候选与区域地图

**当前共享运行包**：只使用一份`runtime/data`，不再按功能复制游戏。
以下独立副本命令为历史实验流程，不用于新阶段交付。当前候选模块选择、
新打包参数、常用旧cmd重定向及手动验收见[共享入口修正](docs/SHARED_ENTRY_REPAIR.md)。

汉化正文、字库和已验收标题资产保持冻结。配置、纹理及自由视角独立入口分别见ENHANCEMENT_CONFIGURATION.md、CURRENT_TEXTURE_LIFETIME.md、FREE_VIEW_CANDIDATE.md。区域地图见docs/MAP_OVERLAY_CANDIDATE.md；以下命令不启动游戏，不刷新旧验收模块。

地图构建依赖复用tools/requirements-localization.txt中的Pillow，仅构建需要；玩家端使用系统GDI+/GDI32，没有新的Python运行依赖。

```powershell
python -m pip install -r tools/requirements-localization.txt
python tools/build_map_atlas.py --source USER_GAME/MAP --output build/map-atlas --size 2048
python tools/prepare_map_trial.py --workspace build/configurable-modern-game --native build/advanced-display-native/Release --atlas build/map-atlas --locale locales/zh-CN --output build/map-overlay-runtime
```

前置配置副本由tools/prepare_configuration_trial.py从已有版本匹配、完整汉化的独立输入创建。新运行模块与地图输出都必须为新目录；在现有已配置Win32 CMake中构建workspace_profile、workspace_launcher、map_overlay_fixture、world_gamepad_fixture、modern_gamepad_fixture、gamepad_ui_fixture。Map数据、原游戏、生成图及运行DLL不提交仓库，源哈希与PNG/MCM1摘要写入生成清单。

未知旧版WRD拒绝；不是静默套用新版布局。配置JSON不变，入口共享已有配置副本的互斥锁。这里只提供可复现构建与候选预检，真实区域/硬件验收分别记录。

## 只读动画姿态审计

在现有Win32 build/native中构建目标bone_pose_audit（C++17，无新增依赖），
运行`build/native/Release/bone_pose_audit.exe runtime/data/AINIM`。
该命令只读用户本地动画、执行生产矩阵数学，不启动游戏、不导出姿态数组。
`tests/test_bone_pose_native.py`以自有合成ANI检查截断、非有限与子引用；
未构建原生目标时显式skip，不把skip称作已验证。

## Optional offline native title replay

Developer-only dependency: `python -m pip install -r tools/requirements-native-replay.txt`.
Run `python -O tools/replay_native_title.py --sample runtime/data/MCAlpha.dll --report build/native-title-report.json`.
Requires the supported user-supplied image; no game binaries are distributed. See [native admission evidence](docs/GAMEPAD_NATIVE_ADMISSION.md).

Cursor preparation/visibility-state replay: `python -O tools/replay_native_cursor.py --sample runtime/data/MCAlpha.dll --report build/native-cursor-report.json`.
This stops before external matrix/graphics APIs and does not verify rendered pixels; see [cursor path evidence](docs/GAMEPAD_NATIVE_CURSOR_PATH.md).

Original GUI keyboard admission and phase replay: `python -O tools/replay_native_keyboard.py --sample runtime/data/MCAlpha.dll --report build/native-keyboard-report.json`. See [keyboard admission](docs/GAMEPAD_KEYBOARD_ADMISSION.md); scene listener is a recorder boundary, not actual gameplay.

Incremental offline map resources: `python tools/build_map_atlas.py --source runtime/data/MAP --output build/map-legacy-candidate --size 2048 --ids 22 31 32 39 128`. Read-only coverage: `python tools/audit_map_geometry.py --source runtime/data/MAP --report build/map-coverage.json`. Outputs must be new; see [legacy WRD geometry](docs/MAP_LEGACY_GEOMETRY.md). No active runtime deployment is implied.

Field static-prefix audit: `python tools/resource_field.py --source runtime/data/Field --maps runtime/data/MAP --engine runtime/data/MCAlpha.dll --report build/field-prefix-report.json`. Requires supported local loader hash, new report outside data; see [Field prefix](docs/FIELD_STATIC_PREFIX.md). No game startup or runtime deployment.

Optional offline height cutaway: append `--clip-z-max 30` to an incremental atlas build. Full-scene viewport remains unchanged; this is not automatic floor or navigation detection. See [height cutaway](docs/MAP_HEIGHT_CUTAWAY.md).

Native cutaway overlay replay uses the owned map_overlay_fixture target with `ASSETS OUTPUT.png [--mini]`; it reports the actual mode and renders the production GDI+ canvas without a game launch. See [native cutaway replay](docs/MAP_CUTAWAY_NATIVE_REPLAY.md).

## Locale-bound opening centering data

Opening ink positions belong to locale data, not generic runtime code. Generate the header
from version/hash-verified localized resources before building:

```powershell
python tools/build_opening_layout.py --source runtime/data --metadata locales/zh-CN/opening-layout.json --output runtime/build-inputs/opening_layout_data.h
$openingHeader=(Resolve-Path runtime/build-inputs/opening_layout_data.h).Path.Replace('\','/')
cmake -S src/runtime -B build/native -A Win32 "-DOPENING_LAYOUT_DATA_HEADER=$openingHeader"
cmake --build build/native --config Release --target workspace_profile title_layout_fixture
build/native/Release/title_layout_fixture.exe --opening-center-check
```

Retain existing `NATIVE_FONT_DATA_HEADER` and other build options. The generator validates
every recorded FDI/BGR SHA256 and remeasures actual ink bounds/centers before writing output;
unknown/drifted sources fail rather than falling back. No header means an empty runtime table
and no locale-specific opening adjustment. Another locale supplies its own metadata file.
See [opening centering evidence](docs/OPENING_CENTER_REPAIR.md).

## 刚性附件与开场居中回归（2026-10-19）

见 [混合动画相位](docs/RIGID_MOTION_PHASE.md) 与 [开场居中](docs/OPENING_CENTER_REPAIR.md)。
新增目标 `rigid_motion_fixture`；必须同时运行原 `motion60_fixture` 与 `title_layout_fixture`。

小型运行模块更新包的构建、安装和回滚见 [2026-10-19 热修候选](docs/RUNTIME_HOTFIX_20261019.md)。

## 场景切换调查探针（2026-10-19）

原生卡尔塔Loading的源锁候选、独立开关、离线验证与事务回滚见
[原生Loading提前呈现](docs/NATIVE_LOADING_PRESENTATION.md)。共享入口已接入，画面待人工验收；不含自绘图片。

`scene_texture_probe`仅运行源锁驱动的Bind/Delete函数和真实系统D3D7，不运行游戏入口。
三模式baseline/candidate/rollback均属资源级观察，不是完整场景切换验收；正常入口/包不改。
命令及“不把仍绑定当UAF”的关键反证见[场景调查](docs/SCENE_TRANSITION_INVESTIGATION.md)。

## 伤害数字离线绘制夹具（2026-10-23）

`damage_projection_bridge` 和 `damage_projection_gpu_fixture` 均为自有程序，
输出隔离到 `build/native/Release/damage-render-fixture/`，不加入共享运行模块或玩家更新包。
同目录的 `AsrD3DDrv.dll` 是 `/NOENTRY /NODEFAULTLIB` 自有数据夹具，不是原商业驱动，
不得复制到游戏目录。商业 PE 仅由 Python/Unicorn 按整份源摘要锁定后读取。

```powershell
cmake --build build/native --config Release --target damage_projection_bridge damage_projection_gpu_fixture
$env:PYTHONPATH="$PWD/runtime/dependencies"
python -m unittest discover -s tests -p 'test_damage*.py' -v
```

原生资源链和GPU像素检查命令见[伤害数字绘制链](docs/DAMAGE_PROJECTION_REPAIR.md)。
离屏HAL依赖本机系统D3D7能力；设备拒绝的分辨率如实保存HRESULT，不通过切换桌面模式规避。

## 一次性连招辅助闭环回归

新增 `combo_assist_chain_fixture`（生产输入持久适配器）和
`combo_assist_context_fixture`（手动接管/模式/生命周期回归）目标。
原生回放及真实资源摘要见[辅助判定链修正](docs/COMBO_ASSIST_CHAIN_REPAIR.md)。
该流程不启动游戏；构建适配器后执行 `python -m unittest discover -s tests -p "test_combo*.py" -v`。

## 发布功能调整（2026-10-23）

手柄与自由视角归档，四条模型路径插帧和 F5 随机遇敌开关的构建、增量更新与回滚见 [发布功能调整](docs/RELEASE_CONTROLS_2026-10-23.md)。

## 纯净版直接覆盖格式

2026-10-24完整测试集合可用build_clean_overlay.py的`--test-candidates`生成：
Play.cmd和Configure.cmd共同默认启用卡墙/声音候选，Play-stable.cmd提供保留此前修复的对照。
该默认只作用于包内副本，本机共享版仍保留原可选路由；内容与验证见[统一测试集合](docs/CLEAN_GAME_OVERLAY.md)。

黑屏/卡墙专项记录、真实GID原生离线链和共享data/布局专用更新见
[阻断问题调查](docs/BLOCKER_TRACE.md)。共享更新与平铺更新须分别使用，载荷不含复现存档。

采样声音后端候选的真实Miles原生夹具、构建、诊断版专用更新及撤回见
[声音后端候选](docs/AUDIO_PROVIDER_POLICY.md)。默认关闭，未完成游戏内F10/F11验收。

平铺 ZIP 的构建、独立纯净备份回滚和布局验证见 [纯净版覆盖测试包](docs/CLEAN_GAME_OVERLAY.md)。该格式直接替换变化资源，不依赖历次小更新；共享运行目录仍使用原 `data/` 布局。

## 技能隐藏模型弹字回归

构建damage_projection_fixture、damage_projection_bridge和workspace_profile后，执行`python -m unittest discover -s tests -p "test_damage*.py" -v`。原生资源链现为11组，包含隐藏模型、父级变换、旧缓存和回血；命令、负对照与离屏像素检查见[伤害投影修正](docs/DAMAGE_PROJECTION_REPAIR.md)。仅离线执行，不启动游戏。
