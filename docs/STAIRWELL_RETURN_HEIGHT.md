# 总部楼梯：触发逻辑与返回高度候选（2026-10-19）

## 当前结论

已定位 `0751 → 0757` 的总部走廊／地下牢梯间，以及0757的下层退回事件。
已在原生指令回放中验证一个确定的坐标写回问题，并实现限定事件的修正。
按用户要求，修正已整合至正常Play.cmd、配置工具启动及统一测试包，不另换入口。
原8份模块和Play-baseline.cmd保留；游戏资源、翻译、配置与存档不因本修正改变。

**此轮没有复现实际游戏软锁。** 回放不运行碰撞与真实对话输入：原版和候选均能走到原生
解锁命令，不能以“新测试通过”声称实际软锁已经根治。用户没有故障存档，未要求其提前游玩；
后续正常流程走到此处时再完成实机验收。正常入口默认加载此候选，但这不代表游戏内软锁已验收。

## Verified：来源与触发

- 原始CD1 InstallShield资源 `Field/0757.fld`：3796字节，SHA256
  `7b92ac0c7fe82aa2d63761c6442ff40f43c0b947644e4f03ea3b48e868b91a87`。
- 当前0757：`13d92e10cddf9bb490bbcfd76c81cf6b7c90b12afebc34a7dd1ba3fd6dff21cf`；
  仅显示标签与光盘不同，事件尾部完全相同。提供的MCV104a.exe无0757/0751载荷。
- 固定Nejuf/magnacarta `9ce77cace0d717f5ad75bb2910517802e55932c8` 无Field修改。
  此事件解码与原生分析不是引用英文补丁的一项既有修复。
- 0751使用WRD13／FPB0723；0757使用WRD17／FPB0729。0751出口转场指向0757。
- 原生加载器RVA `65f90` 记录Field ID，`4ab93`读取动态事件；597份Field中565份
  同时满足已有静态前缀与完整事件尾部EOF检查。其余不自动判为损坏。

0757事件2：文件 `0xC28`，重复次数限制0（不限制），条件位于 `0xC30`：
`304(10000,1)`。`71af6 → 727e6`将角色0的位置加身体高度，对region1的六面逐一测试。
不是根据摄像机或楼梯贴图触发。

| 文件偏移 | 命令 | 经原生代码核实的行为 |
|---|---|---|
| 0xC70 | 7 | `72bc9 → 6e4b1`，增加剧情控制锁计数，首次切入模式6 |
| 0xCAC | 202(10000,5,1) | 角色0向marker5建立XYZ、速度1的原生位置插值 |
| 0xCE8 | 1 | 等待本事件异步命令计数归零 |
| 0xD24 | 700 | 显示FPB0729/tag1的禁止进入提示；该文本确实存在 |
| 0xD60 | 1 | 等待对话命令完成 |
| 0xD9C | 8 | `72bfe → 6e4f4`，减少原锁计数，满足条件时回探索模式2 |

没有“缺少末尾解锁命令”的证据。事件3的502/515/701是另一个独立事件，不属于退回动作。
不删除禁入条件、不修改剧情开关、不强制归零锁计数、不改存档。

## Verified：原生XYZ写回问题

