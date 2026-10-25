# 统一玩家测试补丁包

> 当前发行：Release v1.0 已发布；2026-10-25 收到完整流程通关、测试无误的验收反馈。正式入口为 `Configure.exe` / `Game.exe`。以下日期化调查与测试包记录保留历史证据，旧待验收状态不代表 v1.0 发布状态；专项未独立采样的结论仍保留原证据边界。现行用法见 [v1.0 发布说明](RELEASE_V1.0.md)。

2026-10-22更新。打包共享运行目录当前候选，不再要求玩家串联历史汉化包和免CD包。

## 实现

- 构建时核验`runtime.json`所有数据与运行组件摘要；原版与共享数据逐文件比对。
- 原始商业资源仅以差异交付。MCD1格式为4字节标记、uint64目标长度，随后重复
  uint64偏移、uint32长度、literal数据；均为小端，块长最多4096字节，偏移有序。
  相同块从玩家原版保留，最终校验完整SHA-256。EXE免CD仍为已记录的0x1025分支变化。
- 包含正常驱动增量、DDrawCompat v0.7.1（原许可随包）、当前汉化及高清标题资源增量，
  自有共享模块、Material风格配置工具、动作/手柄/自由视角/地图/纹理独立配方。
- 原版11784文件摘要预检后，仅向新目录的`.assembling`副本写入；完成后重命名。
  失败不发布半成品目标，保留assembling目录供调查；重新安装应使用另一全新路径。
- 不捆绑原版完整EXE/DLL、商业媒体、旧存档或Python。Logo、名单维持原字节。
  发行设置固定为1080p、无边框、30帧、键鼠、自由视角关闭、窗口1280×720；
  不导出维护端个人设置，也不改维护端配置。安装后的可变设置不纳入运行时不可变摘要。

## 安装与恢复

包内`Install.cmd`提示输入原版目录，也支持`-Source`及`-Target`。
默认在包目录上一级创建`MagnaCarta-PlayerTest`。`Configure.cmd`与`Play*.cmd`均位于
新副本根目录，读取同一`data`和存档。原安装不写入。

`-Action Verify`核验原版、补丁与组件；`-Action CheckInstalled`核验已安装资源；
`-Action Rollback`预检全部已修改资源，再从原版恢复813份资源，保留存档/设置/自有工具。
回滚后现代化入口按原有版本守卫拒绝不匹配EXE，恢复原安装可直接作原版对照。

## 证据边界

自动安装、摘要检查、原生入口VerifyOnly、独立回滚与合成夹具属于文件/受控验证。
实际游戏未由本打包流程启动；玩家检查中文排版、无介质新游戏/读档/媒体、窗口、
60帧节奏、实体手柄、自由视角、地图及纹理候选。固定配方不必然读取保存的显示设置。
独立纹理修复通过`Play-texture.cmd`启用，该修复尚未在默认配置中合并。

## 正常入口整合楼梯候选（2026-10-19）

Play/Configure及非baseline配方默认开启限定0757/event2的返回高度修正，不另换入口。
打包器拒绝旧独立楼梯入口，记录 `engine_fixes.field_return_height.default_enabled=true`
和 `in_game_verified=false`。原8份模块、baseline、存档、设置保留。
维护开关 `Start.ps1 -WithoutFieldReturnHeight` 沿用保存设置、恢复原模块路由，
与Install Rollback的“全资源恢复原版”不同。用户正常推进至该事件再验收。
详见[触发链与整合事务](STAIRWELL_RETURN_HEIGHT.md)。

## 2026-10-22 测试发行

包含当前战斗菜单宽屏资源选择、图片结构与拼接标题、高清字模输出门控修正，
以及原生Loading候选；来源见[BATTLE_MENU_WIDTH_ASSERTION.md](BATTLE_MENU_WIDTH_ASSERTION.md)、
[IMAGE_INTEGRITY_REPAIR.md](IMAGE_INTEGRITY_REPAIR.md)与[SCALED_FONT_COVERAGE.md](SCALED_FONT_COVERAGE.md)。
场景切换崩溃和60帧眼球偶发外突仍未确认解决，不能作为正式全流程通过版。
重点人工复验最近存档至下水道入口及首次战斗，保留设置、日志、截图和问题时间。
构建仍使用`tools/build_player_test_bundle.py --source ORIGINAL --runtime runtime --output dist/NEW_NAME`。
离线安装器回归使用`python -m unittest discover -s tests -p "test_player*.py"`；
新增合成完整打包检查确保发行默认值、载荷摘要一致且维护端设置原样保留。
