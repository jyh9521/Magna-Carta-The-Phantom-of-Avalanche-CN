# 原生卡尔塔 Loading 提前呈现候选

2026-10-19。共享 `Play.cmd` 已接入离线候选，实际画面和换区稳定性待人工验收。
不使用自绘占位图，不修改游戏图片、存档、设置、资源加载队列或玩法时钟。
此项不是换区崩溃根治，也不承诺缩短资源读取总时间。

## Verified：资源和触发链

- `FrameData/0204.fdi`（787字节）有15个42字节记录，起点157；前三个有效记录
  `(anchor,x,y,type,id)` 为 `(1,0,0,3,354),(1,128,0,3,355),(1,256,0,3,356)`。
  `BGR/0354.BGR`～`0356.BGR` 各128×128，完整原生组合384×128。
  解码组合与截图黑底右下 `Access in progress...`、卡尔塔系统文字及标志一致。
  翻译计划的 `loading-progress` 只覆盖后两张，256×128不是完整原生布局。
- `MCAlpha+71085` 创建资源 `0xcc`（FDI204），位置为渲染尺寸减 `(365,155)`，
  隐藏场景GUI、清屏、清空绘制批次并更新/绘制原生框架；函数本身不提交屏幕。
- 原生 `6b3bc` 仅在模式 `scene+156c=7` 且 `scene+1730!=0` 时调用该函数。
  场景初始化将1730清零；`71065` 设置1730后转退出模式，普通 `6e36e` 不设置1730。
  原 `631a0` 循环先检查退出，再绘制/提交；`6e697` 退出计数为0或1时立即结束。
- 七个原始指令离线用例验证门控和计数行为；绘制函数以ABI边界代替。

**高置信推断**：普通退出可能未启用原生Loading，且在下一帧绘制前离开循环，
旧画面因而留到同步清理/读取结束。这解释一个呈现缺口；实际卡顿的完整因果链、
耗时分布和崩溃根因仍未验证，不把指令回放当真实换区复现。

## 候选实现与守卫

`src/runtime/native_scene_loading.cpp` 只改写RVA `63075` 的CALL（原字节
`e8 e1 00 00 00`，原目标 `6315b`）。旧作业返回、清理尚未开始时，仅当下一作业
`f2280=1f`（Field）、旧场景虚表 `c12bc`、模式7成立时执行：

1. 验证已安装GUI父节点守卫、GUI/保存控件、驱动、renderer虚表及函数地址，
   原生BeginScene标志必须为0。前置条件不满足则跳过呈现，原清理仍调用一次。
2. 原 `71085(scene)` → Asura `ASRRender(renderer)` → 驱动原Present（虚表+14）。
3. 原 `ASRClearRender()` → 原 `6315b(job)` 清理。

`ASRRender` 遍历CPU队列但不清零计数，故清空已提交批次后再删除框架，避免保留已释放
框架数据引用。此队列不是资源加载队列。异常不吞掉；原清理前恢复LastError。
保护页写入失败会补偿；原作业/加载次序与33ms玩法时钟不变。首启、战斗、标题、
菜单不由此钩子覆盖。GUI/楼梯守卫保留；撤回的 `scene_loading.cpp` 不链接生产DLL。
原生框架构造仍是同步操作；若停顿发生在本钩子之前或构造本身，候选不保证消除该段停顿。

| 输入 | SHA256 | PE timestamp / SizeOfImage |
|---|---|---|
| MCAlpha.dll | `7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e` | `3ed73966 / 10b000` |
| AsrD3DDrv.dll | `00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29` | `3c2b7d28 / 2c000` |
| Asura.dll | `f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557` | `3ed70009 / 74d000` |

安装校验引擎身份、CALL、原函数前缀（SEH按实际基址比较）及资源常量；运行检查
Asura身份/导出RVA `516fd/4e61f`、驱动身份/虚表。入口另校验清单文件摘要，未知输入拒绝。
不提交商业资源或DLL。

## 离线验证

保留现有Win32配置和数据头参数：

```powershell
cmake --build build/native --config Release --target workspace_profile native_scene_loading_fixture
build/native/Release/native_scene_loading_fixture.exe baseline
# exit 1: loading=0 present=0 cleanup=1
build/native/Release/native_scene_loading_fixture.exe modified
# exit 0: original_71085_render_present_clear_cleanup
build/native/Release/native_scene_loading_fixture.exe rollback
# exit 1: original_call=restored
$env:PYTHONPATH="$PWD/runtime/dependencies;$PWD/tools;$PWD/tests"
python tools/replay_native_loading_gate.py --sample runtime/data/MCAlpha.dll --report build/native-loading-gates.json
python -m unittest discover -s tests -p test_native_loading.py
```

自有内存PE/虚表/回调夹具检查执行次序、绕过分支、源漂移拒绝、精确撤回；
**不执行完整原71085函数、不显示真实场景**。原始门控指令回放、图片解码与ABI夹具
是三种独立证据，不等于实际呈现或崩溃修复。基线/回滚的exit1是预期的无Loading结果。

## 入口、人工验收与撤回

复用共享运行目录，无整套游戏副本或新ZIP；旧统一ZIP摘要不变且尚不含此候选。
清单新增 `native_scene_loading={schema:1,enabled:true,module:"native-loading"}`。
安装仅改 `Start.ps1`、`runtime.json` 和新增模块；原角色DLL和baseline配方保留。

由测试者手动启动 `runtime/Play.cmd`，先保存进度；预计3～5分钟，按正常方式退出。
选择可稳定往返的A/B场景，各换区三次，再测菜单、战斗及读档返回：

- 检查清理前是否出现同一套黑底右下原生Loading，无自绘过渡；留意闪屏、残影和位置。
- 记录旧场景停顿、Loading开始/结束时点、地区、方向、存档与崩溃情况。
- 检查楼梯禁入返回、GUI、配置；异常时保留最新日志，不反复覆盖。
- `NATIVE_LOADING_PRESENTED fdi=0204 before=field_cleanup artwork=original` 仅说明
  提交函数返回成功，不证明显示器上的画面；`NATIVE_LOADING_SKIPPED`表示守卫跳过。

独立对照：手动运行 `powershell -NoProfile -File runtime/Start.ps1 -Recipe configured -WithoutNativeLoading`，
只关闭此候选，保留GUI/楼梯守卫。加 `-VerifyOnly` 则仅检查入口，不启动游戏。

```powershell
python tools/integrate_native_loading.py --runtime runtime --module build/native/Release/workspace_profile.dll --record build/native-loading-evidence/integration-final
# 已安装则拒绝重复覆盖，保留事务记录。
python tools/integrate_native_loading.py --rollback build/native-loading-evidence/integration-final
```

本地 `integration-final/changes.json` 与 `original/` 保存原控制文件和前后摘要。
回滚先验证候选及备份未漂移，再逐字节恢复入口/清单、移除候选模块，不触碰存档/设置。
小型自有副本另行验证回滚，不复制游戏。证据位于 `build/native-loading-evidence/VERIFICATION.txt`。
