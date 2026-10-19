# 启动期 GUI 根节点越界修正（2026-10-19）

## 结论与验收边界

**Verified（离线）**：保留转储中的启动光标构造链把通用 GUI 根节点当作空间父节点，
在 `MCAlpha+38afb` 的继承路径读取根对象 `+f4/+100`。根节点由 `ba4c` 的
`push 54h` 分配，仅有 `0x54` 字节；虚表 `bd604`、类型字段 `+4=2`、
父节点 `+8=0`，由全局 `f220c` 引用。故障为 `1e94f` 读取 `baf024`。
原转储、调用链与内存快照限制见 [场景调查](SCENE_TRANSITION_INVESTIGATION.md)。

**Verified（离线）**：生产 C++ 编码器输出的 76 字节桥接代码与审阅的回放代码逐字节相同。
它在 Unicorn 内执行原始空间变换与向量相加指令；原基线重现精确故障，修正后保留
本地位置 `[10,20,30]`、缩放 `[2,3,4]`，恢复原 6 字节后再次重现相同故障。
普通空间父节点仍继承至 `[110,220,330]`、`[6,12,20]`；空父节点不变。
两次虚拟通知使用自有 RET 边界，未模拟实际渲染或完整光标回调。

**未验证**：玩家实机标题、新游戏、读档、GUI 及后续游玩。本轮没有启动游戏，
没有执行商业 DLL 初始化，没有附加运行中游戏或进行实机验收。
**SCENE-01 场景切换崩溃仍未复现、根因未定、未修复。**

## 修正范围

`src/runtime/gui_parent_guard.cpp` 在 `38b45` 验证原字节
`83 7a 08 00 74 72`，替换为六字节 JMP/NOP。
原分支的空父节点仍跳转 `38bbd`。只有父指针同时满足全局根指针、
精确虚表、类型 2、无父节点四个条件时，也跳过空间继承，保留子节点本地变换。
其他父节点继续 `38b4b` 原继承路径；不清空父指针、不改变所属关系、不吞异常。
桥接代码保留 EAX，两个出口重放原 CMP，EDX、其他通用寄存器和栈不受桥接代码破坏。
它只读取通用根节点最前 12 字节；不再读取该类型不存在的空间字段。
它不是通用坏指针修复，也不把任意未知父节点视为无父节点。

安装要求 PE32/I386、时间戳 `3ed73966`、映像大小 `10b000`、原分支、向量函数前缀、
根节点分配尺寸及虚表首项均匹配；正常 launcher 另核对完整 MCAlpha SHA256
`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
拒绝未知版本、其他钩子和漂移。桥接区先 RW 写入再 RX，刷新指令缓存。
可重复安装，精确守卫后撤回；内存撤回要求调用者已停止目标调用，正常回滚为退出游戏后的文件事务。

## 构建、离线验证

沿用 `build/native` 的 Win32 及生成头配置：

```powershell
cmake --build build/native --config Release --target workspace_profile gui_parent_guard_fixture
$env:PYTHONPATH='runtime/dependencies;tools;tests'
python tools/verify_gui_parent_guard.py --sample runtime/data/MCAlpha.dll --fixture build/native/Release/gui_parent_guard_fixture.exe --output build/gui-parent-proof
python -m unittest test_gui_parent_integration test_gui_parent_replay test_scene_crash_evidence test_inspect_minidump
```

验证器只启动自有 `gui_parent_guard_fixture.exe`，该夹具不加载商业模块，也不初始化游戏。
夹具测试生产安装/重复安装/精确撤回/外来钩子/尺寸及版本漂移；它导出生产编码器生成的桥接代码，
回放工具逐字节核对并执行该桥接代码，而不是把另一份算法的通过当作生产修正通过。
`--mode baseline` 和 `--mode rollback` 预期退出 1，`proposal` 和默认 `verify` 预期退出 0。
离线报告固定声明 `game_started=false`、`scene_transition_verified=false`。

## 正常入口、统一包、基线与撤回

`tools/integrate_gui_parent.py` 只接收已整合楼梯修正的精确正常入口基线
`dc4568c4d5312a0b2c68211c923c53bc9d234420b5b07347ab59cf450e12cb24`。
事务新增 `modules/gui-parent-guard.dll`、更新 Start/manifest；不覆盖原 8 份角色模块、
先前的 `field-return-height.dll`、游戏资源、设置和存档。备份两份控制文件并记录前后摘要，
预检全部运行清单，失败补偿，回滚前再次验证当前状态和备份，拒绝覆盖漂移。

```powershell
python tools/integrate_gui_parent.py --runtime runtime --module build/native/Release/workspace_profile.dll --record out/gui-parent-default-integration-20261019
# 维护时完整撤回本次整合（先退出游戏）：
python tools/integrate_gui_parent.py --rollback out/gui-parent-default-integration-20261019
```

`Play.cmd` 与 Configure 原入口不变，非 baseline 配方默认启用
`MC_GUI_PARENT_GUARD=1`，楼梯标志独立控制。`Play-baseline.cmd` 保留旧模块。
`Start.ps1 -WithoutGuiParentGuard` 临时退回上一次正常楼梯模块，保留保存设置和楼梯修正；
与 `-WithoutFieldReturnHeight` 可分别或一起使用，没有新增玩家入口。
VerifyOnly 成功、失败均恢复父进程环境及显示 INI，不触发游戏启动。

重建共享目录使用 `prepare_shared_runtime.py --field-return-height BASELINE_DLL --gui-parent-guard NEW_DLL`；
统一包构建器要求两项默认整合，包元数据独立记录启动 GUI 修正，
`scene_transition_crash_fixed=false`、`in_game_verified=false`。
包的 Install/Verify/CheckInstalled/Rollback 仍使用相同命令，不增加入口。
完整资源回滚仍须原版目录，保留存档及设置；GUI 单项临时关闭用上述现有 Start 参数。
