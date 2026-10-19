# 技术陷阱

## 启动GUI越界修正（2026-10-19）

启动GUI根节点仅0x54字节，不能当作含+f4/+100字段的空间节点；必须按全局指针、虚表、类型、父节点完整识别，而不是清空所有父节点或吞访问异常。生产编码器与回放桥接逐字节比较，保留普通空间继承；见 [GUI父节点守卫](GUI_PARENT_GUARD.md)。

## 楼梯回放的解锁与坐标写回须分开

2026-10-19：0757禁入事件有完整末尾8；原生指令回放原版也能将锁计数恢复0。
问题候选是202的XYZ插值Z被旧角色Z覆盖，非漏写unlock。不能把原版正常解锁的模型改称
“原版软锁复现失败测试”；也不以第三参数1少见就改成0。碰撞、对话完成与实际操作须独立验收，
不能用模拟已完成的UI桩宣称商业游戏软锁已解决。详见STAIRWELL_RETURN_HEIGHT.md。

## DLL映像不是单个VirtualQuery内存区

2026-10-19实机启动在`DIALOGUE_REVEAL_REJECTED`退出125：对话模块误用一次
VirtualQuery要求整个0x10b000映像位于同一可读区。实际加载器的头区只有0x1000，
代码、只读数据及可写数据各自分区；单块VirtualAlloc夹具因而产生假阳性。
修正只校验实际读取的DOS/NT头、三段代码及四个虚表槽，跨相邻可读区逐段查询，
继续拒绝目标范围内的NOACCESS、GUARD、仅执行页及溢出，不要求无关/丢弃节可读。
新增真实DLL的DONT_RESOLVE_DLL_REFERENCES映射检查，不执行商业入口；同时覆盖
先安装中文步长钩子的实际调用顺序。旧代码同一映射检查退出1，修正退出0。

## 提示图片增量与生成头文件摘要

已汉化图片再次应用原始资源的清理矩形会擦除相邻已译标签。提示文字微调应先按旧文案
逐字节复现当前图片，再只使用自身布局框，保留周边“注意”等标签。
Windows文本模式写出生成头文件时会将LF变成CRLF；内存ASCII摘要不等于落盘摘要。
生成器使用明确的ASCII字节写入并核对实际文件，避免构建报告与产物身份不一致。

## UI宽度与ASRCreateInfo实际共用存储

保持CreateWindow窗口尺寸并不足以隔离宽屏UI。MCAlpha的f1b40是ASRCreateInfo首地址，f1b48同时是UI宽度与该结构+8的物理显示宽度；CreateAsura接受首地址而非直接读取f1b48的指令，因此仅检索width绝对地址会漏掉消费者。完整结构指针流必须进入显示创建回归，先验证原800×600仍传给驱动，再验证UI1067画布。上一轮窗口桩测试通过而实机SetDisplayMode失败，已保留这一失败及针对性红绿检查。

## 骨骼插值夹具不要依赖Sleep命中半帧

2026-10-13：骨骼夹具使用真实QPC和Sleep(17)验证33ms区间内中间姿态，重复交付检查中出现一次退出1且输出未刷出。Sleep不保证唤醒仍处于半帧区间，此断言具有调度依赖，不能把该次失败直接当作游戏插值故障。

夹具改为仅在 `MOTION60_TEST` 下显式注入0/17/57/327ms时点，仍执行实际渲染wrapper、姿态hook、缓存、矩阵变换桩和恢复路径；连续10次通过。生产构建保留真实QPC，不提供注入时钟。真实呈现限速仍由advanced_display原生夹具使用QPC单独验证；动作实机表现另由玩家验收。夹具失败应刷出断言输出，避免ExitProcess丢失缓冲。

已记录首轮静态分析中的格式与终端陷阱；游戏启动错误详见 docs/SAMPLE_AUDIT.md。

