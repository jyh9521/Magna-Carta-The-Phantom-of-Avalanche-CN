# 技术陷阱

2026-10-25：地图 `WM_PAINT` 的窗口 DC 在旧 DDrawCompat 环境可进入虚拟屏幕路径，叠加游戏本身的呈现，造成左上角残影风险。不要用叠加窗口的位置/重绘频率掩盖此问题。地图改用既有 EndScene 后、native present 前的 backbuffer 通道；固定槽位按 map → caption → notice 合成。地形缓存必须随尺寸/模式/裁剪变化失效，缓存 DIB 读写前须 GdiFlush；见 [回归与测量](MINIMAP_PRESENTATION_REPAIR.md)。

## 地图状态与场景身份（2026-10-25）

箱体仍在活动链表、object `+d4` 未禁用均不能证明尚未领取；必须读取唯一 object 记录与
原生开关。钥匙箱状态 4 是暂时缺钥匙提示，不是完成。Field 与 WRD 不一一对应，出口需
额外核对 Field 和玩家 actor `+328`；条件 304 的 `10000+n` 不是当前控制角色的通用别名。
见 [物件证据](MAP_POINTS_RESEARCH.md) 与 [出口证据](MAP_EXIT_POINTS.md)。
F9 使用来源调用点锁定的消息边沿队列；只在地图刷新线程查询按键电平会漏掉帧间短按。
地形采用保留折线的特征边，不用屋顶实心填色掩盖室内，也不声称已识别可行走楼层。

## 碰撞返回不是整次移动提交（2026-10-24）

65699还在分轴求解前后执行中心升降探测；只观察6ed4e不足以覆盖最终角色位置。
额外点查询也并非无副作用：tree+14起28字节包含最近命中和端点临时状态，须精确恢复。
源锁保护的跳板相对位移必须以实际补丁地址计算，不能以栈上临时数组地址计算；
自有RX映像应实际执行被改入口，而不只是直接调用C++ hook。
新内核真实几何中心回放不替代现场角色八点或中央建筑的首次穿入复现。

## 离线字体检查复用受保护缓存（2026-10-24）

清理历史生成副本后，字体GPU夹具曾因默认依赖build/scaled-font-evidence/cache而报缺目录。
只读检查默认改为复用受保护的runtime/fonts，仍由原生绑定摘要拒绝未知缓存；不为回归重建20MiB副本。
显式--cache仍支持独立构建输入。该检查路径修正不改生产字体或实际显示设置。

## 声道池不能只改常数或索引（2026-10-24）

探针资源+4是数据指针，不是Miles 3D句柄。后端最大16时原生软件预算仅余8。
真实Miles试验中，Miles Fast 2D Positional Audio仍报告16；驱动打开前设偏好1为64也
没有提升该3D上限（原值已经64）。DS3D软件仿真同为16，DS3D7 Pan and Volume本地报告64。
混音偏好与3D后端上限不同，不能超出后端报告强改数组。新首选成功须同步类别0和manager句柄，
失败须保留全部原生优先项。见[声音后端候选](AUDIO_PROVIDER_POLICY.md)，不覆盖黑屏/卡墙。

## 长对白不能只数label或模拟声音（2026-10-23）

完整label文本不代表像素曾完整揭示；应在删行/销毁前检查前缀。倒计时或自建playing
不证明原声、剧情等待已结束。SVD不可统一裁108：多数剧情资源为56字节头，错误裁切
后FFmpeg可能同步成功但少解首帧。详见[真实对白链路](DIALOGUE_REAL_CHAIN.md)。

## 战斗模式不能统一退化为键盘映射（2026-10-23）

