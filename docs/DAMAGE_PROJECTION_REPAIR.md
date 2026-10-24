# 战斗伤害数字投影修正

## 已验证的根因

锁定输入：MCAlpha.dll SHA-256 `7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`；AsrD3DDrv.dll SHA-256 `00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29`。

`MCAlpha` 模型屏幕位置路径 `474cf → 474ec → 47509` 依次调用驱动虚表的
`+394 RasterPos3fv`、`+1b4 GetFloatv(0xb07)`、`+1a4 GetBooleanv(0xb08)`。
当前D3D驱动 `GetFloatv RVA80a4` 仅处理 `0xba6`，`GetBooleanv RVA9b8c` 仅处理
`0xb60`；RasterPos3fv槽指向RVA1897c的ASURA基类导入跳板，基类为空实现。
两个查询对光栅位置及有效标志不写输出。原调用者因此消费未初始化的栈值，而不是获得敌方模型位置；
不同栈残留可能表现为零坐标、偏位或隐藏。该缺陷存在于原D3D驱动，不仅属于宽屏画布。

`tools/replay_damage_projection.py` 在Unicorn中执行实际PE查询指令：输入位置
`[123,456,789,12]` 和有效标志127完全不变。真实引擎坐标消费者RVA4750f把已初始化的
`[0,0]`转换成`[0,600]`，把有效的`[600,450]`转换成`[600,150]`。
这个受控栈案例证明坏查询与错误坐标链，不冒称复现玩家截图的特定栈残留。

数字创建和更新在AA044/AA2d1等路径，通过`actor+2dc`模型对象调用AC590读取`+138/+13c`屏幕位置，
随后叠加数字原生浮动偏移；修正不更改伤害、数字资源、生命周期或浮动速度。

## 修正

`src/runtime/damage_projection.cpp`仅改上述三个已核对的六字节CALL位置。
当前D3D驱动的三个虚表槽必须同时匹配已知RVA；其它驱动原样透传。
用调用时实际`driver+5c` modelview与`driver+9c` projection变换原生RasterPos3fv输入点，
按逻辑画布`f1b48/f1b4c`计算底原点光栅坐标，再保留原生Y翻转及数字浮动。
普通、宽屏640/800/853/1067画布均支持；不硬编码中文或物理4K输出尺寸。

矩阵来源由原生LoadMatrix RVA356a的实际写入地址绑定；原生RVA c765透视矩阵生成器
在离线x87回放中验证RH深度范围：near=-1映射clip z=0,w=1；far=-1000映射z约1000,w=1000。
因此裁剪使用`0 <= z <= w`，不是直接套用OpenGL的`-w <= z <= w`。
负w、越界、NaN、未知尺寸清除有效标志；未知查询继续调用原生方法。

安装前检查全部位置，任何指令不符拒绝整项；写入失败补偿已写位置，撤回恢复三处精确原字节。

## 离线验证与撤回

```powershell
$env:PYTHONPATH="$PWD/runtime/dependencies;$PWD/tools"
python tools/replay_damage_projection.py --engine runtime/data/MCAlpha.dll --driver runtime/data/Drv/AsrD3DDrv.dll --report build/damage-projection-evidence/native.json
build/native/Release/damage_projection_fixture.exe --baseline
build/native/Release/damage_projection_fixture.exe
python -m unittest discover -s tests -p test_damage_projection.py -v
```

基线退出1：`DAMAGE_POSITION mode=BASELINE x=0 y_top=600 expected=600,150 valid=1 game_started=false`。
候选退出0：`DAMAGE_POSITION mode=MODIFIED x=600 y_top=150 expected=600,150 valid=1 game_started=false`。
夹具通过56项：真实CALL位置、ABI、平移、透视除法、原生矩阵例、近远裁剪、四种画布、未知驱动、
未知查询、输入守卫、逐点写失败补偿与精确撤回。撤回后同一夹具恢复原始`0,600`输出。
Python五项回归通过，包含报告路径与硬链接源保护。未知输入由整份SHA拒绝；没有加载商业DLL或启动游戏。

撤回接口为`setDamageProjection(image, available, false)`；独立夹具执行撤回并逐字节比较三处CALL。
共享模块文件事务和单项恢复由本轮总验证记录保留；不复制完整游戏。
上述旧夹具只验证查询、投影和坐标消费者，不单独证明数字实际绘制。后续端到端离线验证见下节；
完整战斗画面、遮挡及全部敌人/效果组合仍由玩家手动验收。

## 真实绘制链补充（2026-10-23）

### 基线与结论口径

本次源基线为 `05ddd55`，其中已经包含三处投影调用修正。重新编译该基线并接入真实数字绘制链，
不把关闭修正的负对照称为“当前旧版失败”。本次增加原生回放、生产 ABI 桥和离屏 GPU 检查，
没有凭验证缺口再次改动已生效的生产投影算法，也不更新共享模块的构建时间戳。

