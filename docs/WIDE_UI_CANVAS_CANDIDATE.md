# 宽屏 UI 虚拟画布候选

## SetDisplayMode启动回归修正（2026-10-13）

玩家反馈宽屏/组合启动报 `DDERR_UNSUPPORTED - SetDisplayMode`。上一轮只保持CreateWindow宽度，漏掉实际图形创建入口。REA/Ghidra静态证据 `ev_459484388a111bcd0c873a3c5d49d3d439f0d923ddb9c2e4fdb7459b9e386bd0` 确认engine+0xb8df将 `engine+0xf1b40` 共用结构指针传给CreateAsura；宽度正是该结构+8，即已扩展的f1b48。800×600因而被错误传成1067×600。

在确切调用点RVA0xb95b增加第11个指令守卫。cdecl钩子给显示创建传入独立、线程生命周期持久的7 DWORD ASRCreateInfo副本，只将宽度恢复原800/640；其他六个字段原样复制，UI全局画布仍为1067/853。Asura同版本RVA0x1650复制构造器使用7次movsd，支持结构28字节解释（Capstone静态推导）。未知参数指针走原函数。补丁预检/写失败回滚数组改为按站点总数计算，覆盖全部11点。

受控回归 `wide_ui_fixture --baseline-mode-check`：width=1067,height=600,ui_width=1067,result=DDERR_UNSUPPORTED，退出1；`--mode-check`：width=800,height=600,ui_width=1067,result=SUPPORTED，退出0。使用实际x86调用点和自有CreateAsura桩，不代表真实GPU启动已通过。仍需玩家重测宽屏及组合。

2026-10-13。玩家截图确认原4:3右边界仍约束罗盘和系统菜单；宽屏扩展区存在全屏色层遗漏。该模块只在显式宽屏候选启用，基准/4K4:3/60Hz4:3保持原行为。汉化数据与游戏磁盘模块不改。

## 证据与实现

High-confidence static deduction：MCAlpha源SHA256 `5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。PE映射和Capstone指令证据保存在 `build/advanced-display-evidence/wide-ui-static.json`。

- 虚拟画布宽高为engine+f1b48/f1b4c。配置初始化/恢复写宽度在RVA983b/99de。宽屏候选仅把支持的640/800宽度改为853/1067，高度不变。实体窗口/渲染目标并非该变量的同义词。
- UI渲染RVA8b34使用宽度/高度计算中心位移和摄像机深度；宽度扩展使右锚和居中元素使用完整画布，而不是把原4:3 UI整体拉宽。
- 系统菜单初始化7fbc3使用width-197，裁剪7fd2b使用其负值；画布宽度使菜单绘制、父对象坐标及裁剪共同移动，不单独偏移文字。
- 罗盘初始化70810及目标链接更新70b79原始坐标为540/700。四个精确立即数写入点7083a/70843/70cd4/70cdd改为canvaswidth-100。平面和指针共用原坐标，旋转逻辑不改。未知宽度保持原540/700规则。
- 实体窗口构造RVA c0dd的宽度读取c15b单独保留originalwidth；实际CreateWindowEx/AdjustWindowRect参数不使用宽屏画布尺寸。配置源结构和驱动初始化输入保持原值；夹具实际执行该读取验证800/640不变。
- 鼠标轮询2dad得到原窗口虚拟坐标，2dec写入当前坐标前按canvaswidth/originalwidth映射。warp调用2ea5从EBP局部POINT取得窗口origin，2f45从中心POINT减去canvaswidth/2取得origin；两处独立stdcall thunk仅对x-origin执行逆比例，再加回origin，保留屏幕原点与BOOL返回，之后原引擎仍保存画布坐标。没有更改全局Win32 API或系统鼠标速度。

所有10个写入点使用重定位后的预期字节守卫；预检全部完成才安装。未知指令拒绝。每个写入失败（包括已写入失败站点）还原其之前字节；夹具逐站点注入失败验证。恢复返回精确原指令及原宽度；进程退出撤销内存补丁。

## 受控验证

`wide_ui_fixture`构造自有PE32映像和可执行x86桩，实际执行宽度初始化、鼠标轮询、SetCursorPos逆变换和罗盘Thunk。不是商业引擎执行。检查640→853、800→1067、不支持尺寸保持原宽度、鼠标往返一致、未知字节拒绝、禁用及恢复。

未验证：DDrawCompat对实际GetCursorPos的虚拟化、全部对话/战斗/菜单/视频布局。完整宽屏UI验收仍需实体游戏。测试至少包括两端鼠标、系统菜单每个按钮、罗盘、对话选择、状态/物品/存档页、全屏过渡色层。