场景输入分支与子 GUI 的接口不同：字段空格不等于菜单点击，Esc 不等于右键释放。
应先执行真实构造/激活和 FDI/BGR 布局，再回放生产采样、原生计数、资格检查、
命中与 listener，检查实际场景字段。把 GUI admission 强制恒真、把按钮 FDI 尺寸
当命中矩形，或者直接调用场景成功分支，都可能制造仅夹具有效的“手柄正常”。
BGR 包装的实际矩形表是 count×16 字节，不是按图片宽高猜测的矩形。
详见[战斗手柄输入链修正](BATTLE_GAMEPAD_CHAIN_REPAIR.md)。

## 固定逻辑频率不能证明输入边沿完整（2026-10-23）

33ms任务在30／60Hz各执行相同次数，只证明调度计数守恒。
`GetKeyboardState`返回线程消息队列状态；额外呈现帧仍会取出键盘消息。
一次按下和松开若都发生在相邻逻辑轮询之间，只读最终状态会漏掉真实按下沿。
必须回放主循环的消息泵位置、消息移除和原生键盘计数，不能直接以当前硬件状态替代线程状态。

原生虚表必须从构造函数写入值和槽位解释：战斗场景写入`c1960`，
`c195c`属于前一张表的末槽；`+4/+8`分别为自身／递归更新，
`+c/+10`分别为自身／递归绘制。只在夹具和实现中重复同一个错误常量会得到假阳性。
上一轮当前攻击者关闭插值的候选已撤回，不再用攻击动画降采样掩盖输入问题。

## 位置查询成功返回不等于输出已经赋值（2026-10-23）

当前D3D驱动只实现部分GetFloatv/GetBooleanv枚举；对光栅位置及有效标志不写输出。
把宽屏坐标简单缩回640并不能修复未初始化栈值。须验证具体枚举、模型视图/投影矩阵、
齐次除法及裁剪深度，保留原生Y翻转。见[D3D投影修正](DAMAGE_PROJECTION_REPAIR.md)。

伤害数字全链回放还必须使用原生 UI 根相机：`8B34` 是透视像素布局，不是 Ortho。
默认 `1D050/1D440` 的垂直视角约34.51588度，800×600时UI距离约965.68536；
把旧数学示例的45度/.75直接送进最终绘制，会人为制造二次投影偏差。
驱动 End 提交 `FVF=0x1e2` XYZ，不能把数字位置当 XYZRHW；实际提交的 VIEW 与 WORLD 分开保存。
验证数字可见性必须经过 ASR 注册、排序、flush、纹理资源和最终 DrawPrimitive，
不把直接调用队列消费者或纯色矩形当成真实字形显示。

战斗连击计数由33ms逻辑推进，额外绘制不直接增加该计数；
不能只凭60Hz反馈把所有战斗计时减半或扩大原生判定窗。

## 图片清理不能抹掉容器结构（2026-10-20）

显式旧字清理轮廓曾绕过 `erase_mode`，导致透明圆角被填平、彩色边框被擦掉。
仅保护遮罩外像素不足以发现遮罩内部选错锚点、误删底板、破坏渐变和数字图标。
必须同时检查原版完整拼图、清理语义、源保护区和可视 alpha；全色抗锯齿不能仅靠
灰白筛选清除。INFOR/MATION、QUE/STION 等不是两个独立词条。
只读 CD 图片也可能保留只读文件属性，原子替换和异常补偿必须保留并处理该属性。
全量 422 份 BGR、101 份修正及三态证据见 [图片结构修复](IMAGE_INTEGRITY_REPAIR.md)。

## Loading资源与绘制批次不能混同

截图要求的卡尔塔Loading是FDI204的三张原生图，不是另插一张占位图；
翻译分组只含后两张，不能据其尺寸重建整个界面。自绘路线已撤回。
原 `71085` 只构造/绘制，不Present；但额外调用Render/Present也不是完整原生帧的替代。
清理前独立提交候选已被玩家实测否定：黑屏后旧场景回闪，Loading仅一闪。
单纯函数排序夹具漏掉正常门控和完整UI状态；当前改为原固定更新后、绘制前启用1730，
保留原生帧全部阶段，不补画、不额外提交。Asura Render不清零CPU计数也不构成另插一帧的理由。
不能由离线回调成功推断实际像素或换区崩溃已修复。见[原生Loading](NATIVE_LOADING_PRESENTATION.md)。

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