### 原生坐标到绘制提交

- `B216C` 读取实际 CharData；`65CA6` 根据角色运行记录的身高类别生成头部本地锚点，
  `65E80` 写入模型 `+12c/+130/+134`。身高来自角色数据，不冒充网格包围盒。
- 模型真实虚表 Draw `47416` 经 ASURA 矩阵计算和驱动 Load/MultMatrix，调用三处生产查询桥，
  原生消费者写入模型 `+138/+13c`。桥不使用 `DAMAGE_PROJECTION_TEST`，执行实际
  `GetModuleHandleW` 分支，并检查 ESP、EBX、ESI、EDI 和撤回后的原始调用行为。
- `AA044/AA2D1` 从该模型位置创建、更新伤害图形；原生数字资源选择和图形 Draw
  `4C6FF → 55AA7/4E651 → 42503` 产生实际 `ASRRegRender` 参数、矩阵、XYZ 和 UV。
  回血使用独立原生构造/更新分支，不用颜色相似的伤害资源替代。
- UI 根绘制 `8B34` 使用透视相机而非正交矩阵。实际 `1D050 → 1D440` 生成的默认参数为
  垂直视角 `34.51587677001953` 度、宽高比、近面 `9`、远面 `20000`；
  800×600 UI 相机距离约 `965.68536`。把示例透视参数 `45/.75` 当作真实帧设置会制造假偏位。
- ASURA 注册队列和 D3D 驱动最终以 `FVF=0x1e2` 提交 XYZ 顶点，不是已变换的 XYZRHW。
  必须一起保留 WORLD、VIEW、PROJECTION、viewport 和原生纹理方向；只比较屏幕坐标公式不够。

### 独立像素判断

`damage_projection_gpu_fixture` 只创建自有隐藏窗口、普通协作模式和离屏 D3D7 HAL 表面，
不执行游戏入口、不加载商业 DLL、不改变桌面显示模式。
一条绘制使用真实头部锚点及原生世界矩阵，另一条使用原生数字队列产生的矩阵和顶点，
两条分别由 GPU 变换并读回像素；数字还使用实际 BGR 纹理，不用纯色矩形代替可见字形。
浮点头部位置到原生整数坐标的截断，以及物理输出放大后的光栅舍入，按显式像素容差判断。

真实 ASURA 排序/flush 后捕获驱动的 SetRenderState、SetTextureStageState、纹理句柄和提交次序，
离屏程序再应用这些状态，包括原生 `COLORARG2/ALPHAARG2=TFACTOR`，不以手工 diffuse 配置代替。
纹理上传为明确边界：自有纹理表提供 LINEAR/WRAP/no-mip 元数据，原始像素和 UV 不改；
不声称执行了商业驱动的设备/纹理初始化。离屏目标不附加场景深度缓冲，ZENABLE关闭为夹具初始条件。

已验证输入包括640×480、800×600、853×480、1067×600四种画布，
实际怪物引用的角色7/72/82分别提供本地头高40/70/60，原生伤害760/98与回血12345均经过资源选择和绘制。
800×600伤害760的独立世界头部像素为 `(572,162)`，数字原点为 `(572,163)`，
实际三字形包围盒为 `(574,165)-(587,176)`、`(588,165)-(601,176)`、`(602,165)-(615,176)`。
数字位于原生头顶锚点邻域，而不是统一左上角；一像素差来自原生坐标截断和光栅舍入。

3840×2160的原生viewport、队列排序和驱动提交另有四画布回放，不能当作4K像素读回。
本机自有离屏HAL设备在4K目标返回 `88760082`（DDERR_INVALIDOBJECT），
小目标设备改绑4K表面返回 `80070057`（E_INVALIDARG）；保留失败结果，不切换桌面模式。
因此本次GPU像素通过范围为上述四种逻辑尺寸，不声明4K像素或完整游戏画面已经验收。

角色位置、相机位置是公开的夹具输入，不是运行中游戏采样；网格本身、场景遮挡及完整战斗并未绘制。
商业 PE 仅作为校验整份摘要后的 Unicorn 指令输入；系统 GPU 只运行自有测试程序。
自有无入口 `AsrD3DDrv.dll` 仅供生产查询桥识别测试，始终隔离在 fixture 子目录，不进入玩家包。

```powershell
cmake --build build/native --config Release --target damage_projection_bridge damage_projection_gpu_fixture
python tools/replay_damage_render_chain.py --data runtime/data --bridge build/native/Release/damage-render-fixture/damage_projection_bridge.exe --report build/damage-render-chain/native-final.json
python tools/replay_damage_pixels.py build/damage-render-chain/native-final.json --gpu build/native/Release/damage-render-fixture/damage_projection_gpu_fixture.exe --output build/damage-render-chain/pixels-final
```

