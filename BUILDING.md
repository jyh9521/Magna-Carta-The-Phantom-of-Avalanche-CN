# 当前源码构建与验证

本页是当前构建入口。旧阶段命令集中保存在[历史构建记录](docs/BUILD_HISTORY.md)，其旧路径、阶段状态与发布措辞不作为当前默认值。

## 1. 源码与附件状态

v1.0 正式版使用编译式桌面 revision 4，玩家包为 `MagnaCarta-zh-CN-v1.0-release.zip`。
标题版本文字修订采用原生双行标识；文案源、全部角色模块刷新与离线回放见[标题版本标识](docs/TITLE_VERSION_LABEL.md)。
玩家下载、功能与安装见 [v1.0 发布说明](docs/RELEASE_V1.0.md)及 [GitHub Release](https://github.com/jyh9521/Magna-Carta-The-Phantom-of-Avalanche-CN/releases/tag/v1.0)；本页面向源码维护与构建。

干净检出可以运行源码、自有夹具和编译式桌面回归。完整玩家包重建仍需要下列外部输入；GitHub 仓库不含原版游戏、已验收覆盖 ZIP、图标、运行数据或生成头。
源码回归通过不等于完整资源从零重建，也不等于游戏画面验收。

## 2. 干净检出环境

Windows 10/11，Python 3.12 或更新版本，Git；桌面集成测试需要系统 .NET Framework 4.x、WPF、Windows PowerShell 5.1。
实际验证使用 Windows、Python 3.14。原生模块另需 Visual Studio 2022 Build Tools 的桌面 C++ 工作负载、Windows SDK 和 CMake 3.20 以上版本，目标必须为 Win32。

在新克隆的仓库根目录执行：

```powershell
git clone https://github.com/jyh9521/Magna-Carta-The-Phantom-of-Avalanche-CN.git
cd Magna-Carta-The-Phantom-of-Avalanche-CN
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tools/requirements-dev.txt
$env:PYTHONPATH = ''
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -B -X utf8 tools/check_source_tree.py
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -p 'test_*.py'
```

依赖统一入口引用现有三份固定版本清单，不要求 `runtime/dependencies`。
测试必须串行运行；桌面集成夹具共享原生进程空闲检查，独立并行运行会相互干扰。

测试使用自有微型数据，编译入口并检查设置迁移、拒绝错误版本、权限调度、完整包审计与回滚。
需要商业资源或预先构建原生夹具的项目在输入缺失时明确跳过；跳过不算该项通过。
完整本地验证需要准备相应资源及 Win32 夹具后重跑同一命令，不通过删除测试掩盖缺失输入。

只验证最新桌面入口：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -p 'test_compiled*.py'
```

此命令会从当前 C# 源码编译测试用 EXE/DLL，并用自有小型载荷运行测试，不生成玩家包、不启动游戏。

## 3. 完整桌面覆盖包的外部输入

| 输入 | 身份与用途 | 是否随源码提供 |
| --- | --- | --- |
| 本地初版 `MagnaCarta-zh-CN-v1.0.zip` | SHA-256 `44875140bcb101c017aa3759a3570f80949d8d1f7b99ad41989977f70eb38911`；包含 814 项已验收变更及旧封装清单 | 否；历史构建输入，不是当前玩家附件 |
| `MC.ico` | SHA-256 `0bdb54b9098c2d53e060a81c9c280aa6b9729573c21e4bb0ab81b2b0d55fd3ce`；桌面图标 | 否；明确提供文件路径 |
| 当前共享运行输入 | `runtime.json`、清单登记的 modules/maps/config 等文件和 data 中的固定输入；构建器逐项验摘要 | 否；不能用空目录代替 |
| 兼容资源计划 | `assets/release/baseline-compatibility.json`；绑定原版清单与 297 项资源身份 | 是 |
| C#、XAML、语言目录与许可 | `src/desktop/`、`src/configuration/`、`locales/zh-CN/` | 是 |

`--runtime` 不是可省略的“加速缓存”：当前地图和完整输入取自该清单。省略该参数只会基于旧输入构建不同组合，不能称为当前完整包复现。
`--source-game` 可另外提供匹配的固定游戏输入；默认读取所给共享目录的 data 子目录。未知或缺失输入停止构建，不自动采纳安装目录中的其他版本。

准备好上述输入后，在源码根目录执行。以下大写路径必须替换为实际绝对路径；工作目录与输出 ZIP 必须是全新路径：

```powershell
$Python = (Resolve-Path .venv/Scripts/python.exe).Path
$Accepted = 'C:\INPUTS\MagnaCarta-zh-CN-v1.0.zip'
$Icon = 'C:\INPUTS\MC.ico'
$Runtime = 'C:\INPUTS\shared-runtime'
& $Python -B -X utf8 tools/build_compiled_release.py --source $Accepted --source-sha256 44875140bcb101c017aa3759a3570f80949d8d1f7b99ad41989977f70eb38911 --icon $Icon --runtime $Runtime --compatibility-plan assets/release/baseline-compatibility.json --work build/desktop-rebuild --output dist/MagnaCarta-zh-CN-v1.0-rebuilt.zip
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed' }
& $Python -B -X utf8 tools/verify_compiled_release.py --archive dist/MagnaCarta-zh-CN-v1.0-rebuilt.zip --icon $Icon --report build/desktop-rebuild/package-audit.json
if ($LASTEXITCODE -ne 0) { throw 'Package audit failed' }
```

构建器编译两份 EXE 与公共 DLL，保留已接受资源并补齐固定依赖；审计器检查归档、清单、图标、814 项游戏资源与 488 项固定输入。最终 ZIP 中不携带外置脚本、XAML 或清单。
托管编译时间戳、构建提交标识及许可文档会影响 ZIP 摘要；同一功能版本不自动等于跨环境逐字节相同。应保存 build-report.json、package-audit.json 和 ZIP SHA-256，并逐项比较非预期变化。
当前玩家行为及原生预检方式见[编译式桌面入口](docs/COMPILED_DESKTOP_RELEASE.md)。

## 4. 原生模块与资源重建

原生工程为 `src/runtime/CMakeLists.txt`。完整功能构建需要指定字体、系统消息和开篇生成头，并生成剧情字幕与版本文字头，而不是只有默认 CMake 配置：

| CMake 参数 | 生成入口或来源 |
| --- | --- |
| `NATIVE_FONT_DATA_HEADER` | `tools/build_font_coverage.py`；固定字槽映射、轮廓字体、原生字体、地点译文及源锁引擎 |
| `SYSTEM_MESSAGE_RULES_HEADER` | `tools/build_system_messages.py`；系统消息计划、同一字槽映射及源锁模块 |
| `OPENING_LAYOUT_DATA_HEADER` | `tools/build_opening_layout.py`；开篇资源与 `locales/zh-CN/opening-layout.json` |
| `SCALED_FONT_DATA_HEADER` | `tools/integrate_scaled_font.py --cache CACHE --header NEW_HEADER`；已验证高清字模缓存 |
| `STORY_CAPTION_SOURCE_ROOT` | 匹配的 Field/SED 等源资源；CMake 调用 `tools/build_story_captions.py` 生成字幕头 |
| `TITLE_VERSION_CATALOG` | 默认 `locales/zh-CN/title-version.json`；生成双行版本文字头，复用原生字体 |

字体来源锁和许可位于 `assets/font-sources/noto-sans-sc.json`、`assets/licenses/NotoSansSC-OFL.txt`。
不要重新排序已冻结的私有字槽，也不要用缺省空映射编译替代完整模块。
字形和系统消息详见[原生映射](docs/NATIVE_GLYPH_MAPPING.md)、[灰度覆盖](docs/UI_READABILITY_FIX.md)、[系统消息](docs/SYSTEM_MESSAGES.md)及[高清字模](docs/SCALED_FONT_COVERAGE.md)。

```powershell
cmake -S src/runtime -B build/native -A Win32 "-DNATIVE_FONT_DATA_HEADER=C:/INPUTS/headers/native_font_data.h" "-DSYSTEM_MESSAGE_RULES_HEADER=C:/INPUTS/headers/system_message_rules.h" "-DOPENING_LAYOUT_DATA_HEADER=C:/INPUTS/headers/opening_layout_data.h" "-DSCALED_FONT_DATA_HEADER=C:/INPUTS/headers/scaled_font_binding.h" "-DSTORY_CAPTION_SOURCE_ROOT=C:/INPUTS/source-game" -DWORKSPACE_EXE_SHA256=6046b29600b5e009903b3495bd11df0b4d89fc3545adde028193ea9fbff8d4de -DLOCALE_ENGINE_SHA256=7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e
cmake --build build/native --config Release --target workspace_profile workspace_launcher
```

原生模块重建后，按专项部署器更新清单；不直接把新 DLL 覆盖到已锁定清单中。
完整资源流程依次为：原版版本核验 → [文本与字体](docs/FULL_TRANSLATION_PIPELINE.md) → [图片/视频/模块](docs/MEDIA_LOCALIZATION.md) → [地图](docs/MINIMAP_F9_TEST.md) → 原生模块 → 覆盖包审计。
历史阶段的已有工具和技术发现全部保留；当前仓库没有将这些外部输入收齐并从零生成全部玩家资产的单一入口。

## 5. 清理与保留

源码仓库保留有效测试、逆向记录、语言数据、源素材、来源许可及历史重建工具。
只移除已填充目录的空占位符与只锁定过时文档措辞的检查；后者改为检查当前指南链接和源码清单。
`tools/check_source_tree.py` 拒绝已跟踪的构建输出、游戏副本、缓存、失效当前指南链接和冗余占位符。

本地历史产物另由 `Clean-generated.cmd` / `tools/cleanup_release.py` 先预览再清理；本轮不删除共享数据、存档、原盘、必要构建输入、回滚证据或最新 ZIP。
每轮提交和推送规则见[贡献说明](CONTRIBUTING.md)。
