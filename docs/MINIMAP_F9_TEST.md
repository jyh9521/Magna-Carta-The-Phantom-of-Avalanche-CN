# F9 小地图与全屏半透明地图测试版

2026-10-25。本页记录新增地图功能的源码、构建与人工验收流程。
正式 v1.0、发行 ZIP 与安装包不随本轮测试功能更新；部署结果以实际部署记录为准。
历史 [地图候选](MAP_OVERLAY_CANDIDATE.md) 的 F8/F9 双键说明不适用于本页版本。

## 操作与显示

- 初始关闭，F9 每次有效按下依次切换：**小地图 → 全屏半透明地图 → 关闭**。
- 小地图位于左上角，玩家保持居中；可视范围约为 240 世界单位，受地图采样范围限制。
- 全屏模式覆盖游戏客户区，地形保持等比缩放，不拉伸成宽屏比例。背景色键为
  `RGB(19,32,39)`，背景透出游戏画面；线条、图例和标记使用 `150/255` 的统一不透明度。
- 图层不暂停游戏、不抢前台、不接收鼠标点击；F8 保留原输入语义，不再切换地图。
- 长按不连续切换。输入桥缓存 F9 消息按下沿，避免两次界面刷新之间的短按丢失；
  失焦或无有效探索快照时丢弃待处理按下沿，重新取得控制后先松键再触发。
- 菜单、战斗、场景转换、标题与失焦期间隐藏图层；新有效区域快照到达后读取对应资产，
  不使用过期场景点或上一张图代替缺失地图。

## 地图与实时对象

**已验证的离线数据：** 当前源资源集为 176 份 WRD，174 份完成解析、第一帧实例变换
和 `feature-edges` 线稿生成。原坐标包围框、比例与 MCM1 元数据保持不变。
线稿保留边界、折边与高度变化轮廓，减少共面三角形内边；不再用上层实体填色遮住下层轮廓。

地图观察器在原世界更新后只读玩家位置、方向、活动 NPC 与箱体对象。
橙箭头表示玩家，绿点表示实时 NPC，紫色实方表示尚未消耗的容器互动，NPC 金圈表示
原生记录中尚未领取的道具奖励，黄线表示当前会话的最近移动轨迹。已消耗的容器不再显示；
状态未辨明的箱体只画空框，不宣称可收集。领取状态来自原生开关表，不使用模型是否仍存在代替。
背包满也可能消耗原交互，因此隐藏标记不保证物品成功入包。已核实类型与范围见
[可收集物只读证据](MAP_POINTS_RESEARCH.md)。轨迹不写入存档。观察器继续核对场景、玩家所属对象及
地图资源标识，失效或超过有效期限的快照不参与绘制。

方向读取不是移动轨迹的估算：原生 `653c6/655a1` 更新 `actor+104` 的转角后，
`59e29` 刷新方向向量 `+148/+14c/+150`。箭头使用其 XY 分量并对屏幕 Y 轴取反，
原地转身也随方向更新；投影不修改原生坐标。

0084、0096 仍触发解析器索引边界检查，明确拒绝生成；不丢弃异常三角形来伪造完整覆盖。
这些拒绝不等同于原游戏资源损坏，详见 [旧版 WRD 覆盖](MAP_LEGACY_GEOMETRY.md)。
多层几何仍叠合，线稿不是自动楼层分离、碰撞图、可通行路线或跨区域世界地图；
任务点、路径规划、已探索遮罩与动画平台更新均不由本功能推断。

换区口另从 Field 的区域条件 304 与转场动作 4/5 提取，不按黑色贴图猜测。
565 个完整解析场景生成 379 个候选换区点，其中 182 个场景包含标记，383 个场景无此类标记；
32 个未完整解析场景不生成出口数据。青色菱形表示换区触发区域的中心；额外剧情条件、
多目标动作或有限执行次数以空心菱形表示，未执行原生剧情条件，不承诺当前必能通行。
按当前 Field、WRD 和玩家 actor 标识共同筛选，同一地形的另一剧情场景不混用出口。
格式、原生条件/转场回放及完整边界见 [出口标记证据](MAP_EXIT_POINTS.md)。

## 可重复构建

在仓库根目录执行，复用现有 Win32 构建配置和生成头文件；完整准备方式见
[共享运行布局](SHARED_RUNTIME_LAYOUT.md)。以下命令不启动游戏。

```powershell
cmake --build build/native --config Release --target workspace_profile map_overlay_fixture map_collectibles_fixture modern_gamepad_fixture
$env:PYTHONPATH="$PWD/runtime/dependencies"
python tools/build_map_atlas.py --source runtime/data/MAP --output build/map-f9-atlas --size 2048 --style feature-edges --labels locales/zh-CN/map-ui.json
python tools/build_map_points.py --source runtime/data/Field --engine runtime/data/MCAlpha.dll --output build/map-f9-atlas/points
```

