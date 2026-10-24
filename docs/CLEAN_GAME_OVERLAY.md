# 纯净版直接覆盖测试包

## 2026-10-24 全修复统一测试集合

`MagnaCarta-clean-game-all-fixes-test-20261024.zip`可直接覆盖受支持的纯净版，不需要历史全合一包
或Contact-Audio、Blocker、Collision等小更新。814项既有变化资源和全部最新自有模块一并交付，
11,784项源资源映射与当前共享数据逐一摘要核对，无额外未收录变化。存档、日志、维护端设置不进入包。

本版通过`--test-candidates`明确生成测试默认值，仅改变包内副本，不改本机共享运行目录：

- 普通Play.cmd及Configure.cmd的同一Start.ps1路由，默认启用通用卡墙、采样声音后端候选及接触观察。
  不依赖某个专项CMD遗留的环境变量。声音后端不可用时保留原生后备。
- Play-stable.cmd使用`-WithoutTestCandidates`，保留此前修复集合，仅关闭上述两项候选及接触观察。
  baseline配方也不启用两项候选。正常剧情黑幕不修改。
- 三个进程环境变量进入既有保存/恢复事务，正常结束及失败均还原；验证入口不启动游戏、不改变显示状态。
- 默认1080P、无边框、30帧、键鼠；60帧等设置仍经Configure.cmd选择。归档手柄/自由视角不重新启用。
- 候选尚未完成实际水之迷宫、全角色F10/F11验收；完整测试集合不是所有已知问题已经修复的声明。

包内仍为平铺布局，解压到MagnaCarta.exe同层后直接运行Play.cmd；无需Python、历史Install.cmd或data子目录。
Verify-Overlay.cmd检查覆盖完整性，Restore-Original.cmd从独立纯净备份撤回，保留存档、个人设置和日志。
针对平铺启动、候选默认值、配置器共用路由、对照/基线禁用、失败还原及覆盖/独立撤回的12项回归通过。
基础运行模块沿用此前921项（3项条件跳过）回归验证，不将该结果冒充新增整包游戏实测。

```powershell
python tools/build_clean_overlay.py --previous dist/MagnaCarta-unified-test-hud-fix-20261023.zip --previous-sha256 e75802844d12b01368a63383c4174baec67652c08431ab134791dcdf8bbc966a --runtime runtime --output dist/MagnaCarta-clean-game-all-fixes-test-20261024.zip --test-candidates
python -m unittest discover -s tests -p 'test_overlay*.py' -v
```

该格式是直接解压替换的完整功能集合，不依赖 F11、发布控制或后续 HUD 小更新。保留既有纯净备份，只覆盖用于测试的纯净安装目录。不要把唯一的纯净备份作为覆盖目标。

## 使用

1. 退出游戏，将 ZIP 内所有文件和文件夹直接解压到 `MagnaCarta.exe` 所在目录，替换同名文件。
2. 双击同层 `Play.cmd`，可用 `Configure.cmd` 调整分辨率、窗口模式、30/60帧。
3. 不运行历史 `Install.cmd`，不创建或移动到 `data/`。无需 Python。
4. 可选 `Verify-Overlay.cmd` 检查覆盖文件；设置和活动显示 INI 属于可变文件，不按发行缺省摘要拒绝玩家设置。
5. 回滚可运行 `Restore-Original.cmd` 并输入独立纯净备份路径。全部源/目标摘要预检成功后，恢复变化的原资源并移除新增的非设置运行文件；存档、设置、显示 INI、日志和维护检查入口保留。回滚后的原资源通过完整原版摘要检查，使用原游戏入口。

## 构建与内容边界

`tools/build_clean_overlay.py` 读取摘要锁定的既有统一增量包，核对每项源摘要、当前目标摘要、增量摘要、运行目录完整清单，再只将实际变化资源写成可直接替换的文件。未修改的商业资源不进入覆盖包；完整游戏不会被复制或提交。兼容层许可与字体/译文许可沿用统一包。生成覆盖 ZIP 只存放于忽略的 `dist/`，不将商业资源加入版本库。