原字体数值索引间隙不等于空字形：高尾字节候选在两套 Chi 中没有同时为空的槽，未采用“查找零位图后直接使用”的假设。非CP949私有槽候选与有效CP949区域分离，所有字形变化有显式映射和增量记录，详见 NATIVE_GLYPH_MAPPING.md。
有意义的失败记录目的、版本/哈希、方法、现象、证据等级、原因、恢复及回归检查。
重点调查编码与解码不匹配、字形映射与宽度不同步、未知字段丢失、偏移/长度误判、盘资源遗漏、兼容层叠加和隐藏依赖。
调查线索不等于已发生缺陷，未复现问题保持待确认。

## 空 FPB 不是损坏文件

183 个四字节零值文件是空表。初版调查器将其误判为截断头部；修正后 606 个样本通过检查，已增加空表回归测试。

## 最小镜像的严格解析差异

pycdlib 1.14.0 拒绝提供的最小镜像，报告双字节序字段不一致。完整镜像出现 UDF 终止记录警告但 ISO9660 命名空间可枚举。保留原件，不据此推定 Windows 挂载失败，也不自动修复镜像。

## 终端编码与资源编码分离

CP932 终端直接输出部分韩文诊断内容会触发 UnicodeEncodeError。研究报告使用 UTF-8 文件输出，控制台使用统计值；该终端错误不作为资源损坏或游戏乱码证据。

## 原生字形索引与文本框步长并非同一规则

MCAlpha 的 Font 绘制/测宽把 CA..FF 消费为双字节，文本框步长函数却只把 A4..C9 视为双字节。CA..FD 私有编码仅更换字库会在换行时被拆分，造成不完整前缀与错误测量。必须分别验证编码、测宽、换行、缓存及渐显路径；SGI 的局部标签成功不证明全文对话可用。版本、函数与证据见 NATIVE_GLYPH_MAPPING.md。

## 渲染标记通过不等于进程测试通过

DDrawCompat v0.7.1 离屏探针在完成 120 帧后，standard 和 hal 两组均观察到 AMD 驱动退出异常。渲染 stdout 已打印 PASS，但最终进程退出码为 `0xc0000409`，因此整个测试失败。移除显式 DLL 卸载后仍有异常，不能将卸载顺序认定为已解决根因。
图形验收必须保存最终退出码，重复运行并核对退出稳定性；非零退出覆盖任何中间 PASS 标记。游戏读档的 `0xc000041d` 单独记录，不能用不同探针异常解释游戏根因。

## InstallShield CAB 不按 Microsoft CAB 处理

CD1 安装资源使用 DATA1.CAB、DATA2.HDR、DATA3.CAB。NanaZip 7.0 对 DATA1.CAB 报告不能作为 Cab archive 打开，不据此认定原镜像损坏。上游 Drv_unpatched 可作为固定来源候选，但在安装包驱动提取完成前，不宣称与原版镜像字节一致。


## 全文候选不能绕过覆盖门禁

局部FPB重建、字形覆盖和逆编码一致仅证明该批资源结构，不证明全文完成或实际场景换行。14/22像素原生字库静态预览仍采用原引擎按字宽换行策略，未增加中文行首禁则；标点落行首需要最终布局校对。图片标签、片尾烧录文字、系统Unicode/ANSI消息和动态字库属于不同显示域，不得仅替换字体后宣称全部中文化。固定槽空间之外还须检查sprintf局部缓冲区，避免磁盘合法却在显示阶段越界。


## 신기同形谓语与武器概念

初始名词候选清单误把0145“觉得新奇”的`신기할`纳入神器命中，翻译一致性检查因此错误要求“神器”。直接对照全部11处来源后，保留5处武器概念，排除6处普通形容词。正确修复对象是术语语义命中范围，而非把正常译文硬改成专名。源绑定排除记录和回归测试用于防止重复错误；原文变化必须重新复核。


## 不混用不同批次的私有字形映射

字库槽规划使用排序后的整份目标字符集合，新增字符可能使原字符槽位变化。仅加入新资源、继续使用旧字库，或只更新字库却保留旧编码资源，均可能导致错字。候选必须由同一语料、映射及构建清单重建全部目标资源，并通过逐条逆解码与字库摘要验证；不向已验证运行副本逐文件盲增补。


## 依赖路径与字段尾部数据

