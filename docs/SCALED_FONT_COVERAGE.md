# 高分辨率文字：离线字模与切片试样

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
