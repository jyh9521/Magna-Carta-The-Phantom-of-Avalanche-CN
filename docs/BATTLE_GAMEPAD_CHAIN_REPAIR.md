# 战斗手柄真实输入链修正（2026-10-23）

## 输入与验证边界

沿用共享运行目录，不启动游戏、设置程序或游戏 DLL 入口。运行样本为
`MCAlpha.dll`，SHA256
`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
自有 Win32 夹具编译生产输入实现，XInput/前台状态由可复现采样代入；
原生 x86 指令在 Unicorn 中执行。实体手柄、渲染与完整剧情仍由玩家验收。

## 已验证根因

上一版把战斗视作单一输入上下文：A 恒为空格，B/Start 恒为 Esc，并关闭整场
战斗的菜单聚焦。原生场景不接受这些键作为所有子菜单的统一操作接口。

- 场景构造函数 RVA `9D424` 写入虚表 `C1960`。
- 场景 `+10FC` 指向战斗 GUI；真实构造函数 `AE3D0` 在 `AE411` 写入
  `C203C`，`+1BC` 回指场景，`+190` 保存当前模式。
- 原生输入 `2F95` 更新按键计数；`55134` 分发键盘；`557EE` 分发鼠标；
  GUI 经 `AF867`/`AF9C2` 和 `A2F7A` 到达场景处理分支。
- 模式 1 的空格进入 `A3258`/`A3681`。Esc 不会代替取消/开菜单；
  真正入口为右键释放事件 `40` → `A31E7` → `A9025(scene,14)`，
  最终写入 `scene+1980=14`。旧生产 B 采样回放后该值仍为 0。
- 命令菜单模式 4、能力菜单模式 5 和物品菜单模式 6 需要原生控件命中、按下与释放通知，
  单纯发送空格不会产生按钮 `47`/`48` 及对应控件 ID。
  模式 7 是结果菜单，不应误命名为蓄力态；保留原生空格确认接口。
- 模式 4 的 B 在画布中心、未命中按钮时，经真实菜单容器的原生右键释放
  通知写入 `scene+1980=5`，旧 Esc 路由保持 0；不借用不可见的 F8 子节点。

默认基类构造把 GUI 设为 mouse-only，不代表最终交互态；原生 `55BFB`
负责激活键盘。回放执行实际激活、可见/启用、独占栈及子节点优先规则，
不把 `565D2` 强制改成恒真来凑出通过结果。

## 原生未实现分支

模式 6 的物品菜单构造确实使用 ID `123`（`AEBDB → 5E260 → AEC42`），
但当前样本的 `AF867` 只分发 `F8..10C`，场景 `A2F7A` 也没有模式 6 分支。
离线空物品菜单三态均不推进；不能因 LMB 映射通过就宣称该原生占位分支可用，
也不把其 ID 改成能力菜单来伪造成功。输入层保持原生控件链，不新增物品功能。

## 资源与命中矩形

原生 FDI 加载器 `B5C64`、布局 `4D7B9` 和 BGR 构造 `422F0` 生成实际
控件结构。FDI 的尺寸不能直接当作命中矩形：按钮 EE/2B/35 的矩形标记为
0，点击区域来自 active/clickable 的装饰节点与 BGR 411/220/228。
原生 `32457` 读取包装 offset 4 的数量及 offset 8 的 count×16 字节 XYXY。
GPU 创建与外部系统调用采用具名契约桩，原生布局、资格判断、点击分发、
事件监听和结果字段写入保留实际指令。报告列明桩与输入摘要。

## 修正原则

生产输入按经过构造指令校验的 GUI 模式分流；字段/结果确认保留原生按键，
菜单确认沿用鼠标控件链，B/Start 使用原生右键语义。方向聚焦只选择实际
可见、启用、获准接收输入的原生命中区域，不直接调用场景成功分支。

切换上下文时抑制持续按住的语义键，保留新按下沿；断开、换设备、失焦或
上下文切换取消自有鼠标按压，不制造释放确认。物理键鼠状态不被覆盖。
未知上下文不合成战斗操作。连击窗口与固定逻辑周期不变。

## 可复现构建

复用已配置的 Win32 构建及生成头：

```powershell
cmake --build build/native --config Release --target workspace_profile battle_gamepad_chain_fixture battle_gamepad_focus_fixture modern_gamepad_fixture gamepad_ui_fixture world_gamepad_fixture
```

`battle_gamepad_chain_fixture MODE` 输出实际生产输入的逐帧采样；
`battle_gamepad_focus_fixture` 从 stdin 接收原生构造/布局导出的 GUI 结构与
矩形，执行生产 `navigate()`，不使用 Python 重写聚焦算法。

## 从仓库重建全部回放输入

不能依赖本机遗留的临时源码目录。仓库内的准备器固定读取已审计基线提交
`dc742e8bf21e7ec953d1d816a9502794d445dc67`，校验共同源码/头文件没有漂移，
在新的输出目录编译基线、修改、隔离回滚三个自有 Win32 阶段并生成六种模式采样。
不复制游戏文件。需要 Windows x86 C++ 工具链、CMake，以及既有 Python PE/Unicorn 依赖。
CMake 未加入 PATH 时显式传 `--cmake` 和已安装的 CMake 可执行文件路径。

```powershell
python tools/prepare_battle_gamepad_replay.py --output build/battle-gamepad-repro
python tools/replay_battle_gamepad.py --sample runtime/data/MCAlpha.dll --values runtime/data/ValueData/0001.val --data runtime/data --trace-dir build/battle-gamepad-repro --bridge-dir build/battle-gamepad-repro --report build/battle-gamepad-repro/native-chain.json
```

原生回放共 68 项断言，覆盖 800×600 与 1067×600 逻辑画布、三阶段、真实菜单
命中/返回/选择、角色朝向/连击和结果确认。每项记录采样、资源摘要、源/桥接模块
摘要、原生字段结果及 GPU/音频/角色内容等具名边界。修改态成功、基线与回滚态
恢复缺陷，mode6 的无响应仅作为原版边界记录。不得把该报告扩展为实体手柄实机验收。

## 生产源码三态验证

基线取自 `dc742e8` 的真实生产源码；修改态编译本轮生产源码，回滚态在另一份
自有源码副本恢复基线并重新编译，不复制游戏。

```powershell
python build/battle-gamepad-chain/input/stage_check.py baseline
python build/battle-gamepad-chain/input/stage_check.py modified
python build/battle-gamepad-chain/input/stage_check.py rollback
```

三条命令的退出码分别为 `1/0/1`，恢复后重新出现原缺陷。检查项包含原生右键
路由、三种菜单左键路由、菜单导航、上下文 held rearm、失焦/断线/换设备取消；
相关字段在基线和回滚态为 0，修改态为 1。每阶段实际 CMake 命令、输入、逐字输出与
源码摘要保存于本地 `build/battle-gamepad-chain/input/input-stage-results.json`。
该输入层三态结果须与原生 PE 结果一起使用，不能单独证明战斗状态已改变。

## 原生方向状态

生产修改态的 D-pad/左摇杆采样进入 `A0B7E → 2F95 → 55134 → AF867/AF9C2 →
A307F → A421C/A424E`，经构造指令 `8B153` 绑定的角色虚表 `C1644` 调用
`653C6/655A1`，角色 `+104` 角度在左按后由 0 变为 `0.15000000596`，右按恢复 0，
左摇杆也产生相同真实浮点状态写入。角色状态资格 `8E0EF` 使用原始 getter。
角色朝向的矩阵提交和 ASR 外部接口为具名契约边界；此结果证明方向指令到达
原生角色朝向状态，不把该状态描述为已选中敌人或已渲染移动。

## 实际菜单状态写入

命令菜单的按钮 `105` 由真实 FDI/BGR 构造，位置 `(10,132)`，局部命中矩形
`(5,3,76,37)`。生产 D-pad 聚焦至 `(50,152)` 后，A 按下即触发原生确认，
写入 `scene+1740=5`、`+1744=0`、`+1980=5`；不人为改成释放时才确认。
在画布中心且未先选择按钮的 A 保持原生无操作，不新增隐式自动瞄准。

能力菜单从真实模式 4 进入模式 5 后，原生 `5CA57 → 5C595 → 56910`
构造可选行 `10F`；生产聚焦至 `(94,154)`，A 沿 `5EB3F → AF867 → AFE91 →
A3561 → B1B94 → A8C7E → A9025` 产生 `47(106,10F)` 并写入同一命令状态。
行内容与角色槽 1 的资源记录为明确的自有状态契约；文字 glyph 提交是渲染边界，
不是直接伪造按钮事件。B 通过真实子菜单链使模式 `5→4`。

上下文变化时，实际 C00DC 按钮 `+19C` 从按下的 1 经生产取消遍历选中，
再执行原生 `5718F` 清为 0；后续松开不产生额外确认，不撤销原生已在按下时
发生的命令。混合物理左键＋自有右键取消只清右键计数，不清真实左键按压视觉。
结果菜单 A 保留实际 `A4087` 资格判断，使 `scene+16E0=1`。

## 部署与撤回

共享运行目录的 12 份自有角色模块整批更新为同一 DLL，源摘要和清单统一校验。
模块 SHA256：`fe432fb247c77d9003db9e1e8243ad67fe0511e39ee4f8243d59e4c7f38a5391`。
本地验证目录 `build/battle-gamepad-chain` 保留 `MODIFIED_FILE.dll`、
`DIFF_FILE.patch`、`VERIFICATION.txt`、可执行 `ROLLBACK.sh` 和真实变更事务。

```powershell
python tools/update_runtime_modules.py apply --runtime runtime --module build/native/Release/workspace_profile.dll --record build/battle-gamepad-chain/NEW_RECORD
python tools/update_runtime_modules.py rollback --record build/battle-gamepad-chain/NEW_RECORD
```

现有真实事务为 `deployment-final`；默认 `ROLLBACK.sh` 只在另一份自有模块/清单
副本执行安装及精确回滚，活动模块保留修正。显式 `ROLLBACK.sh --active` 才恢复
活动运行目录的上一版模块；回滚也会恢复上一版战斗手柄缺陷，不触碰存档和设置。

小更新包 `dist/MagnaCarta-battle-controller-update-20261023.zip` 适用于上一版
连击输入边沿修正；`dist/MagnaCarta-feedback-battle-update-20261023.zip` 为从
2026-10-22 基线合并的累计反馈更新。两者均验证实际 PowerShell 更新器的
Verify/Install/CheckInstalled/Rollback，字节精确恢复，存档/设置保留。