本次首次全套检查因未加载本地研究依赖路径，报告fontTools与pycdlib缺失。设置已有研究依赖的PYTHONPATH后，提交基线230项通过；该环境问题不作为资源缺陷。

字段范围不等于字段尾部可随意清零。固定名称扩长若覆盖原NUL之后的非零未知数据，构建器拒绝；增加独立回归。固定资源容量、格式化栈缓冲与UI像素宽度分别检查，不因结构catalog缺译为0就关闭媒体和系统显示域的缺口。

## 图片遮罩与字幕排版陷阱

单图的宽泛转录框不是可直接擦除的遮罩。中性灰笔画筛选留下彩色抗锯齿残字，遮罩过短会留下韩文末笔；门禁保护遮罩外像素也不能证明框内视觉质量。每轮须检查原图和最终预览。跨页说明与标题重叠曾被实际拒绝。视频双行字幕不能只验证首行y坐标；逐行排版并检测总高度和水平宽度后再完整解码。详情见MEDIA_LOCALIZATION.md。

实际截图中的旧字描边残痕已按完整清理轮廓修正；202份图像复核、985→0像素对照、源保护和独立回滚见[IMAGE_RESIDUE_FIX.md](IMAGE_RESIDUE_FIX.md)。不将静态清理通过称作完整游戏内验收。

## 新加入资源的只读属性

0359此前不在汉化清单，独立副本保留了原来源的只读属性。标题扩展首次写入在该文件失败；已逐项核对只可能为旧/新已知摘要，恢复全部203资源后重新升级。升级工具现在只对带候选标记的副本解除必要文件的只读位，写入失败自动恢复所有已尝试资源，独立回滚恢复原文件属性；原安装属性不修改。只读文件和中途写入失败分别有受控回归。

768像素拼图填充不等于640像素可见区域；布局中心与原文字完整擦除范围须分离。音量黑条标签擦除超过圆角条的下缘会产生黑色凸缘。单色字体阈值化后再放大不能改善丢失笔画；抗锯齿需在实际BGRA写入层保留灰度。保存地点来源在Field而非FPB，旧存档人物名与地点显示不能混为同一适配。详见[UI_READABILITY_FIX.md](UI_READABILITY_FIX.md)。

按每字墨迹居中/独立字号会造成字幕基线漂移；必须对完整字符集确定共用字号和基线。填充纹理的128像素不能代替原翻页标签91像素可见范围；原英文字旋转不应机械套用中文标题。见[UI_ALIGNMENT_FIX.md](UI_ALIGNMENT_FIX.md)。

## Alt+Tab 窗口验收与输入验收分离

2026-10-13出现多次切换后双指针和鼠标点击失效、空格有效、重启恢复的实测反馈。此前切回窗口的首轮验收不涵盖鼠标设备重新获取或游戏内点击。FOCUS_MINIMIZE_SUPPRESSED只记录最小化调用抑制，不证明输入恢复。保持该失败记录并独立追踪INPUT-01，不以隐藏系统指针代替鼠标交互回归。

## 标题容器坐标不等于装饰图块坐标

背景GUI Point偏移通过仍可显示左对齐，因为装饰节点独立加载坐标。旧夹具只测容器参数，导致错误信心。必须覆盖最终装饰向量setter及BGR变换输入，先证明旧源码同一回放失败；详见WIDE_TITLE_LAYOUT.md。不得将受控回放等同最终像素验收。

## 4K文件不等于4K纹理

2048纹理进入Asura质量1路径会先重采样到256；离线4K合成、源资源尺寸和布局测试都未覆盖这一环节。标题清晰度须检查加载尺寸选择、设备实际尺寸及最终截图，不能用PNG预览冒充实机显示验收。见TITLE_BACKGROUND_4K.md。
# 标题按钮颜色：不能只验证提交参数

Verified（支持的Asura/MCAlpha版本，详见`TITLE_STYLE.md`）：BGR格式0x102的
ASRRegRender第8个整数参数不用于这条绘制路径的颜色。仅在测试桩观察该参数，
会产生“测试已变色，画面完全没变化”的假阳性。
实际生效的是队列记录复制的RGBA状态；状态必须仅在目标顶点提交时改变，
并立即精确恢复。颜色夹具应观察排队RGBA，不把未被下游使用的字段当作视觉证据。

