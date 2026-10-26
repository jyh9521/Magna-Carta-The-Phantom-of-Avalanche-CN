# 编译式桌面入口与 v1.0 封装修订

**v1.0 正式版覆盖包：`MagnaCarta-zh-CN-v1.0-release.zip`（desktop revision 4）。包含完整汉化、修复模块、固定运行依赖、旧安装兼容资源及按需 UAC 入口，不再叠加单项修复 ZIP。以下旧版与单项修复记录保留作历史证据。**

> 当前源码重建入口和输入准备见[构建说明](../BUILDING.md)。下列 V: 路径及旧工作目录属于历史记录，不是克隆后可用的默认值。

## 状态与边界

2026-10-25：配置、启动路由和覆盖包校验逻辑从外置 PowerShell 迁入 C#，保留原生运行模块。源码仍在仓库；分发包不携带脚本源码、外置 XAML、config 目录、runtime.json 或 Overlay-Manifest.json。这是编译与资源嵌入，不是加密或防反编译保证。

v1.0 通过 [GitHub Release](https://github.com/jyh9521/Magna-Carta-The-Phantom-of-Avalanche-CN/releases/tag/v1.0) 提供覆盖 ZIP，不另设安装器。玩家功能与使用步骤见 [发布说明](RELEASE_V1.0.md)。814 个已验收游戏资源保持输入摘要；地图模块和地图资产采用当前共享运行清单。既有游戏通关反馈不等于新桌面入口和地图组合已经完成游戏验收。

## 模块与资源

- `src/desktop/CompiledEntry.cs`：Configure.exe / Game.exe 桌面入口。
- `src/desktop/Configuration.cs`：WPF 设置、直接选择项、保存、恢复默认和子进程状态。
- `src/desktop/RuntimeCore.cs`：配置验证、运行路由、资源摘要检查与恢复。
- `modules/DesktopRuntime.dll`：上述公共实现；静态资源以 `mc/` 名称嵌入程序集。
- 图标、标题图、XAML、语言目录、显示预设、52 字节配置模板和两份清单均内嵌；不提取并执行脚本。
- 原生运行模块、地图与字体继续作为运行数据存在。程序依赖 Windows .NET Framework 4.x / WPF，不再依赖 PowerShell。

每份清单列出桌面 EXE 和运行资源摘要；公共 DLL 不在自身内嵌清单中计算递归自摘要。最终 ZIP SHA-256 覆盖公共 DLL 在内的全部归档字节。清单和摘要是完整性核对，不是数字签名或恶意文件检测。

## 用户设置与布局

当前设置路径为游戏根目录的 `enhancements.json`；日志和临时运行缓存仍在 `%LOCALAPPDATA%/MagnaCarta/Installations/<安装目录标识>/cache/`。标识沿用安装根目录标准化后 SHA-256 前 16 位。根目录已有设置优先；根目录缺失时依次读取旧用户目录设置、旧 `config/enhancements.json`，两者都缺失时才生成内嵌默认值（1080P / 无边框 / 60 帧）。旧设置保留，不删除；无效设置直接报错而非静默重置。存档位置不变。游戏目录显示 INI 仍按原生组件要求保留。

配置窗口默认 720×600 DIP，保留小工作区滚动和窗口化尺寸选项。底部提示改为横排，相邻项目用两个空格分隔：

```text
F5切换随机遇敌  F9切换小地图  F10普通自动连招  F11暴走模式自动连招
```

提示区不再保留原先底部 16 DIP 空白；窗口较初版 670 DIP 高度减少 70 DIP。离屏预览与测试不代表实际显示器视觉验收。

## 历史 centered 构建与检查

输入仍为已验收覆盖 ZIP 和明确摘要，不构造完整游戏副本。MC.ico 由调用者提供，不提交图标原文件。命令中的输入摘要必须来自对应文件，不使用占位值绕过校验。

```powershell
python tools/build_compiled_release.py --source dist/MagnaCarta-zh-CN-v1.0.zip --source-sha256 44875140bcb101c017aa3759a3570f80949d8d1f7b99ad41989977f70eb38911 --icon V:/MC.ico --runtime runtime --work build/compiled-release-v1-header --output dist/MagnaCarta-zh-CN-v1.0-desktop-centered.zip
python tools/verify_compiled_release.py --archive dist/MagnaCarta-zh-CN-v1.0-desktop-centered.zip --icon V:/MC.ico
python -m unittest discover -s tests -p test_compiled_desktop.py
python -m unittest discover -s tests -p test_configuration_material.py
```

构建目录和输出 ZIP 必须不存在；历史脚本打包器保留用于复现原始版本。审计工具逐项核对 ZIP CRC、外置源码缺失、资源清单、原生 ICO 图像帧、窗口图标和 814 个游戏资源。托管元数据审计使用 ReflectionOnlyLoadFrom，不执行被审计程序集。

## 玩家入口与恢复

```powershell
./Configure.exe
./Game.exe --verify-only
./Game.exe --check-installed
./Game.exe --check-baseline "ORIGINAL_GAME"
./Game.exe --rollback "ORIGINAL_GAME"
./Game.exe --without-test-candidates
```

`--verify-only` 不启动游戏；Configure.exe 对应参数仅做隐藏 UI 自检。回滚先预检所有被覆盖资源的原版摘要，再恢复资源并移除新增文件，保留用户设置与存档。整个回滚不是跨文件事务；中途 IO 失败需要依据日志处理，不声明全局原子性。回滚后应使用原版游戏入口。

将 ZIP 覆盖解压到旧安装不会删除旧脚本。确认设置迁移和新入口检查成功后，可将旧 config 目录、Start.ps1、Verify-Overlay.ps1、runtime.json 和 Overlay-Manifest.json 移出游戏目录留作备份；新入口不使用这些文件。新 ZIP 本身不含这些外置文件。

## 验证与告警记录

自动测试使用自有微型数据、拒绝非 verify-only 参数的模拟原生入口，覆盖 24 种显示组合、功能开关、用户设置迁移、错误预检、INI 恢复、日志保存、完整覆盖包恢复和隐藏 WPF 预览。全量测试与此集成测试应串行执行：原生入口空闲检查是全局检查，并行测试可能触发“Exit game and native launcher first”。不修改生产空闲保护来迁就测试。

2026-10-25 用户提供安全软件截图：HEUR:Trojan/MSIL.Loader.d，文件被删除。临时 native-preflight/OwnedEntry.exe 在编译后缺失，调用失败为 WinError 2；对应源码是临时反射校验入口，不属于分发包。该临时程序没有恢复或重跑，未更改安全软件设置。仅凭截图和缺失文件不判定误报；真实原生入口的该次校验未执行，不能记录为通过。正式发布包的文件审计和功能测试不等于杀毒软件扫描通过。

本轮测试记录：全套 1076 项通过（3 项跳过）；随后横排提示调整的编译桌面 18 项与 WPF 5 项重新通过。720×600 离屏预览回读正常，默认布局无需滚动。自有数据独立回滚恢复 1 项、移除 12 项新增文件，存档和用户设置保持原字节；正常修改副本保留。详细命令、输出与本地归档摘要保留在 runtime/maintenance/compiled-desktop-v1-20261025。

横向收紧修订：窗口宽度 790 → 720 DIP，高度和文字字号不变；四项快捷键保持横排。此修订单独重跑桌面与 WPF 测试，使用独立界面资源副本验证 720 → 790 的撤回；不运行游戏。

顶部栏修订：移除“高清标题 · 汉化保持当前版本”显示节点及 C#/PowerShell 标签绑定。HeaderGrid 采用 `* / 220 / *` 对称列，LOGO 在顶部栏水平、垂直居中，不再随左侧 210 / 右侧 90 的非对称列向右偏移。WPF 自检测量 LOGO 中心相对 HeaderGrid 的偏差（容差 0.5 DIP），并检查旧提示节点不存在。19 项编译桌面测试、5 项原 WPF 测试通过；独立 DLL 副本精确回滚并重跑原布局自检通过，正常修改副本保留。窗口仍为 720×600，未运行游戏。

## 包外基础库版本与入口错误详情（2026-10-26）

已验证：最新 centered 包的 938 项运行载荷摘要全部匹配，但现场包外 `Asura.dll`
为 499,712 字节，SHA-256 `f9b6c605843add37eb527f3bccc696b7c041715956d98d102fdd459ccf020795`。
增强模块要求 516,096 字节，SHA-256
`f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557`。
两者不是同一受支持二进制。此前覆盖包不携带该基础库，因此重复覆盖不会替换该基础库；
该错误不是设置 JSON 或旧缓存失效，也不通过删除设置、放宽摘要检查或关闭 60 帧处理。

`Game.exe --check-installed` 现除覆盖载荷外，同时核对内嵌 runtime 的全部基础输入，
与入口的版本门槛保持一致；可变显示 INI 仍按原规则排除。
摘要错误日志记录期望值和实际值。配置窗口从本轮子进程新写的 Game.log 读取错误首行，
直接显示不匹配文件名；旧日志、缺失日志或读取失败继续显示退出码与日志路径，避免误报历史原因。
具体语言文案保留在 locale 目录，公共读取逻辑不绑定中文文件名或分辨率。

修复现场时须先保留原 DLL 及摘要，再从已经校验的匹配版本输入恢复单个基础库；
不得将未知版本加入白名单或提交完整商业 DLL。安装目录受系统保护时，使用管理员文件操作完成该单项恢复，
不改变目录权限。只执行 `--verify-only`，不自动运行游戏。
本地摘要、命令和独立副本回滚记录位于 runtime/maintenance/entry-hash-repair-20261026。


本轮新增 4 项回归，旧实现 4 项失败、修正后 23 项桌面集成测试通过。
全套首次运行 1,078 项，其中缺少 pycdlib 导致 1 个测试模块导入错误，另 3 项跳过；
复用 runtime/dependencies 后，该模块 4 项全部通过。两段覆盖合计 1,081 项，
1,078 项通过、3 项跳过，无剩余测试错误。共享匹配输入的原生 VerifyOnly 也通过，
该结果不是原安装修复完成或游戏画面验收。

本地另备 5 项文件的单项修复 ZIP：匹配基础库、两份桌面 EXE、公共 DLL 和说明。
修复副本基础库检查通过，独立回滚副本恢复原摘要及原错误；未新增完整游戏副本。
原安装因系统保护尚保留现场文件，管理员覆盖及随后原安装入口复验仍由测试者完成。


## 完整统一覆盖与旧安装兼容（2026-10-26）

已验证的缺口分为两类：原包的 143 项固定运行输入中有 9 项没有进入 ZIP；
原版引擎库、驱动及音频提供者又有部分依赖安装目录现存版本。
本轮按源清单枚举 53 项原生二进制，结合运行输入形成 191 项固定依赖，
全部进入同一 ZIP。较此前覆盖包增加 57 项输入，不以 source_files 中存在摘要代替包内存在文件。

只读全量比对发现，旧安装在补丁外另有 130 项原版资源缺失、167 项内容不同。
297 项路径、目标摘要及观察到的旧摘要记录在
`assets/release/baseline-compatibility.json`；该计划绑定整份原版源清单的规范化摘要，
构建前验证匹配输入，拒绝未知来源字节和错误源清单。模型、场景、怪物、特效及帧数据
按受支持基线恢复，不修改现有 814 项已验收汉化/修复资源目标。
统一包合计包含 488 项固定输入，其中含上述 297 项兼容资源；新增输入共 354 项。
完整指覆盖补丁及其依赖齐全，不是独立完整游戏。

构建器 `bundle_inputs` 对包内已有输入和补充源逐项验摘要；全部通过后才生成输出。
`complete_inputs.files` 与 runtime.data 一致，`baseline_compatibility` 绑定兼容计划。
审计器拒绝任何缺失的 runtime.data 或源清单原生输入，独立核对兼容资源目标摘要。
完整商业资源仍不进入源码提交；本地统一归档与公开源码同步分开处理。

`tools/verify_unified_overlay.py` 只搭建旧覆盖载荷加所需输入的最小验证目录，
不复制完整游戏。相同旧 Asura 输入须先复现退出 1，再仅覆盖一次统一 ZIP，
执行真实 Game.exe 的安装检查、原生入口预检、24 组显示预检和隐藏 WPF 自检。
所有预检保留 verify-only，不改变桌面显示模式，不启动商业游戏。
源清单未由 ZIP 替换的原版文件在原位置只读核对，确保没有遗留未覆盖的版本差异。

独立回滚视图只为最小覆盖目录建立硬链接，恢复时以新 inode 替换变更文件，
避免写穿正常修改副本。回滚必须恢复原字节及原 Asura 失败行为；正常修改副本保持通过。
用户设置、存档哨兵、无关文件及真实原安装输入分别核对。
本轮证据保存在 runtime/maintenance/complete-overlay-20261026；正式使用只需一个统一 ZIP。
这些结果属于离线包/原生预检，不扩展为新的游戏画面或全流程验收。


本轮最终记录：统一 ZIP 为 2,115 项文件、182,457,991 字节。
全套 `Ran 1094 tests in 603.390s`，`OK (skipped=3)`；没有剩余测试错误。
72 个原生/托管 PE 的导入模块均在包内或当前系统定位，无缺失模块；此项不执行游戏 DLL 初始化。
原版清单 11,784 项中，1,168 项由 ZIP 提供，另外 10,616 项在原位置比对通过，
未覆盖差异为 0。旧入口退出 1、统一覆盖后真实原生预检退出 0；
24 组显示配置和隐藏 WPF 自检通过；306 项独立回滚后恢复旧入口退出 1，
正常修改副本再次原生预检退出 0。原安装未部署本轮文件，游戏仍由测试者手动启动。

已清理 14 项旧 ZIP/校验文件，释放 1,057,028,889 字节；保留三份构建输入、
centered 对照基线和当前统一覆盖 ZIP，并保留共享数据、存档、设置与必要回滚证据。
不再把本轮单项修复包作为当前交付。


## 根目录设置与按需 UAC（2026-10-26）

已验证的现场原因：用户 JSON 与日志迁移至用户目录，并未解决原生显示层仍需写入
`DDrawCompat-MagnaCarta.ini` 的要求。此前补偿路径只覆盖“父目录禁止创建，但已有文件可写”；
当 INI 本身也没有写权限时，锁定原文件写入同样抛出 UnauthorizedAccessException。

当前行为：

- Configure 与 Game 在迁移设置、持有设置/运行互斥锁、打开本次日志之前检查写入路径。
  根目录用 DeleteOnClose 微型探针验证创建权，现有设置及显示 INI 用只打开、不改字节的方式检查。
- 权限不足且当前令牌未提升时，通过 `ShellExecute/runas` 重启同一个入口并等待退出码。
  Configure 重开可见窗口，Game 保持后台入口；已经提升的进程不再次请求 UAC。
- 路径参数在重启前转成绝对路径，保留配方、预检、候选开关及原调用者 LOCALAPPDATA。
  原调用者路径用于导入旧设置及写入日志，避免使用管理员凭据时误读另一账户的设置。
- UAC 取消保留退出码 1223，写入明确提示；不会继续原生入口，也不会创建根目录设置。
  子进程已有的本次具体错误日志优先保留，不以通用提权错误覆盖。
- EXE 显式内嵌 `asInvoker` 清单，关闭隐式文件虚拟化；实际提权由写入门禁决定。
  程序不执行 SetAccessControl，不修改安装目录或文件 ACL，不要求手动“完全控制”。
- `enhancements.json` 只在首次运行生成，不放入 ZIP，因此再次覆盖补丁不会重置根目录设置。
  INI/设置写入临时解除并恢复只读属性；该处理不替代权限提升。预检恢复 INI 原字节。
- `--check-installed`、`--check-baseline` 和 Configure 隐藏自检不请求 UAC。
  游戏 `--verify-only` 会验证真实写入事务，在受保护目录中仍可能需要 UAC，但不会启动游戏。

构建使用与前一完整统一包相同的来源锁、兼容计划、图标及运行输入，只更新桌面封装和说明。
新包保留 814 个已接受游戏资源以及 488 项固定运行输入，未重建游戏修复 DLL。

```powershell
$env:PYTHONPATH=(Resolve-Path runtime/dependencies).Path
python tools/build_compiled_release.py --source dist/MagnaCarta-zh-CN-v1.0.zip --source-sha256 44875140bcb101c017aa3759a3570f80949d8d1f7b99ad41989977f70eb38911 --icon ICON_PATH --runtime runtime --compatibility-plan assets/release/baseline-compatibility.json --work build/compiled-release-v1-uac --output dist/MagnaCarta-zh-CN-v1.0-unified-uac-20261026.zip
python tools/verify_compiled_release.py --archive dist/MagnaCarta-zh-CN-v1.0-unified-uac-20261026.zip --icon ICON_PATH
python -m unittest discover -s tests -p "test_compiled*.py"
```

验证分层：真实 Windows ACL 回归覆盖目录拒绝创建、INI 拒绝写入、提权前无设置/INI改写、
授权取消、参数转发、只读属性恢复、根目录设置优先与迁移。自动化截获 UAC 调度并在自有夹具中
模拟授权完成，不自动点击系统授权框；真实 UAC 同意/取消交互与游戏画面由测试者手动验收。
正常可写路径继续执行真实原生 `--verify-only`，不把模拟授权视为系统 UAC 实测。

人工入口：退出旧配置窗口，完整覆盖新 ZIP；从受保护目录双击 Configure，允许 UAC，
保存设置后确认游戏根目录生成 enhancements.json，再点“检查入口”。根目录已有设置应被保留，
旧用户目录设置应保持原字节。取消 UAC 应退出且不启动游戏。游戏仍由测试者手动启动。
本地完整命令、原摘要、三态回放与独立撤回记录位于
`runtime/maintenance/display-access-20261026/VERIFICATION.txt`。


本修订的自动验证结果：全套 1106 项（3 项跳过）通过；最终权限专项 9 项通过。
最小 ACL 回放的旧版返回 UnauthorizedAccessException / 退出码 1；新版请求一次 UAC 调度，
在夹具模拟授权后完成根目录迁移和预检 / 退出码 0；独立 DLL 回滚恢复原摘要并重现旧错误。
完整包复用此前稀疏覆盖夹具，通过 24 种显示组合的真实原生预检和隐藏配置自检，
INI 字节恢复、旧用户设置及来源夹具保持不变。归档 2115 项仅桌面 EXE 两份、
DesktopRuntime.dll 和说明 4 项改变；其余 2111 项与前一完整统一包字节一致。
系统 UAC 点击交互和实际游戏仍未在本轮自动执行。
