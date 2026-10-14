# 共享相位人物与摄像机插值候选

> 2026-10-14空间解释更正：非空父参数的登记矩阵仍是队列世界变换，相机在ASRRender消费时另乘。下文逆相机方案和旧完整副本入口是历史记录，不是当前实现/部署方法。现用唯一runtime/data及runtime/Play-motion.cmd；详见 [队列世界修正](MOTION_QUEUED_WORLD_REPAIR.md)。

2026-10-13。完整60FPS动作阶段的候选实现，实际游玩验收待执行；不以呈现帧率或自建夹具代替游戏验证。汉化数据、已验收4K标题和正常副本保持原样。

## 源绑定静态事实

- MCAlpha SHA256：`5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。
- Asura SHA256：`f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557`。
- AsrD3DDrv SHA256：`00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29`。
- MCAlpha RVA `cdc4`：逻辑调度器；`cf61`在消耗callback后读取调度信息与控制器。守卫原字节`8b55f88b45ec`，回到`cf67`继续原始记录流程。信息`+8`为间隔、`+10`为余留、`+4`为callback对象；局部`ebp-4`为真实消耗次数；`ebp-10`为本轮原时钟差。只观察控制器`engine+f2250`的33ms任务。来源：REA `ev_d7610017603ab2eb108705959301d42cebbbf3ec9c2b530ceb8faffbded109a9`。
- MCAlpha摄像机`1d810/1db27`：活动相机指针`f2290`，矩阵`camera+80`。矩阵从LookAt构造后读取，并由load/multiply路径进入MODELVIEW；不是投影矩阵。来源：`ev_506c02d6b379708a3cfd40dbd94655b683a7efd2e8d30f3307ae5a01710bc2b4`、`ev_61567de627f9e447aeccdf05d0b88ec0cd34f357efa325261a86aac254118000`、`ev_9703932f6c7173790587a94e9a7b358ac1723a588288e70b71693bab08f5734b`。
- 驱动虚表基址RVA`1a5a8`；`+290`为load、槽RVA`1a838`、函数`356a`；`+2d0`为multiply、槽`1a878`、函数`7036`。只在模式`1700`且输入指针恰为活动相机`+80`时处理。来源：load证据`ev_1b0b1513086539736458a7a9e70a08a9f790de6bf2d85ea2964f305cf7642ed8`及同摘要只读指令解码。UI、纹理与投影输入原样传递。
- Asura矩阵列主序，乘法为`left * right`。来源：`ev_b0f52023014d661bcfc86e698bba7c1df48db287fcdc0a031c81728064dd8ce5`。骨骼渲染在对象`+c`构造`modelview * local`；不能把含相机的矩阵当纯世界坐标再插值。
- Asura `ASRRegRender` RVA`5182f`逐项复制16个矩阵元素到渲染记录，而不是保留原矩阵指针；因此提交绘制后恢复对象矩阵不撤销该次已提交变换。来源：`ev_57d32aa885bdfbc76d1622b27958331a4d4cc5a72f9cb2c07039bfe8bd0740d8`。

上述证据属于静态代码和数据流观察，不是现场姿态捕获。完整证据保存在忽略的`build/motion60-complete-evidence`下。

## 实现

`render_timeline`为语言和Windows无关的数学模块。插值相位直接使用逻辑余留/33；tick只随原callback消耗推进，不使用第二个墙钟猜相位。骨骼保留原姿态恢复边界，世界位移/旋转与镜头使用同一相位。

相机按逆视图的刚体姿态插值，再求逆提交。人物矩阵先移除已平滑相机，插值纯世界变换，再合成平滑相机，避免镜头被插值两次。绘制及SEH结束路径恢复原逻辑姿态和原modelview；相机数据本身只读。战斗判定、碰撞、动作帧、脚本、音频及存档不修改。

首次、任务身份改变、超250ms间隔、5次追赶上限、跳tick、非刚体/非有限矩阵、超过256单位传送和大幅镜头切换保持当前值并重置。相机移除产生的浮点误差使用小容差，避免静止人物每个呈现帧误重置。逻辑仍约30Hz；增加最多一逻辑tick的渲染延迟。粒子、材质动画等其他30Hz系统未单独改造，不称为整个引擎全部系统60Hz。

## 构建与独立副本

```powershell
cmake --build build/advanced-display-native --config Release --target workspace_profile motion60_fixture render_timeline_fixture
build/advanced-display-native/Release/motion60_fixture.exe
build/advanced-display-native/Release/render_timeline_fixture.exe
python tools/prepare_motion_trial.py --source build/disc-gate-game --native build/advanced-display-native/Release --locale locales/zh-CN --output build/motion60-complete-game
```

输出必须全新。构建依赖沿用BUILDING.md的版本锁、字体头与消息头，不重建汉化。`MC_MOTION60_COMPLETE=1`只由独立入口启用，旧入口保留上一版姿态路径。新入口校验本地工具和资源摘要，准备模式不启动游戏。移除钩子恢复原槽和指令，关闭游戏后进程内修改全部结束。

## 玩家验收

入口目录：`build/motion60-complete-game`。

1. `Play-30fps.cmd`：同4K宽屏画质下的30Hz逻辑/呈现对照。
2. `Play-60fps-legacy.cmd`：上一版骨骼插值，世界/相机仍旧；用于隔离新变化。
3. `Play-60fps-complete.cmd`：共享相位骨骼、位移/转向、相机候选。
4. `Rollback-motion.cmd`：关闭游戏后恢复基准配置；原正常副本不改。可重新使用30FPS或旧60FPS入口关闭新模块。

同存档同站位，记录至少2秒走路、原地转身、待机和镜头跟随；逐帧应出现新增中间状态，不只是监控60。固定起终点比较耗时；攻击、战斗事件和剧情音画不得加速、重复或遗漏。检查停止、换动作、镜头硬切、暂停恢复、存读档及跨场景，不验收已搁置的Alt+Tab故障。

日志应含`MOTION60_COMPLETE_READY`、`MOTION60_CLOCK_APPLIED`、`MOTION60_CAMERA_APPLIED`、`MOTION60_WORLD_APPLIED`。没有对应命中日志不把该子路径当作已工作。原生夹具验证同源字节守卫、实际x86计时桥、相机load/multiply调用、共享中间状态、SEH恢复和精确移除；实际画面与完整游玩仍由玩家确认。