## 近刚体容差不代表可以丢弃伸缩

`rigid()` 接受的小缩放/剪切不能直接经四元数重建为单位旋转矩阵，
否则绘制中间帧与原生端点尺寸交替。回归须覆盖所有显示相位、精确端点及
真实绘制钩子恢复，不能只检查平移位置。受控修复见 `MOTION_STRETCH_REPAIR.md`；
玩家现场是否命中仍未验证。

## 近刚体逆矩阵不能无条件用转置

近刚体容差允许的伸缩/剪切意味着3×3不再严格正交。视图→位姿→视图及
modelview→actorWorld链路必须验证往返误差和静止人物不漂移，不能只测
单位矩阵和平移。数学与相机驱动槽的旧代码失败证据见 `MOTION_INVERSE_REPAIR.md`。

## 历史缓存数量上限不是生命周期管理

不能只给过渡历史设置固定数量上限却永不回收旧阶段条目，否则新角色在后续
区域悄悄失去回放保护。容量回归应覆盖“旧阶段填满→新阶段进入新对象”和
“全部记录仍在当前阶段→保留正在使用的历史”两种路径。见 `MOTION_HISTORY_CAPACITY.md`。

## GUI子节点存在不等于子节点参与输入

焦点收集不能因为存在隐藏/禁用GUI装饰节点就漏掉父按钮，也不能把空listener
误当作原生输入不消费：基础分发器在资格成立后仍可能返回1。
必须分别回归非活动子节点、活动无listener子节点及可交互子节点；
源槽和资格字段证据见 `GAMEPAD_INACTIVE_CHILDREN.md`。

## 虚拟光标自己的提交不是新的物理鼠标输入

比较输入字段前后坐标时，必须确认控制器消费者写回的整数值，否则方向焦点
与连续右摇杆会被自己的上一帧提交阻断。既要覆盖“自己写入→下一次实际轮询”，
也要保留真正不同坐标的鼠标优先、持续偏转阻断及回中接管。见 `GAMEPAD_CURSOR_OWNERSHIP.md`。

## Shared launcher log reuse (2026-10-14)

Verified: StartShared reused cache/profile.log, while workspace_launcher refuses an existing log. Its verify-only branch returns before that check, so engine hash preflight did not prove launch readiness. The shared entry now removes only that single prior session log under the existing session mutex and running-game exclusion, before real launch. Verify-only preserves it. Directories and reparse points are rejected; other logs, saves and game assets are untouched. Repeated-cache tests execute the actual PowerShell preparation block without launching the game. Game startup remains manual acceptance.

## Native OS polling is not a virtual cursor write

GetCursorPos refreshes engine coordinates before the keyboard IAT hook. A virtual field write must not replace the raw physical baseline. Replays must restore OS coordinates every frame and check confirm press/release hit positions; see GAMEPAD_PHYSICAL_POLL.md.

## Resource addresses are not skeletal topology

Action and ASRBone pointer changes can describe an equivalent rooted hierarchy. Preserve one-tick display continuity only after exact logical child-index comparison and model/pose/epoch/adjacent-tick checks; retain all true incompatibility resets. See MOTION_ACTION_CONTINUITY.md.

## Animation frame identity is not a logical transition epoch

A held animation frame may have different native local poses across engine updates. Same-frame stability checks belong inside one tick; consecutive transitions must update the interpolation endpoints. See MOTION_HELD_FRAME_TRANSITION.md.

## Mouse idle and release are separate native states

MCAlpha key counter 0 is idle (+190), -1 is release (+194). Replay both independently, including held press counts. Source-shaped title-stack fixtures must restore the plain input epilogue before calling its middle-of-function entry; otherwise a fixture-only stack failure is not a game defect. See GAMEPAD_MENU_DISPATCH_REPLAY.md.

## A non-null render parent is not proof of camera-composed space

