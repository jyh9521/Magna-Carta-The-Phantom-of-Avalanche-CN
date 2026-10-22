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
实际敌人头顶锚点、不同敌人体型、攻击/回血/暴击、遮挡和宽屏画面仍待玩家手动验收。