## 虚拟光标提交不是新的物理鼠标输入

比较输入字段前后坐标时，必须确认控制器消费者写回的整数值，否则方向焦点
与连续右摇杆会被光标上一帧提交阻断。既要覆盖“光标写入→下一次实际轮询”，
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

## 生成产物清理必须保留运行清单入口（2026-10-19）

已验证：仅按 `.cmd`/`.ps1` 扩展名删除共享 data 根目录旧入口，会误删
`runtime.json.files` 引用的当前兼容入口，导致 `Start.ps1 -VerifyOnly` 因缺文件停止。
清理现排除 `manifest.data` 和 `manifest.files` 引用的根文件，测试同时覆盖当前入口保留与旧日志删除。
当前12份入口已从最新统一包载荷按清单摘要恢复，未重建或改写游戏资源。
构建研究目录还可能包含指向共享 runtime/native 的目录联接；预检必须拒绝穿越联接。
本次只解除已核对目标的旧联接本身，之后才删除构建目录。

## 高清文字纹理接入（2026-10-20）

C候选保留原槽并增加独立纹理，不将共享池整体放大16倍像素。
原D3D驱动TexImage2D的RGBA分支存在不同于子矩形上传的转换顺序；
独立纹理采用BGRA输入，并以彩色32位alpha读回检查，不能只用白字判断通道正确。
只提高字模清晰度而不处理槽UV、原测量、失败退回和回收，会留下布局或资源生命周期问题。
详见[SCALED_FONT_COVERAGE.md](SCALED_FONT_COVERAGE.md)；离屏验证不替代游戏内验收。

## 输出与内部目标门控（2026-10-20）

兼容层可以提升实际输出而保留原GetSurfaceDesc逻辑尺寸。只在自有4K渲染目标上通过，
不能证明auto高分屏下会启用高清字模。回归必须分开内部800×600和输出2880×1800，
并保留1080p/窗口化、未知快照的退回用例。只出现READY不能计作TEXTURE创建成功。

## 宽屏画布不能用于原生资源模式选择（2026-10-20）

共享f1b48不只参与布局。战斗菜单只接受640/800；扩为853/1067会在Line169断言。资源选择保留原生宽度，布局继续扩展；不能删除断言或临时改共享值。launcher正常退出码也不证明没有弹过断言。见[BATTLE_MENU_WIDTH_ASSERTION.md](BATTLE_MENU_WIDTH_ASSERTION.md)。

## 连击次数不是结算成功证据（2026-10-23）

原生连击处理器对失败输入也可能写入记录并增加次数。只检查Space已发送、
count=3或三次宽松成功声音，会漏掉精准窗错误和动作降级。必须同时重放原生
成功计数、精准标志、动作资源选择，并验证手动接管/失焦/断连的反例。
持续按住A/X还会在输入合并时覆盖辅助松键；不要用只测试辅助类的夹具掩盖该问题。
详见[辅助判定链](COMBO_ASSIST_CHAIN_REPAIR.md)。

### 原生回调后的字段指针与寄存器分配

继续游戏完整转储显示：对象有效不等于跨原生回调缓存的内部指针仍有效。
旧对白钩子检查 EDI 可读后却解引用 ESI=0；仅拆 noinline helper 又让编译器把对象
放入 ESI，可能无异常但漏掉语音完成清理。当前同时保留 volatile 栈槽和后置取址边界，
检查生成的 x86 成品，并断言真实钩子的清理日志、计时器恢复，避免假绿。
故障快照与主动破坏寄存器夹具不证明哪次原生调用最初改写寄存器；须明确区分。