MCAlpha queues parent * local before ASRRender applies the camera. A fixture that bakes camera into that parent can validate the wrong implementation. Reproduce registration, copied queue matrix and deferred camera consumption separately. The prior inverse-camera branch polluted restored object+c and introduced camera-dependent same-tick world changes. See MOTION_QUEUED_WORLD_REPAIR.md.

## Re-anchoring every deadline accumulates waiter overshoot

Advance a fixed presentation epoch, carry QPC fractional ticks and skip missed slots. Setting each next deadline to actual wake time plus one period accumulates scheduler lateness. Keep fixed33ms game logic separate; use actual Present hook replay and distinguish synthetic lateness from real device evidence. See FRAME_PACING_DEADLINE.md.

## One camera matrix pointer can have multiple render-stage uses

Temporary object-screen projection can load the prior camera before native refresh; final scene consumption uses the refreshed camera in the same logic tick. Sampling both into one TransformTrack invents a same-tick instability and discards interpolation. Guard the source final-scene CALL and replay actual x86 caller addresses, not a fixture-only classification flag. See CAMERA_SCENE_SAMPLE_REPAIR.md.

## Release-only menu actions and controller cancellation

Do not equate disappearing synthetic pressed input with a deliberate release: native title buttons execute actions on release. Preserve raw physical mouse ownership before merging controller keys; clear only synthetic counter/visual state on device loss or replacement. A zero counter alone prevents the action but leaves the native pressed visual stuck; use the verified no-listener visual helper for supported widgets. Focus behavior is separate and unchanged. See GAMEPAD_DISCONNECT_CONFIRM.md.

### Controller cancellation must cover both mouse buttons

Canceling only synthetic left presses does not protect native right-release menu actions. B/Start disconnection can dispatch event40 even when the user did not deliberately release. Replay the original counters for both buttons and separately preserve raw physical ownership. Do not apply left-button visual cleanup to right callbacks without source evidence. See GAMEPAD_CANCEL_RELEASE.md.

## Menu wrap must respect the requested axis

A wrap score without an opposite-axis condition can convert horizontal input in a vertical menu into an unrelated row change. Restrict wrap candidates to negative directional projection; retain normal opposite-end wrapping and grid behavior. Actual old focus fixture failed check5. Shared sprite-class cursor suppression must compare the current cursor object identity, not hide every object using its vtable. See GAMEPAD_USABILITY.md.

## Virtual focus must not replay the same controller arrows natively

Moving a synthetic hit point is not input consumption. Native GUI keyboard dispatch still reads the merged arrow counters, potentially changing a different control region. Suppress only owned synthetic direction bytes/counters during that original dispatch; restore exactly on all exits. Include hold-delay and release frames, same-serial dispatch, native-control entry and physical keyboard priority in the regression seam. See GAMEPAD_DIRECTION_OWNER.md.

## Hiding a pointer needs reliable replacement focus feedback

Do not treat hidden mouse graphics as proof of usable controller selection. Without dependable selected-widget visuals, retain a native menu locator. Snapshot input scope for later draw: worldScope is restored at tick exit, so querying it during rendering misclassifies exploration.

Native marker research: Asura SHA f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557, ASRRegRender RVA51a01 retains the vertex pointer while copying16 matrix words and4 RGBA floats. A temporary stack vertex buffer or null matrix reference is not a valid production render marker. Evidence ev_8b49744e8cca26d79f20d7aabc355954d699a2d44a41eb937ee4a43451597a17. Current menu locator reuses the original draw rather than inventing an unverified queue submission.

## A menu-axis latch must not latch the old sign

A sampled input stream can jump across neutral between frames. Requiring a fully neutral sample before reversing keeps an obsolete direction active. Preserve axis hysteresis, but reverse a strong opposite component immediately; weak opposite input stops the old direction, and old-axis release permits cross-axis takeover. See GAMEPAD_STICK_REVERSAL.md.

## Menu trace phases must not overclaim confirmation

A merged mouse counter at the keyboard GUI hook precedes native mouse dispatch. Label it before_mouse/merged_input, not a completed A confirmation or saved-game transition. Successful virtual focus movement likewise proves only selected target/coordinates, not a rendered highlight. Bound repetitive event records and emit one explicit limit notice. See GAMEPAD_MENU_EVIDENCE.md.
# Cursor preparation is not sprite submission (2026-10-15)

