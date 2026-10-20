# 高分辨率文字：C方案运行接入


## 2880×1800输出门控修正（2026-10-20）

玩家反馈笔记本2880×1800仍有颗粒；保留的运行日志只有SCALED_FONT_READY，
没有SCALED_FONT_TEXTURE。显示包装层日志确认为2880×1800、ResolutionScale=display(-1)。
旧实现用GetRenderTarget/GetSurfaceDesc的内部逻辑尺寸作门槛；该值不是输出尺寸的可靠替代。

**Verified缺陷**：自有D3D7夹具把内部目标设成800×600、输出快照设为2880×1800时，
旧实现退出1（expected private high slot）；修正后40个高清纹理读回通过。
**实机未验证**：旧日志没有记录内部尺寸，因此该回放不宣称已经读到玩家内部目标为800×600，
也不排除其它守卫未通过。新日志逐步区分renderer、输出门控、canvas和纹理分配。

启动器在游戏/兼容层注入前，以EnumDisplaySettingsW读取物理桌面尺寸，结合源锁显示配方、
固定渲染尺寸和窗口大小，产生MC_SCALED_FONT_OUTPUT。auto的2880×1800不再被低逻辑目标挡住；
1080p配方及1080p窗口仍走原字模。未知配方、非法尺寸拒绝；缺失快照不猜测桌面大小。
该API不参与DPI虚拟化，依据[Microsoft文档](https://learn.microsoft.com/zh-cn/windows/win32/api/winuser/nf-winuser-enumdisplaysettingsw)。
VerifyOnly也输出SCALED_FONT_OUTPUT，且不创建游戏进程。本机只读预检已返回selected=2880x1800。
快照在每次启动时重新读取；不宣称游戏运行期间插拔显示器或拖动窗口会动态刷新。

新增scaled_font_output_fixture覆盖72组配方/窗口/桌面组合；原D3D7夹具
增加--presentation，三态均使用同一800×600内部目标与2880×1800输出快照。
新SCALED_FONT_GATE记录output/logical/enabled/reason；只有SCALED_FONT_TEXTURE才证明创建了高清纹理。

共享目录仅更新scaled-font.dll、workspace_launcher.exe和runtime.json；原Start、字体缓存、
其它模块、配置和存档保留。事务工具：

```powershell
cmake --build build/native --config Release --target workspace_launcher workspace_profile scaled_font_runtime_fixture scaled_font_output_fixture
python tools/update_scaled_font_output.py --runtime runtime --native build/native/Release --record build/scaled-font-output-evidence/integration
python tools/check_scaled_font_runtime.py baseline --presentation
python tools/check_scaled_font_runtime.py modified --presentation
python tools/check_scaled_font_runtime.py rollback --presentation
python tools/update_scaled_font_output.py --rollback build/scaled-font-output-evidence/integration
```

最后一条只撤回本轮启动器/模块/清单到上一版C。完整撤回C时，先撤回输出修正，再使用上一轮
scaled-font-runtime-evidence/integration记录；摘要漂移拒绝覆盖。当前候选保留在原Play，
不自动启动游戏。仍需测试者手动确认同一段对白和SCALED_FONT_GATE/TEXTURE日志。
从干净来源重建共享目录时须使用同一轮构建的profile与launcher，不混用旧启动器。

## 当前候选：原有Play入口（2026-10-20）

C方案已接入共享运行目录的 `Play.cmd → Start.ps1 → modules/scaled-font.dll`，
不增加另一套游戏或替换截图。保留原native-loading/GUI/楼梯模块、原游戏Font、
资源、配置、存档、旧入口及最新统一测试ZIP。当前ZIP未重新打包。
**已完成离线原生/GPU读回验证；游戏画面、性能和长时间稳定性仍待手动验收。**

### Verified：原生接入与回收

源引擎与驱动摘要及六处CALL上下文见 `assets/runtime/scaled-font-contract.json`。
只改31bce文字缓存构建中的31d97（1ef9f）、3200e/321b3（27d21）、
32056/321fb（27eb7），以及322de文字回收中的3235e（27e4d）。
不修改4526e的原生文字绘制、逻辑切块/测量/渐显字段或商业模块磁盘字节。
原生1fb39、1f86f既有覆盖钩子在限定的线程局部构建范围中记录相同五遍绘制。
14/22像素逻辑字模改用56/88像素覆盖，字距、共享基线和描边沿用已批准C。
ASCII/韩文/未知字形保留原生单色形状和步进，不伪称重新栅格化。

每个原文字槽仍正常分配、上传并保留；高清词块另外持有28字节原生ABI槽视图，
owner保存原逻辑尺寸的二次幂宽高，实际GPU纹理为其4倍。归一化UV与裁剪不变。
独立纹理经原驱动Gen/Bind/TexImage2D/Parameter创建，BGRA源与32位alpha读回逐像素相等。
不放大共享纹理池，不改变图片槽。回收先解绑设备临时引用，再删除自有纹理，
把原槽交回原27e4d；未知或回收后的纹理ID不用于删除其它资源。

- 仅支持已锁定D3D7驱动；OpenGL等路径不创建高清槽。
- 已修正为启动器解析的实际输出快照宽>=2560或高>=1440才使用高清；内部逻辑目标仅记录诊断。
- 单次CPU线缓冲<=16MiB，独立GPU纹理预算64MiB、最多128槽，保留至少32个驱动空闲ID。
- 设备纹理尺寸上限和实际分配尺寸均校验；一行后续块失败会把前面块一并退回原槽视图，避免半行两种清晰度。
- SGC1从 `fonts/` 启动时读取一次；摘要通过生成头绑定模块，并由Start清单先校验。
  绘制期间不读取字体文件。源字库不写入游戏数据，也不替换Loading图片。

### 重建与离线验证

先按后文来源锁流程重建SGC缓存，全部低分辨率单元必须与当前生成头逐字节相等。
复用已有Win32构建目录和其它生成头；以下命令不启动游戏：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH="$PWD/runtime/dependencies;$PWD/tools;$PWD/tests"
python tools/integrate_scaled_font.py --cache build/scaled-font-evidence/cache --header build/scaled-font-runtime-evidence/scaled_font_binding.h
cmake -S src/runtime -B build/native -DSCALED_FONT_DATA_HEADER=ABSOLUTE_BINDING_HEADER
cmake --build build/native --config Release --target workspace_profile scaled_font_fixture scaled_font_runtime_fixture
python tools/check_scaled_font_runtime.py baseline
python tools/check_scaled_font_runtime.py modified
python tools/check_scaled_font_runtime.py rollback
python -m unittest discover -s tests
```

生成头目标必须为新文件，不覆盖既有证据。三态夹具在隐藏窗口的自有3840×2160
离屏D3D7设备上运行，读取商业驱动时不执行DLL入口或加载商业Core/Asura依赖。
只调用独立纹理函数及嵌入的D3DX转换初始化/清理；不创建游戏窗口，不切换显示模式。
24组覆盖14/22、原高/16或32填充高及1/255/256/257/512/513宽度；
40个高清纹理GPU读回与C参考完全一致，包含尾块、透明填充、彩色、混合ASCII、
原上传指针、裁剪UV及释放。另验证1080p退回和第128槽耗尽后的整行退回。
六处指令安装、拒绝未知CALL与精确撤回均在自有PE中检查。
该证据不是游戏内画面验收，也不是整段4526e或场景切换的完整执行证明。

### 事务、基线及回滚

```powershell
python tools/integrate_scaled_font.py --runtime runtime --module build/native/Release/workspace_profile.dll --cache build/scaled-font-evidence/cache --record build/scaled-font-runtime-evidence/integration
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -VerifyOnly
```

只新增一个自有DLL、两套自有覆盖缓存及OFL许可；Start与manifest备份到事务记录。
未知基线、缓存摘要/模块绑定不一致、已有候选、已改动回滚目标均拒绝覆盖。
受同一共享入口互斥锁保护。部分写入失败补偿；只复制涉及文件的隔离回滚验证，
保留真实共享目录的候选。正常入口的baseline配方不启用C；只关闭C且保留其它修正：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File runtime/Start.ps1 -WithoutScaledFont
```

上条是**手动启动命令**，开发验证只加 `-VerifyOnly`。完整撤回（先退出游戏）：

```powershell
python tools/integrate_scaled_font.py --rollback build/scaled-font-runtime-evidence/integration
```

撤回恢复本轮前的Start/manifest及native-loading路由，删除新增候选文件，不覆盖存档设置。
本地 `build/scaled-font-runtime-evidence/` 保存原始摘要、三态命令/输出/退出码、
MODIFIED_FILE.cpp、DIFF_FILE.patch、VERIFICATION.txt及ROLLBACK.sh；ROLLBACK.sh仅操作真实事务。
共享目录从头重建支持 `--scaled-font DLL --scaled-font-cache CACHE`，同时要求保留native-loading及其依赖。
统一包包含自有覆盖/OFL并明确in_game_verified=false，不把候选当作画面已验收版本。

### 手动验收

由测试者启动原 `runtime/Play.cmd`，沿用保存设置，不运行另一测试入口。
4K核对截图中的对白字形、14/22字号、长行256边界、渐显与点击补全、选择项、
彩色/数字混排、存档列表、菜单、跨场景和Alt+Tab。低分辨率核对字号/换行未改变。
保留 `runtime/cache/profile.log` 中SCALED_FONT_READY及SCALED_FONT_TEXTURE记录；
只有READY而无TEXTURE表示尚未进入支持的高分辨率文字缓存路径，不作为高清生效证明。
确认实际画面清晰度与C一致、布局不变后再记录游戏内通过。Loading闪回及场景崩溃仍单独跟踪。

## 历史：2026-10-19离线试样

以下记录仅描述接入前的原型状态，不代表当前候选尚未安装。

2026-10-19。阶段为**离线试样，不是已安装的4K文字修复**。
正常Play、原字库、存档、设置和当前Loading候选不变；没有启动游戏或另建游戏副本。
比较图由自有Win32夹具生成，不修改玩家截图，也不作为游戏内截图展示。

## Verified：现有路径与集成缺口

引擎SHA256：`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`。
`1fb39` 写单字BGRA，`1f86f` 先画四向黑边，再以 `(0,1)` 画前景；当前补绘为
1,898个既有私有码的14/22像素灰度单元。

`31bce → 1ef9f → 1f86f` 创建文字像素，按最长256像素切块；每块20字节记录
槽指针、原x/y及宽高，文字对象另存原完整尺寸和测量尺寸。
`27d21` 从列表选择能容纳请求尺寸的槽，`27eb7 → 26440` 绑定缓冲纹理ID，
经renderer虚表 `+4e4` 按槽位置上传子矩形。

只增大Chi高度或生成一张高清图片不是完整修复。槽容量、上传坐标、UV、切片、
回收和原测量必须配套。**当前未改共享纹理池或GPU上传钩子**。
图集实际容量、最大纹理尺寸、跨类型复用与生命周期仍需源锁验证；
4倍边长需要16倍覆盖像素，不能假设原槽或全部设备都可直接容纳。

## 试样实现

`build_scaled_font_coverage.py` 读取当前生成头中的私有码、Unicode对应及灰度平面。
首先用同一摘要锁定轮廓字体重建全部3,796个低分辨率单元，要求与当前运行头
逐字节一致，然后生成4倍轮廓覆盖，**不是放大旧位图**。

- 字体仍为相同Noto Sans SC来源，wght=500；来源/许可摘要见 `assets/font-sources/`。
  衍生名Locale Scaled Glyph Coverage，附来源声明与完整OFL；不提交轮廓字体。
- 14/22逻辑步进不变，物理单元分别56/88像素，不扩大UI字号或改游戏换行。
- 原统一字号乘4，每套字模只用一个共享基线，不按单字缩放。
  高分辨率hinting可能要求共享基线整体微调1个物理像素，实际值记录在manifest；
  不声称墨迹逐点位置不变。末尾保留完整逻辑空行，兼容前景y=1。

`src/runtime/scaled_font.cpp` 仅链接独立夹具，**不链接workspace_profile**。
它复用生产 `blendNativePixel` 和投影后的原逻辑裁剪，保留直通BGRA语义。
夹具逐字比较全部低分辨率白色前景像素与生产 `drawNativeCoverage`，检查步进、
越界哨兵、未知字形拒绝；高分辨率仍使用原四向黑边/前景偏移。

## 比较图与重建

`render_scaled_font_preview.py` 调用编译后的夹具，对14/22分别生成：

- A：当前字模最近邻放大，展示源像素块。
- B：同一字模双线性放大，展示只平滑、不增加字形细节的效果。
- C：相同逻辑尺寸的4倍轮廓重栅格，含新覆盖细节。

A/B是两种滤波对照，不断言当前游戏一定使用其中某一种采样设置。
例句分行只存在于locale探针，未改实际对白；C保留原描边逻辑，不是GPU验收。

使用来源锁的固定URL/摘要取得字体，保留已有runtime/build-inputs和Win32配置：

```powershell
$env:PYTHONPATH="$PWD/runtime/dependencies;$PWD/tools;$PWD/tests"
python tools/build_scaled_font_coverage.py build --font OUTLINE.ttf --source-lock assets/font-sources/noto-sans-sc.json --font-license assets/licenses/NotoSansSC-OFL.txt --native-header runtime/build-inputs/native_font_data.h --mapping-header runtime/build-inputs/system_message_rules.h --sample locales/zh-CN/probes/scaled-font-preview.json --output build/scaled-font-cache --scale 4
cmake --build build/native --config Release --target scaled_font_fixture
python tools/render_scaled_font_preview.py --cache build/scaled-font-cache --fixture build/native/Release/scaled_font_fixture.exe --font OUTLINE.ttf --output build/scaled-font-preview
python -m unittest discover -s tests -p test_scaled_font.py
```

构建须保留 `NATIVE_FONT_DATA_HEADER`，输出必须为新目录。未知字体摘要、许可漂移、
映射不一致、低分辨率基线不同或越界字形拒绝；两次构建缓存/序列要求逐字节相同。
原生夹具拒绝伪装成高清的scale1输入。SGC1见[文件格式](FILE_FORMATS.md)。

## 切片、回滚与剩余工作

原256逻辑像素切片在4倍时最多1024物理像素，尾块保留真实尺寸。
255/256/257、512/513边界分别验证，高清裁片拼回像素完全一致。
只有槽原点、块尺寸和整张图集一起等比扩大时归一化UV才相等；数学验证不表示
实际图集分配、上传、采样已经完成或通过GPU验证。

三态均使用自有代码；回滚只在**另一份自有SGC缓存副本**上测试：

```powershell
python tools/build_scaled_font_coverage.py rollback --manifest build/scaled-font-cache/manifest.json --target SEPARATE_OWNED_CACHE.sgc --height 22
```

先核对候选/基线摘要，再原子恢复scale1；未知/漂移副本拒绝覆盖。
4倍候选保留。实际游戏无需回滚，因为入口、模块、字库没有改变。
本地证据在 `build/scaled-font-evidence/`，没有重打统一玩家ZIP。

尚未完成：原生共享图集分配/上传/UV/设备上限/回收接入，以及实际对白渐显、
选择项、存档列表、各分辨率下的像素、布局和性能验收。离线试样不记为游戏修复完成。
