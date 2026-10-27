# 标题画面双行版本文字

## 目标与范围

右下角原有 `v1.04a` 改为右对齐的两行：

```text
Original: v1.04a
CN Localization & Enhancement Patch: v1.0.0
```

只替换文字内容和排版，沿用原游戏字体、暖金色、描边、透明纹理和渲染顺序。
不绘制底板、圆角、背景图片或新的窗口图层；标题图片、菜单按钮和点击区域不变。
第二行保留原版版本文字的底边位置，两行共用原版文字右边界。

## 已验证的原生路径

源锁 `MCAlpha.dll` SHA-256：
`7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e`，
PE32 / `SizeOfImage=0x10b000` / 时间戳 `0x3ed73966`。

- 标题初始化 `RVA 0xb690c` 从配置生成版本号，格式串为 `RVA 0xf1748` 的 `v%.2f%s`。
  原来的局部字符串缓冲区仅够短版本号；保持该缓冲区及 `sprintf` 原样，不能直接写入长文案。
- `RVA 0xb6fad` 的 `e8 8e e0 f8 ff` 调用 `0x45040` 创建原生文字对象，大小 `0x15c`，ID `0x155`。
  新钩子在相同字体/颜色状态下创建两份文字，第二份使用原生分配器和相同父节点，匿名 ID 为 `-1`。
  两份对象由原生父节点管理，不持有跨标题场景的对象指针。
- `RVA 0xb7046` 的 `e8 35 64 f9 ff` 调用 `0x4d480` 定位，原输入是 `canvas_width-52, canvas_height-20, z`。
  `0x1ee51` 使用当前原生字体测量原版本号；以原 `x + 原文宽度` 为右边界。
  新文字宽高来自各对象 `+0x12c/+0x130`，上行上移 `max(行高)+4`，下行沿用原 y；深度不变。
- 两份文字继续通过原生 `+0x18` 虚方法更新矩阵，不使用 `frame_overlay` 或系统绘字。
  字体资源、纹理透明度、描边与缩放继续由原有路径负责。
- 两个调用点在写入前一并校验；错误版本、改动字节与回滚目标漂移均拒绝。
  安装与拆除幂等；回滚恢复两个完整原生调用。文件回滚应在游戏退出后进行，下一次进入标题显示旧单行。

以上为源锁静态分析与自有原生调用回放结论，不是新增游戏截图或完整流程实测。
REA 关键证据：`ev_89a3766a9d0907f39c86885f1b0631b4c508e442a8d91ba02ad9ecb92e915dda`
（原生测宽）、`ev_c64d500e118d2383ad760f11f3b3485cc134e18271e8987fd0561dea904dbb22`
（定位）、`ev_52a6347c68b19260b90b2b243ad36de2cd8f86283dc0fe20a2f7f353f8239e4e`
（父节点登记）。

## 构建与发行

文案位于 `locales/zh-CN/title-version.json`，通用代码不硬编码补丁名称。
`tools/build_title_version.py` 编译选定语言目录的目录数据，拒绝控制符、超长字符串和未知字段。
本条原生 ASCII 字体路径只接收可打印 ASCII；其他语种需要独立提供相应字形和编码支持。
CMake 的 `TITLE_VERSION_CATALOG` 可选择其他目录数据。

```powershell
cmake --build build/native --config Release --target title_version_fixture workspace_profile
build/native/Release/title_version_fixture.exe --baseline
build/native/Release/title_version_fixture.exe --modified
build/native/Release/title_version_fixture.exe --rollback
python -B -X utf8 -m unittest discover -s tests -p test_title_version.py
```

自有夹具覆盖 15 组画布、45 次标题重建、原生调用参数、测宽/右对齐、颜色/深度、父节点、未知文本旁路、分配失败及字节回滚。
游戏资源存在时另核验实际 DLL 的哈希、调用点和版本格式串。

共享目录先用 `tools/update_runtime_modules.py` 更新 12 个角色模块，再用 `tools/deploy_minimap.py` 更新默认地图入口模块。
两步均保留各自事务记录；回滚顺序相反。地图图集无需重建。
编译式发行构建器现在从已验证共享清单刷新全部 13 个角色模块，而不只刷新地图模块。
任一角色漏带新文字、使用旧模块或文案不一致时停止构建；发行审计再次验证嵌入清单与所有模块。
旧的 814 项已验收游戏资源和 488 项固定输入保持原摘要，玩家设置与存档不打包。

游戏画面由测试者手动验收：从 `Game.exe` 进入标题，确认双行文字、原生描边、右下边距，无背景底板；
读取后返回标题再次检查，分别确认窗口化/无边框和 30/60 帧设置。离线测试不自动启动游戏。