For supported MCAlpha cursor class be374, +18/38c24 prepares position/matrices; suppressing it can leave stale transforms without suppressing sprite submission. Actual sprite drawing is +c/48774, reached by +10/38bd7 traversal. The input cursor ownership hook now targets only the actual draw slot and preserves the preparation slot. A fixture that only counts calls through +18 must not be described as rendered-pixel evidence. See GAMEPAD_CURSOR_RENDER_BOUNDARY.md and GAMEPAD_NATIVE_CURSOR_PATH.md.

## 保存的窗口标志不等于运行窗口模式

2026-10-16：锁定MCAlpha的RVA 0x99cf在加载设置后无条件写入ASRCreateInfo首字段1，忽略保存的窗口字节。仅修改52字节profile不能证明窗口化。当前配置候选改为在内存核对RVA 0x9a0e完整10字节指令后，仅切换立即数；原文件不改。原生执行桩证明0/1写入与精确恢复，实际窗口化画面与输入仍待验收，详见CONFIGURATION_MATERIAL.md。

自由视角依赖共享时钟与相机矩阵消费者。只设置MC_FREE_VIEW但关闭60帧路径时，旧安装门槛会漏装相机钩子。专用配置模块在30帧自由视角下也接入所需时钟/相机钩子，保持30帧显示限制；开关、呈现节奏与原生逻辑应分开验证。

## Mixed animated renderers

MCAlpha has separate skin (3b0c0) and rigid (3d12f) animated renderers. Interpolating only the former leaves mixed model parts a full tick apart. Do not reuse skin-only object+f0/f8 fields for the rigid layout; derive its stack-local sample from action/frame. See RIGID_MOTION_PHASE.md.

## A second renderer hook is not mixed-part world synchronization

The player still observed moving eyes after the rigid-renderer candidate. The actual log did not show that renderer hook, but showed many non-rigid model-world bypasses. A rigid-only model-world gate can mix latest native placement with delayed local pose even when both objects use the same skin renderer. Test scaled/reflected model worlds without widening camera admission; keep observed callback counts separate from unobserved eye model identity.

## 窗口客户区放大不等于完整画面缩放（2026-10-19）

窗口创建之后、渲染设备初始化之前放大客户区，会改变驱动依据GetClientRect分配的后台面。
本作仍只绘制原逻辑尺寸，后台面其余区域为黑色。单测只检查窗口尺寸、目标矩形与鼠标往返时，
此错误仍会通过。须同时约束后台面分配大小和呈现目标，且通过受控真实调用点验证。
仅直接调用返回地址适配辅助函数，既没有覆盖实际调用链，也没有覆盖渲染资源的分配阶段。
GDI PrintWindow返回成功也不保证捕获到DirectDraw画面；空白/纯白位图不计为游戏画面证据。

## Bound texture is not automatically a dangling texture

The 2026-10-19 real D3D7 probe measured AddRef from1 to2 on native binding.
Native Delete releases the application's reference; the device can legitimately retain
its own live reference until replacement. A mock `hazard=true` or assertion that a deleted
ID must leave no device binding is not proof of an access violation. Original, candidate
and exact rollback each completed200 real COM/native Bind/Delete cycles. Preserve this
negative result; do not promote optional unbinding as a proven scene-crash fix.
See SCENE_TRANSITION_INVESTIGATION.md.

## Generic node ancestry does not guarantee spatial layout

The source-locked GUI root is allocated0x54 bytes, but spatial transform38afb
reads any non-null parent's +f4/+100 fields. A retained startup exception binds
that root to the exact failing read. This is layout confusion, not evidence that
the root was released. SEH dialog snapshots capture later heap state; keep
recovered registers and MemoryInfo snapshot timing distinct. A startup cursor
construction fault and its offline replay do not prove a scene-transition crash.
See SCENE_TRANSITION_INVESTIGATION.md. Never launch a game from an offline audit.