包内 `runtime.json` 使用 `data_root="."`。通用 `StartShared.ps1` 支持 `data`（既有共享运行目录）和 `.`（纯净版平铺覆盖），其余值拒绝，缺省保持 `data`。发布清单去掉旧 `data/Play-*.cmd` 父目录跳转包装，以及归档的手柄/自由视角入口；配置和字体/地图/模块相对路径保持不变。该布局不创建目录联接、不修改注册表、不使用本地绝对路径。

所有 814 项既有变化资源（正文、图片、字模、视频字幕、免 CD 及驱动等）和当前自有运行文件一起交付。变化资源来自统一包的源版本绑定，不重跑翻译、不改变播放速度或逻辑频率。当前包含 F10/F11 辅助、四类模型插帧、显示/焦点/高清文字和标题、楼梯/GUI 等已有修正、最新 F5 提示可见后补交候选。手柄/自由视角按当前发布决定保持归档。分辨率缺省 1080P、无边框、30帧、键鼠，不输出维护端个人设置。

F5 提示是否恢复仍待实机，换区崩溃和眼球偶发外突仍未宣称修复；覆盖包是当前测试集合，不是所有问题已完成游戏内验收的声明。

## 离线验证

- 原启动脚本在平铺自有夹具中寻找不存在的 `data/` 并失败；新脚本通过 `--verify-only` 到达自有检查器，不执行商业游戏。
- 自有最小资源夹具验证 ZIP 覆盖、真实 PowerShell 检查器、独立纯净备份回滚、混合版本拒绝与存档/设置保留；另一份覆盖夹具保持修改状态。
- 实际归档回读 CRC/每项 SHA256，并以“纯净版源摘要 + 覆盖文件摘要”虚拟合并核对运行清单的每个依赖，不复制完整游戏。
- 游戏由测试者自行启动，证据在 `build/clean-overlay-evidence/`。

```powershell
python tools/build_clean_overlay.py --previous <统一包ZIP> --previous-sha256 <SHA256> --runtime runtime --output dist/<覆盖包ZIP>
python -m unittest discover -s tests -p test_overlay_bundle.py
python -m unittest discover -s tests -p 'test_configuration*.py'
```

## 原安装路径启动修订

首版覆盖包在注册表 Directory 指向覆盖目录时被原生启动器拒绝：`Original install must not be used as workspace`。脚本平铺布局验证不足以覆盖原生入口；旧 `--verify-only` 在路径检查前返回，产生检查通过、真正启动失败的缺口。

平铺启动脚本现在明确传 `--in-place-overlay`，仅允许已锁定的免 CD EXE 与本地化引擎。模块位于目标 modules、配置与日志位于目标 cache；与注册目录重叠时只接受同一个根目录，祖先/子目录仍拒绝。旧隔离模式的原路径检查保留；机器安装项不写入，临时配置继续由独立 HKCU 会话接管。

`--verify-only` 移至全部无副作用的原生启动预检之后，包含真实目录关系、版本、图形组合、ANSI 路径与52字节配置检查；不启动进程、不创建会话或日志。自有 `overlay_launch_fixture` 调用生产 wmain，只有安装目录读取用确定性替身，注册写入及进程创建有捕获计数。原代码复现同样报错，随后因 verify-only 错误通过而断言失败；修订后显式平铺成功、旧模式拒绝原路径、独立隔离目录通过、父目录/外部日志拒绝，写入/子进程计数均为0。

`tools/build_overlay_launch_repair.py` 为首版覆盖 ZIP 的准确摘要构建仅四个自有文件的小修复：启动器、Start.ps1、runtime.json、Overlay-Manifest.json。不改资源、存档和个人设置。原生启动器能力标记检查进入完整覆盖构建，避免再次搭配不支持平铺参数的旧启动器。完整修正版可重新生成；首版已解压者只需小修复。

### 小修复入口的窗口结果

首版 Fix-Overlay-Launch.cmd 只在失败时 pause，成功 exit=0 后会自动关闭，不能据此称作更新崩溃。修订入口始终显示退出码并等待按键，同时将 PowerShell 完整输出保存为同层 Overlay-Launch-Fix.log。只替换 CMD 不改变更新清单或安装标记，已经安装的原小修复可幂等检查。真实 cmd.exe 的开放输入管道回归确认成功和失败均等到按键才结束，且保留原退出码。