### 暴走确认不能只测按键发送

暴走用1de8/1df0/1df4及39/3a/3b键，不沿用普通连招字段和精准窗。
0/2/4的候选虽发出三次Space，原生有符号计数器仅一次松键后为-1，再按变成0而非1，
GUI不会发出新按下事件。0/3/6保留两次松键采样，并在最佳含端点6以内完成。
完整原生计数器→GUI→handler→评分/后续动作的闭环才能排除这种假绿；见
[暴走辅助](RAGE_COMBO_ASSIST.md)。

## Asura 基础模型的插帧入口（2026-10-23）

只替换 MCAlpha 派生 vtable 和对应的 MakeAbsoluteMatrix IAT 不覆盖 Asura 基础 renderer 的直接 CALL。基础 action 序列是句柄，不是派生实现中的包装指针；混用会造成旁路或错误解引用。按独立来源守卫入口、调用点、资源表范围并复用相位/恢复，详见 RELEASE_CONTROLS_2026-10-23.md。

发布入口归档时，既要删除玩家载荷中的快捷方式，也要移除发布 runtime.json 中相应 files 摘要；共享目录维护脚本可能已把旧入口加入校验清单。只在 glob 复制阶段排除会从 files 集合重新带回入口，或留下指向缺失入口的摘要。真实统一包 ZIP 回读应检查载荷和 manifest 双向一致。

### 遇敌提示的呈现回归

窗口 HDC 的背景像素通过不代表实际 HUD 可用。2026-10-23 玩家反馈常驻顶部大条幅与左上角同文闪烁。新增生产消息回放，覆盖显示期限、焦点、位置与提交次数；文字改在离屏 DIB 绘制后整体提交，禁止窗口 DC 直接绘字。最终 DirectDraw 画面仍需人工验收。

### 隐藏窗口上传不等于兼容层取得位图

DDrawCompat 0.7.1 仅为已登记窗口缓存 UpdateLayeredWindow 位图，未登记的隐藏窗口会被跳过。只在隐藏时上传，随后显示并依靠内容缓存跳过后续上传，存在合成缓存缺口。应初始化后显示，再补交可见位图；回放必须模拟登记顺序，真实 API 成功不等于游戏最终合成可见。

### 平铺脚本验证遗漏原生原路径检查

纯净版覆盖格式改变脚本数据根目录并不等于原生启动器支持原安装路径。首版命中真实路径重叠检查，且旧 VerifyOnly 在该检查前返回。回归必须同时执行生产原生预检并模拟注册目录等于覆盖根目录；验证分支应与启动共用无副作用预检，显式平铺仅放行已绑定本地化版本，不能全局删除隔离检查。

## 弹字投影不能依赖模型可见绘制

技能相机回放必须初始化原生演员的有效位置和 `+108` 朝向矩阵；全零矩阵导致相机逆矩阵为NaN，
所有目标都会被裁到画外，不能把“没有绘字报错”当作通过。新增回放拒绝非有限相机，
并用原生命令重建朝向。长连击使用明确的耐久存活目标，避免用已归零HP的模型冒充持续存活敌人。
角色夹具须使用原生 `59BD2` 基类构造器；仅用 `2590` 普通对象加CHA行会遗漏 `+EC` 的真实VObject，
简单攻击可能通过，后续受击位置提交 `5A710 → 4CC88` 则会断言，不能以空对象或无条件成功掩盖。

只统计EFS800会漏掉普通攻击和部分F11：伤害还来自战斗模型kind9命中帧，经403/401进入受击链。
探索/战斗模型不是同一变体；ABI/ATT必须按ID查询，不能按物理行号取记录。
隐藏弹字对象、隐藏数字父控件，都不保证独立数字子节点停止绘制；必须检查最终逐位提交数及回切恢复。
完整依据见[完整伤害显示链](COMBAT_DAMAGE_CHAINS.md)。

