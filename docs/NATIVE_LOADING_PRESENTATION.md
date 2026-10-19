# 原生卡尔塔 Loading 正常帧候选

2026-10-19第二轮。共享 `Play.cmd` 继续使用原生卡尔塔界面，不插入截图或自绘图。
旧的清理前独立呈现路线已替换。实际修正效果仍待人工复测，不宣称换区崩溃已根治。

## 玩家反馈与失败路线

玩家实际观察：去新场景 → 黑屏 → 旧场景重新亮起 → Loading一闪 → 新场景；本轮未崩溃。
最新本地日志存在多条旧 `NATIVE_LOADING_PRESENTED`，证明候选分支到达，
不证明显示器上呈现顺序正确。旧夹具只检查函数调用顺序，遗漏了完整原生帧的状态与门控。

**Verified**：旧候选在 `63075` 清理CALL前直接调用 `71085`、Render、Present、ClearRender；
正常帧仍未设置 `scene+1730`。这增加了一个脱离正常帧的独立提交，且位于原帧末尾之后。
正常 `631a0` 帧不仅提交图像，还包含白色光照、矩阵重置、深度状态、GUI绘制与白色颜色恢复。
**高置信推断**：未启用正常Loading门控，加上末尾额外提交与继承的渲染状态，造成时序和回闪异常。
尚未离线重现真实像素，不能把这个结构性缺陷称为五步画面现象的完整因果证明。

## Verified：资源和正常帧调用链

- `FrameData/0204.fdi`（787字节）有15个42字节记录，起点157。前三个有效记录
  `(anchor,x,y,type,id)` 为 `(1,0,0,3,354),(1,128,0,3,355),(1,256,0,3,356)`。
  `BGR/0354.BGR`～`0356.BGR` 各128×128，完整组合384×128；解码匹配玩家截图。
  翻译计划 `loading-progress` 只覆盖后两张，不代表整个原生布局。
- `631a0`：退出检查 → 清屏/清队列 → `0cdc4` 原固定更新 → `631da CALL 63322`
  → 原场景绘制 → 世界Render → 矩阵/深度/GUI/颜色恢复 → UI Render → 帧尾 → 原Present。
- `63322 → scene虚表+10 → 02b60 → scene虚表+c → 6b3bc`。
  `6b3bc` 先绘制世界根，仅在未暂停、模式7且 `scene+1730!=0` 时执行 `71085`。
- `71085` 隐藏旧GUI、清屏/清队列、构造并绘制FDI204；定位为渲染尺寸减 `(365,155)`。
  原生Loading进入同一帧，世界根的旧队列被清掉；随后继续原GUI和提交流程。
- 场景初始化将1730清零；普通 `6e36e` 转模式7但不置位，专门入口 `71065` 则置位。
  `6e697` 在下一轮检查退出计数；当前修正不修改其计数或返回值。

## 当前改动：只启用原生门控

`src/runtime/native_scene_loading.cpp` 替换 **RVA631da** 的5字节CALL：
`e8 43 01 00 00`，原目标 `63322`。在原固定更新之后、原绘制之前检查：

1. 待处理作业 `f2280=1f`（下一Field），旧场景虚表为 `c12bc`，模式7，1730当前为0。
2. 已安装原GUI父节点守卫，原GUI/保存控件及所需布局有效。
3. 只写 `scene+1730=1`，然后调用原 `63322(job)` 一次；既有非零标志不覆盖。

不再直接调用71085、Render、Present或ClearRender；不在帧尾补画。
`63075 CALL 6315b` 清理原字节必须完整；检测到旧钩子或外来改动时安装拒绝。
所有像素、淡出、UI状态和提交继续由游戏原生帧处理，33ms逻辑时钟、更新次数、
退出计数和加载/清理次序不改；没有Sleep或人为延长Loading。
原生门控已经开启的路线保留；战斗、标题、菜单、新场景首启不由此候选改变。
如果进入模式7前已离开正常帧，或者守卫跳过，这个绘制点不覆盖该路径。

引擎SHA256：`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
安装检查PE32身份 `3ed73966/10b000`、新CALL、原清理CALL、71085前缀（SEH按实际基址比较）
和资源常量 `71136:68cc000000`；共享入口还校验文件摘要。未知输入拒绝。
原生资源不修改、不提交；不再依赖候选代码直接调用驱动或Asura导出。

## 离线证据和边界

新增回归夹具先在旧生产代码上失败：
`FAIL loading flag must be armed BEFORE original draw, not after cleanup`，exit5。
修正后在同一原CALL位置运行生产包装器，检查门控先于原绘制、清理CALL不变、
旁路、既有标志、LastError和精确撤回。

`tools/replay_native_loading_frame.py` 执行原631a0/63322/02b60/6b3bc/退出检查指令：
原flag0无Loading；置位后原71085边界先于正常Present；三态均只有一次原时钟调用和正常提交（不计实际逻辑子步）。
固定更新、绘制后端和置位用明确ABI边界，置位逻辑另由生产C++夹具验证。
**不执行完整71085、真实资源解码、并发任务或GPU绘制；不把这些结果当成像素验收。**

```powershell
cmake --build build/native --config Release --target workspace_profile native_scene_loading_fixture
build/native/Release/native_scene_loading_fixture.exe baseline  # exit1：原门控为0
build/native/Release/native_scene_loading_fixture.exe modified  # exit0：绘制前置位，无独立提交
build/native/Release/native_scene_loading_fixture.exe rollback  # exit1：原门控/绘制CALL恢复
$env:PYTHONPATH="$PWD/runtime/dependencies;$PWD/tools;$PWD/tests"
python tools/replay_native_loading_frame.py --sample runtime/data/MCAlpha.dll --report build/native-loading-frame.json
python -m unittest discover -s tests -p test_native_loading.py
```

## 人工复测、入口与回滚

由测试者手动启动现有 `runtime/Play.cmd`，预计3～5分钟，正常退出；不需另启动fixture。
同一A/B场景各往返三次，目标为原生Loading出现在旧场景清理/新场景读取之前，
期间不再闪回旧场景；记录黑屏、Loading首帧/末帧、闪屏和残影。
不人为保证最短显示时间，快速读取时显示很短本身不判失败；重点是不回闪旧场景。
随后检查菜单/战斗/读档、楼梯禁入返回和GUI。异常时保留最新日志，勿覆盖存档证据。

新日志为 `NATIVE_LOADING_ARMED flag=1730 before=native_draw standalone_present=false`，
只证明原门控置位，不证明实际像素；旧 `NATIVE_LOADING_PRESENTED` 不应出现在新会话。
独立对照：手动运行 `powershell -NoProfile -File runtime/Start.ps1 -Recipe configured -WithoutNativeLoading`，
保留GUI/楼梯守卫；加 `-VerifyOnly` 只检查入口，不启动游戏。

本轮仅替换共享候选模块与清单，复用原数据、入口、基线与旧ZIP；无游戏副本或新ZIP。
完整撤回记录为本地 `build/native-loading-order-evidence/integration-verified`：

```powershell
python tools/integrate_native_loading.py --rollback build/native-loading-order-evidence/integration-verified
```

此命令在游戏退出后使用，验证候选/备份摘要后恢复原入口/清单、移除候选模块；
存档和设置不动，下一次手动启动使用原门控。新事务以原始无Loading候选基线为起点，
不是把已反馈异常的上一版重新设为默认。旧模块/源码/玩家日志仅在本地证据目录保留。
验证记录、修改文件、差异和可执行回滚脚本均在 `build/native-loading-order-evidence/`。