分析引擎SHA256 `7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。

`7591c`读取202第三参数：等于1时用marker的完整XYZ调用`4f989`，否则保持角色当前Z。
`4fdea / 4fb87 / 4fc9b`正常推进插值；完成判断`4fb52 / 125f0`比较三个分量。
但每次写角色位置前，`75BEB–75BEE`又无条件用角色旧Z覆盖插值结果的Z，随后
`75C0A`调用`5a773`写回XYZ。因此“插值内部到达目标”与“角色到达完整目标”不同。

marker5坐标约为 `(250.237, -442.234, -96)`。使用WRD17真实水平踏步的两个重心作为
自有回放的初始坐标，执行原生调度、202与插值：

| 输入Z | 原版写回Z | 候选写回Z | 原生锁计数／探索模式 |
|---:|---:|---:|---|
| -116.422699 | -116.422699 | -96 | 两者均0／2 |
| -121.447800 | -121.447800 | -96 | 两者均0／2 |

此模型明确省略真实碰撞／落地、动画资源和UI。对话用“已完成”边界桩代替，该模型不足以排除
真实游戏的碰撞或对话死锁。原版在该模型并不死锁；测试失败信号是**XYZ写回不匹配**，不是伪造的卡死。

返回XY的竖线查全可视几何得到三面：mesh0/triangle17水平Z=-101.347295、
mesh6/triangle17水平Z=-101.492502，另有向下斜面mesh10/triangle0。
旧Z=-116.422699低于两水平面约15，而目标-96在其上约5。
这是可视几何失配证据，不是已运行原生碰撞判定的证明。

## High-confidence deduction / 尚待实机

在楼梯退回时丢失XYZ中的高度，有把人物留在踏步下方的风险，是该外部软锁报告的
候选原因。真正的碰撞恢复、对话出现及消失、操作恢复与反复进出仍待实际游玩。
不能把“第三参1比较少见”单独当作根因；改成0并未解决完整返回坐标问题，未采用。

## 候选范围与正常基线

`field_return_height.cpp`仅替换202内部的一个位置写回CALL（RVA75C0A）；未改游戏磁盘DLL。
源锁启动器先核整文件SHA；运行时再核PE32/I386/映像大小、CALL原字节与函数指令前缀。
设置`MC_FIELD_RETURN_HEIGHT=1`才安装；未知目标或冲突拒绝，不静默跳过。

每次调用还必须同时满足：0757场景、玩家角色0、事件2、原生对象类型、唯一活动202命令、
精确参数指针、完整六命令FNV `B82B40D0`、原条件、marker5与插值目标逐字节一致、有限坐标。
只把本次插值Z传给原生位置写回，其余输入全部透传。其他区域、其他事件、二维移动、
剧情开关、完成判断和原生锁计数不动；日志最多8条实际修正记录。
原生场景在68BC1分配150个命令槽；夹具及回放使用该容量，扫描保留原循环的最后保留槽边界。

正常Play/Configure启动及非baseline配方统一加载 `modules/field-return-height.dll`，
设置 `MC_FIELD_RETURN_HEIGHT=1`；baseline保持原display模块、环境开关0。
原8份角色DLL逐字节保留，旧独立楼梯入口已撤回。

## 构建、整合与恢复

```powershell
# 仅历史独立试用迁移需要先恢复旧记录：
python tools/prepare_field_return_trial.py --rollback out/stairwell-return-height-20261019
# 干净基线整合到现有入口；record必须全新且位于runtime之外：
python tools/integrate_field_return.py --runtime runtime --module build/native/Release/workspace_profile.dll --record out/stairwell-default-integration-20261019
powershell -NoProfile -File runtime/Start.ps1 -VerifyOnly
powershell -NoProfile -File runtime/Start.ps1 -Recipe baseline -VerifyOnly
# 维护用临时关闭，不新建入口，不改保存设置：
powershell -NoProfile -File runtime/Start.ps1 -WithoutFieldReturnHeight -VerifyOnly
# 完整恢复原启动脚本/清单，撤回新增DLL：
python tools/integrate_field_return.py --rollback out/stairwell-default-integration-20261019
```

整合器核验原启动脚本版本、全部组件摘要及新输出路径，保存两份控制文件原件和三项摘要记录。
回滚先核全部当前文件与原件，任一漂移拒绝整批写入；写失败补偿至事务前状态。
可变设置、存档和原模块不覆盖。历史独立试用工具仅供旧记录恢复，不用于新包。
干净重建共享目录时，`prepare_shared_runtime.py --field-return-height DLL` 写入相同默认路由。
统一打包器要求该元数据/组件/路由，拒绝旧的独立楼梯入口。统一包保留原版资源回滚。
游戏内验收等待玩家正常进度，本轮不启动游戏。

## 自动验证

```powershell
# 先按BUILDING.md配置Win32本地构建，保留已有字体/开场生成头。
cmake --build build/native --config Release --target workspace_profile field_return_height_fixture
build/native/Release/field_return_height_fixture.exe --baseline  # 预期exit1，旧Z不匹配
build/native/Release/field_return_height_fixture.exe             # 合成CALL现场、作用域与回滚
build/native/Release/field_return_height_fixture.exe --image runtime/data/MCAlpha.dll
python tools/replay_native_field_return.py --sample runtime/data/MCAlpha.dll --field runtime/data/Field/0757.fld --report build/NEW-baseline.json
python tools/replay_native_field_return.py --sample runtime/data/MCAlpha.dll --field runtime/data/Field/0757.fld --candidate --report build/NEW-candidate.json
python -m unittest discover -s tests -p 'test_field_return*.py'
python -m unittest discover -s tests -p test_resource_field_script.py
```

真实DLL测试只以`DONT_RESOLVE_DLL_REFERENCES`映射，不执行商业入口；检查真实PE分页布局下
CALL安装和精确恢复。合成CALL夹具实际执行相同RVA的调用槽，覆盖ECX、三float参数和栈清理，
不是只直接调用辅助函数。两者与Unicorn原生命令回放互补，仍不是商业游戏已触发修正的记录。

正常流程人工验收：从走廊进入楼梯，走到下层禁入区；应平滑退回并显示原提示，关闭后可移动、
打开菜单、返回走廊。反复触发、绕边接近和重新进入都检查一次；观察日志是否有
`FIELD_RETURN_HEIGHT_APPLIED`。现有baseline配方或维护开关为OFF对照，不要求玩家修改进度或存档。

## 本地研究证据与来源

忽略目录`build/stairwell-research/`保留资源、几何、选择性CD解压和比较报告。
CD比较依据twogood/unshield固定`feaa32f6227fb306a87f4249a6618aa2ddd49966`的容器布局
独立编写；仅读取两份成员共1744压缩字节，解压后分别核HDR中的MD5，未运行安装器。
未复制上游源码，不分发完整游戏资源。

REA记录：加载器`ev_b8cec24e5fb02126fa22bf482c98bfd40d0a3c60eefa3238345326dd3c1005c5`；
脚本读取`ev_96eaca45a46facb66c3914c52224bf837ed93a71e106ca23f72dcb49ba77950b`；
202`ev_17f2d6750b2d92e3063a524a4e96c1864914a9dbf230f58f8d4418e972fe8631`；
区域条件`ev_f7595fbad1ab35b4ac5bb1a4d5ed166fe26bab7b31becacc7d735552380497e7`。
完整记录导出在`build/stairwell-fix-evidence/rea-evidence-complete.json`，反编译文本不是原始源代码。