三处D3D查询桥通过不代表隐藏模型也有新坐标。原生47416在+114/+118隐藏时提前返回，AC590仍读+138/+13c缓存。回归必须覆盖构造零缓存和过期非零缓存，并从数字创建一直检查到实际绘制；弹字读取必须使用当前场景相机，不能使用已切到UI的驱动矩阵。证据和边界见[DAMAGE_PROJECTION_REPAIR.md](DAMAGE_PROJECTION_REPAIR.md)。

## 原Miles离线流夹具的后端（2026-10-25）

本机默认DirectSound分支在 `_AIL_waveOutOpen` 初始化期间出现SDK内部COM Release低地址异常。
该失败发生在字幕逻辑、原引擎映射和流启动之前；延长路径字符串生命周期没有消除该失败。
原SDK偏好表位于RVA4fc28，初始化分支读取4fc64，即索引15。夹具通过正式
`AIL_set_preference(15,1)`选择WinMM，再验证静音原SVD的暂停游标、语音身份和结束清理。
只约束离线测试环境，不修改游戏音频后端或原DLL。夹具保留阶段化异常记录，
避免把音频驱动初始化失败误判成字幕状态机失败。

原生音频池夹具的数字驱动启动也使用明确的WinMM自有边界，保留原生3D提供者选择、
真实句柄分配/释放、池上限和模块字节回滚。原SDK open_digital_driver 的flags=0会重新选择
DirectSound，单独预设偏好15不足以固定该环境。
本机软件3D提供者返回4时，测试必须验证真实原生后备及8个通道，不把硬件不可用伪装成56通道成功；
软件路径可用时仍要求56通道与16次请求全部成功，自有守卫夹具另覆盖确定的可用/失败分支。
这不改变游戏候选的生产后端或原SDK，也不扩大音效修复声明。

### Curtain opacity does not imply dialogue occlusion
A fully opaque field curtain may be drawn behind the native dialogue box. Never infer that a visible dialogue needs an overlay from opacity alone. Require explicit box/root hidden state; regress all four curtain slots and visibility transitions.

## 已有文件可写不等于父目录可创建临时文件（2026-10-25）

已验证：受保护安装目录下，现有 `DDrawCompat-MagnaCarta.ini` 授予当前账户写入权限，但父目录禁止创建文件。旧显示配置事务在父目录新建 `enhancement-*.tmp`，导致 `UnauthorizedAccessException`，Game 与配置启动均在原生启动器之前退出 1。可写开发目录的预检未覆盖该条件。

正常目录继续使用同目录临时文件和原子替换。仅捕获权限拒绝时，改用 `FileMode.Open`、`ReadWrite`、`FileShare.Read` 锁定现有 INI，保存原字节，写入、刷新并校验摘要；写入失败在同一句柄补偿原字节。预检成功或失败均恢复原 INI，外部修改继续拒绝覆盖。该路径不创建新 INI，不扩大目录权限，也不修改存档或设置。

回归使用真实 Windows ACL：禁止父目录 `CreateFiles`，保留现有文件写入；旧模块失败，新模块通过预检恢复与正常配置写入。实际安装目录的 Game 隐藏预检及配置 GUI 隐藏启动链均返回 0；实际游戏画面仍由手动启动确认。

## 可变用户数据与只读安装资源分离（2026-10-25）

不能只迁移 GUI 的 JSON 而保留游戏入口读取旧文件，也不能只移动 PowerShell 日志而遗漏 EXE 包装器或原生启动器的 cache 路径守卫。当前三条路径统一到安装路径哈希对应的 LOCALAPPDATA 子目录。原生启动器允许项目专属用户 cache，但不放宽至任意外部路径；真实预检覆盖允许目录、越界路径与 traversal 拒绝。

兼容层显示 INI 是游戏侧接口，仍需原位置已有文件可写；工具 JSON 和日志迁移不等于所有商业游戏文件、存档及兼容组件均支持完全只读安装目录。

