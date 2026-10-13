# 高级显示首轮实现与证据

## 第二轮玩家反馈修正（2026-10-13）

首轮4K获玩家确认；宽屏扩展区色差/UI仍停留旧边界、监控60但动作30、所有模式标题按钮在启动/退出残留。第二轮源码加入：[UI画布](WIDE_UI_CANVAS_CANDIDATE.md)、[标题状态可见性](MENU_VISIBILITY_CANDIDATE.md)、[骨骼局部姿态插值](ANIMATION_60_RESEARCH.md)。下文首轮“无插值”的描述为历史状态。第二轮仅骨骼插值，不包含世界位移/朝向/摄像机。

REA实证：UI根渲染 `0x52008b34`（ev_5b8d8ba1ab019c2b13a5c33f9ab30834896f42cf885427d66314b3cf1111479b）按全局宽高做居中变换；过渡色盒构造 `0x520579f3`（ev_692178bb533aabebe47c643f3c8e17c9532ee563c788dc46a24a032683e2084a）使用相同全局宽高。扩展全局虚拟画布可共同覆盖两侧，实体窗口宽度保留原值；色差实机消失仍待复验。完整REA源锁定记录保存在 `build/display-feedback-evidence/rea-evidence.json`。

三项补丁只在独立运行副本更新项目自有DLL/launcher；商业模块磁盘字节、资源、翻译数据、存档及原入口不修改。Asura.dll新增全文件源锁 `f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557`，配合内存入口/调用点/虚表/IAT守卫。已安装状态重复调用保持幂等；未知状态拒绝。回滚还原上一轮运行工具，候选内资源不回写。

2026-10-13：提供基准、2160行4:3、16:9宽屏4K、60Hz呈现、组合五个独立入口。汉化源数据与现用游戏副本不修改，手柄挂起。[玩家验收与恢复](ADVANCED_DISPLAY_ACCEPTANCE.md)。以下是候选实现，不是全流程游玩验收。

## 源版本与REA发现

原MCAlpha.dll：`79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f`；本轮实际汉化模块磁盘摘要：`5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。未更新AsrD3DDrv.dll：`00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29`。launcher锁定全文件，内存安装再核对映像、指令及重定位虚表槽，未知输入拒绝。

Verified（REA/Ghidra 12.1.4静态反编译）：驱动构造器将虚表设为driver+0x1a5a8；352槽（RVA0x1ab28）为0x300085cd的四double透视函数。FOV转换度到弧度，传入1/aspect；this+0x58=0x1701时更新投影矩阵并提交D3D。5槽（RVA0x1a5bc）为UpdateFrame函数RVA0x3262。完整源绑定证据留在build/advanced-display-evidence/paused-rea-evidence.json，不提交完整商业模块。

High-confidence deduction（同SHA的PE映射/Capstone指令与虚表对应）：MCAlpha+0x1d4f1调用352槽，四double来自摄像机对象；前面将宽高比存入camera+0x18，RVA0x1d4b5原6字节为`dd5a188b45fc`（fstp double[edx+18];mov eax,[ebp-4]）。该字段与投影的值流建立，但全场景裁剪消费者与UI比例没有完成运行验证。

## 2160行与宽屏

4K模式只改变DDrawCompat渲染目标盒为3840x2160。保持4:3时预测2880x2160；宽屏模式配置16:9并启用源绑定的摄像机/投影适配，目标预测3840x2160。均不修改桌面显示模式。实际尺寸受GPU上限及图形配置影响，必须通过运行日志/捕获确认。

摄像机存储点的6字节内存跳转将原4:3 aspect转换为16:9，保留其他比例、通用寄存器、EFLAGS与原字段写入；驱动透视入口独立保底，只改近似4:3且矩阵mode=projection的aspect，不重复扩大已是16:9的参数。FOV、Near/Far不改，目标为保持垂直视野、扩展水平视野而非拉伸3D主体。驱动其他矩阵/正交入口保持原指针与参数。

未验证：引擎所有裁剪/遮挡、特殊镜头、菜单/HUD/字幕布局、视频宽高比和鼠标坐标。在16:9呈现下2D元素可能仍拉伸，保留该验收缺口，不宣称已解决完整宽屏UI。原始纹理和视频不会因2160行渲染变成新高精度素材。

## 60Hz呈现与逻辑计时

Verified（REA）：实际对象计时器0x5200cdc4使用timeGetTime，等待elapsed+accumulator超过interval，之后累积真实elapsed，并最多执行5次固定callback，每次扣interval。已定位注册点仍为33ms。直接33→16会提高callback频率，因此没有改这些注册值，也没有虚拟化时间。

本候选只将RVA0xce5c的等待分支`77`改为`eb`，保留后续callback比较/消耗与速度倍率。系统timeGetTime原样保留；RVA0xcecc的调试FPS倒数计算单独处理0ms为0，避免无等待时产生无穷值，并不把0ms伪造成逻辑时间，也不对多个timer强行逐一等待。驱动UpdateFrame原方法执行后通过QPC与高分辨率等待对象按约16.67ms节奏返回。没有全局timeBeginPeriod、Sleep替换或系统时钟倍率。依据[Microsoft QPC](https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancecounter)及[等待对象](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createwaitabletimerexw)。暂停/长停顿重置呈现deadline，不凭这点声称已消除游戏原有5次补偿丢弃规则。

每120个UpdateFrame调用输出`RENDER_PACING update_frame_hz`；这是该驱动方法的调用节奏，不是GPU帧率或全逻辑计数实测。夹具模拟一分钟：30Hz绘制1800次与60Hz绘制3600次时，33ms逻辑都执行1818次。实体呈现、非timer的逐绘制更新和音画仍需实测。

明确未完成：模型/摄像机运动插值，所有动画完整60FPS化。当前只能标记“60Hz呈现、原逻辑步长候选”，不能标记“全游戏真60FPS已验收”。

## 控制与验证

`--display-profile`显式选择五模式；配置SHA必须与模式完全匹配；未知driver/layer拒绝。与TextureLifetime、现代手柄实验互斥。baseline/render4k不安装透视/计时补丁，环境中的wide/render60标志显式归零。进程退出内存改动撤销，磁盘商业代码保持原字节。

`advanced_display_fixture`使用自建PE32内存映像、虚表和可执行调用桩，验证摄像机字段原版/16:9/非标准/回滚、driver投影/正交分流、返回值、等待分支、未知字节拒绝、33ms逻辑模型及真实QPC限速。没有执行商业引擎代码。Python回归覆盖五模式hash、入口守卫、PrepareOnly、失败恢复与存档保护。

交付完整副本，五个CMD仅由用户手动启动；PrepareOnly不启动游戏。启动失败自动恢复已知配置到baseline，遇到未知哈希保留现场。独立源代码回滚、候选配置回滚和原副本不变的验证见本轮VERIFICATION.txt。