报告保存源摘要、实际提交参数、原生资源选择、像素包围盒、退出状态及未覆盖边界；
回放输出必须位于资源目录之外。重新运行时使用新的报告路径，保留既有基线与撤回证据。

## 技能期间隐藏模型的独立缺口（2026-10-24）

### 已验证

此前“未发现新缺陷”只适用于正常模型 Draw 的六组夹具，不涵盖本节的新输入。
原生 `38A2F` 检查模型 `+114/+118`，`47416` 在隐藏时直接返回，三处查询修正没有执行机会。
`AC590` 却无条件返回 `+138/+13c` 的旧缓存；普通伤害、回血及其它弹字的九个调用位置共用它。
以构造态零缓存、隐藏标志和数值1706运行原生构造/数字资源/绘制链，数字确实从 `(0,0)` 创建，
而同一模型的可见头部投影为 `(572,163)`。已有非零缓存也会留下过期位置。

新增修正保留原三处驱动查询桥，同时将九个弹字读取 CALL 改到即时投影桥：
`AA0BA/AA398/AA629/AA916/AAB88/AB128/AB453/AB6E1/ABA34`。
按模型头部 `+12c`、本体 `+b4`、当前及父级 `+4c`、当前场景相机 `f2290 → +80`、
相机 `+4` 指向的投影参数（垂直视角/近远面），计算新位置。只在已识别的D3D驱动启用，
其它驱动保留原缓存读取。此处不读取已经被UI覆盖的当前驱动矩阵，不强制显示隐藏模型。
父链最多64级并拒绝环；无效投影输出原生隐藏标记 `(-1,-1)`，不钳位到左上角。
有效结果同时更新原缓存。伤害数值、浮动曲线、数字资源和技能时序保持原生行为。

十二处指令整批预检、写失败补偿及撤回；九个五字节CALL后的下一条指令首字节保持原样。
自有Win32夹具覆盖所有位置的未知字节、逐次写失败与精确撤回（353项），
生产ABI桥逐一验证九个弹字入口；原生链另覆盖隐藏、过期缓存、父级变换、四种画布和回血。
关闭新桥或显式撤回时，同一隐藏输入重新得到 `(0,0)`。

```powershell
cmake --build build/native --config Release --target damage_projection_fixture damage_projection_bridge workspace_profile
$env:PYTHONPATH="$PWD/runtime/dependencies;$PWD/tools"
python -m unittest discover -s tests -p 'test_damage*.py' -v
python tools/replay_damage_render_chain.py --data runtime/data --bridge build/native/Release/damage-render-fixture/damage_projection_bridge.exe --report build/damage-skill-evidence/native.json
python tools/replay_damage_pixels.py build/damage-skill-evidence/native.json --gpu build/native/Release/damage-render-fixture/damage_projection_gpu_fixture.exe --case-index 7 --case-index 8 --output build/damage-skill-evidence/pixels
```

### 尚待游戏画面确认

截图证实1706在左上角，但没有提供技能名或运行状态采样；截图中具体技能是否触发上述隐藏分支，
仍属于高置信推断，而非已采样事实。本次原生回放中的隐藏/父级/位置是显式输入，不是完整技能脚本。
全部技能、特殊挂接模型、相机切换时序和实景遮挡继续由测试者手动验收。
不把离线资源链或离屏GPU检查称作完整战斗验收。

### 交付与恢复

共享运行目录只更新十二个自有模块及其摘要清单，原引擎、游戏资源、存档及个人设置不变。
`tools/update_runtime_modules.py` 的事务记录保留原模块；单项内存补丁也支持精确撤回。
独立最小模块目录执行实际模块更新/撤回后逐项恢复原摘要，共享运行目录保持候选状态。
原生产源另在独立文件副本上恢复、重编译ABI桥；同一1706隐藏回放恢复左上角失败，
与新源通过形成基线、修改、撤回闭环。

完整平铺测试包为 `dist/MagnaCarta-clean-game-skill-damage-fix-20261024.zip`，
沿用当前统一包全部汉化资源、卡墙/声音候选与稳定对照入口；无需历史小更新。
包内 `Play.cmd` 和 `Configure.cmd` 均走新模块，回滚仍用 `Restore-Original.cmd`。
此包仅表示候选集合已更新，不表示截图中的完整技能已完成游戏画面验收。

```powershell
python tools/update_runtime_modules.py apply --runtime runtime --module build/native/Release/workspace_profile.dll --record build/damage-skill-evidence/runtime-transaction
python tools/build_clean_overlay.py --previous dist/MagnaCarta-unified-test-hud-fix-20261023.zip --previous-sha256 e75802844d12b01368a63383c4174baec67652c08431ab134791dcdf8bbc966a --runtime runtime --output dist/MagnaCarta-clean-game-skill-damage-fix-20261024.zip --test-candidates
# 共享模块撤回（退出游戏后，与后续更新互斥）：
python tools/update_runtime_modules.py rollback --record build/damage-skill-evidence/runtime-transaction
```