地图输出必须是全新目录，位于原始地图目录之外。构建清单记录原 WRD、PNG 和 MCM1 的
SHA-256，源资源在构建结束时重新核对；未知格式继续拒绝。默认 `solid` 样式保留，
只有显式 `--style feature-edges` 才生成线稿，既有高度剖切参数不被隐式开启。

`--labels` 从 locale JSON 生成 `label.txt`、`legend.txt`、`hint.txt`，编码为 UTF-16LE、无 BOM。
清单 `labels` 记录 JSON 源 SHA-256、编码与生成文件摘要，不记录本机绝对路径。
标题为必填字段，图例与提示可选；字段须非空、最多 255 个 UTF-16 代码单元，拒绝 NUL、
换行、重复键与未知字段。通用渲染器不硬编码中文，省略 `--labels` 时保持原有仅生成地形的行为。
部署仍要求 `label.txt`，图例、提示作为可选 locale 资产进入部署摘要清单。
旧 atlas 缺少提示时仍可加载，但不会因此改变地图坐标或自动补入中文文字。

## 测试版部署与撤回

仅更新现有测试运行目录，不创建完整游戏副本。退出游戏和启动器后执行：

```powershell
python tools/deploy_minimap.py apply --runtime runtime --native build/native/Release/workspace_profile.dll --atlas build/map-f9-atlas --record runtime/maintenance/map-f9-deployment
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -Recipe configured -VerifyOnly
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -Recipe maps -VerifyOnly
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -Recipe baseline -VerifyOnly
```

部署器校验已有运行清单、源 WRD/Field/引擎摘要、坐标投影和新 Win32 模块标记，保留每个变化文件的
原字节及前后摘要，并读回校验。记录目录必须全新；平铺测试布局的记录须位于运行目录之外。
发生未知摘要、已有未登记目标或后续改动时停止，不覆盖成另一版本。

新清单字段为 `map_overlay={schema:1,enabled:true,module:"minimap"}`。
`configured` 与 `maps` 入口使用当前完整构建的 `modules/minimap.dll`，保留原有显示、
字体、场景和其它修复开关；`baseline` 不启用地图。原手柄与自由视角撤回状态不变。
无此字段的旧运行清单保留原路由，当前配置和存档不被重新初始化。

撤回使用同一份记录，先核对当前载荷与备份摘要，再恢复原文件并移除本次新增文件：

```powershell
python tools/deploy_minimap.py rollback --runtime runtime --record runtime/maintenance/map-f9-deployment
```

重新构建完整共享运行包时，`prepare_shared_runtime.py` 的原有参数可追加
`--minimap build/native/Release/workspace_profile.dll`。新地图路由要求非空、摘要匹配的 atlas；
地图资产随小型运行包复制，原游戏数据不复制。部署记录、源码基线与输入摘要保留用于回滚。

## 离线检查与人工验收

```powershell
build/native/Release/map_overlay_fixture.exe --cycle-self-test
build/native/Release/modern_gamepad_fixture.exe --map-edge
build/native/Release/map_collectibles_fixture.exe
build/native/Release/map_overlay_fixture.exe build/map-f9-atlas build/map-f9-mini.png --mini
build/native/Release/map_overlay_fixture.exe build/map-f9-atlas build/map-f9-full.png --full
python -m unittest discover -s tests -p test_map_f9_native.py -v
python -m unittest discover -s tests -p test_map_feature_edges.py -v
python -m unittest discover -s tests -p "test_map_points*.py" -v
python -m unittest discover -s tests -p test_minimap_entry.py -v
python -m unittest discover -s tests -p test_minimap_deployment.py -v
```

原生夹具使用自有位置与对象，输出生产绘制路径的离屏 PNG；PNG 不是游戏截图。
离线测试覆盖状态循环、全客户区布局、透明度、点击穿透、资产坐标、入口路由及部署撤回，
不替代真实全屏合成、实际人物与地形对齐或完整剧情切换验收。

完成预检后，通过测试运行目录的正常游戏入口手动启动：

1. 进入探索区域，短按 F9 三次，核对小地图、全屏半透明地图、关闭的顺序；长按只切一次。
2. 沿直路和转角移动、原地转身，检查箭头朝向；移动 NPC 的绿点应实时跟随，领取箱体或 NPC 道具后检查对应标记变化。
3. 全屏图打开时确认场景仍可见，移动和鼠标点击保持正常，F8 不切换地图。
4. 打开菜单、进入战斗、切区、读档及返回标题，确认不残留旧场景图或旧位置。
5. 切到其它程序时确认地图隐藏；返回后松开按键，再验证 F9 顺序与短按响应。
6. 在黑色贴图旁检查青色换区菱形；触发后确认新场景出口重新加载，空心标记不视为已解除剧情条件。

异常反馈保留区域编号、位置、窗口模式、截图及本次 `profile.log`。
就绪标记包括 `MAP_F9_CYCLE_V1`，实际状态变化记录为 `MAP_OVERLAY_MODE mini/full/off`。
实际画面通过前，本功能保持测试版状态，不计入正式 v1.0 的既有通关验收。