## 编译式配置器自检

离屏 Measure/Arrange 不自动触发 Window.Loaded；自检须显式覆盖该事件，避免仅预览通过而实际打开时类型转换失败。ContentRoot 是 StackPanel，不应硬转为 Grid。桌面集成测试与完整原生入口测试须串行，避免全局空闲保护造成并行测试冲突。安全软件删除临时校验程序时，应记录失败而非恢复文件或宣称误报；本轮记录见 COMPILED_DESKTOP_RELEASE.md。


## 覆盖包通过不代表包外基础库通过（2026-10-26）

已验证：覆盖包不含 Asura.dll，现场保留了不同版本，导致最新编译入口在基础输入预检退出 1。
原 CheckInstalled 只检查 overlay.files，因此漏掉 runtime.data 中的包外依赖；
现两组均校验，仍拒绝不同摘要。配置窗口展示本次日志中的具体文件与原因，
不能只以通用“入口失败”替代诊断，也不把历史 profile.log 当作本次成功证据。
详见 COMPILED_DESKTOP_RELEASE.md 的包外基础库版本记录。


## 完整覆盖必须验证实际载荷，不只验证目标摘要（2026-10-26）

旧审计将 ZIP 缺失输入回退到 source_files，因而包内缺少 Asura 等 9 项输入仍显示通过。
运行依赖闭包和源清单原生模块现必须实际入包。只修 DLL 也不证明旧安装资源版本一致：
全量只读核对另发现 297 项差异/缺失，已用绑定原版清单的兼容计划统一纳入覆盖。
源清单外的用户文件不进入恢复集合，现有汉化目标不以原版字节覆盖。

最小回滚视图使用硬链接时，不得原地写回备份字节，否则会写穿正常修改副本。
恢复须新文件原子替换；漂移与备份摘要应在任何写入前全量校验。
来源锁、原生 24 组预检和真实旧输入回放见 COMPILED_DESKTOP_RELEASE.md。


## 现有 INI 写入兜底仍需文件权限（2026-10-26）

已验证：编译式入口沿用了仅处理“父目录禁止创建临时文件”的既有写入兜底，
当显示 INI 本身拒绝写入时仍返回退出码 1。迁移用户 JSON 不能替代游戏侧 INI 写权限。
当前改为游戏根目录 settings 加按需 UAC，授权前完成门禁；不通过扩大目录 ACL 修复。
根目录 enhancements.json 不随 ZIP 分发，迁移顺序和验证层次见 COMPILED_DESKTOP_RELEASE.md。

Windows ACL 夹具恢复必须明确标记 Access 部分已修改：直接把未变更的旧 FileSecurity
传回 SetAccessControl 可能不持久化；SetSecurityDescriptorSddlForm 应明确指定 Access，
否则可能请求不必要的 SACL/SeSecurityPrivilege。生产入口不修改 ACL。

## 干净源码检出与本机验证必须分开（2026-10-26）

已验证：仅从 Git 导出的源码与公开依赖运行全套测试时，旧测试有两项隐含本机前提：
GUI 引擎检查直接打开忽略目录中的 MCAlpha.dll，音频时钟检查在确认夹具是否构建前断言模拟 DLL 存在。
输入缺失应明确跳过对应资源/原生检查，而不是把干净检出记为代码错误。
存在夹具时仍须核对模拟 DLL，存在引擎时仍执行全部版本与指令检查；全量本地验证继续覆盖这些分支。

同一源码在带有旧 build/runtime 的目录中通过，不能证明依赖已记录或新克隆可复现。
当前依赖统一入口为 tools/requirements-dev.txt；源码与当前指南检查不读取本机 runtime。
GitHub Release 的存在以远端实际对象为准，不从本地 ZIP、清单中的 released 字段或历史文案推定。
当前构建入口与外部输入清单见[构建说明](../BUILDING.md)。
