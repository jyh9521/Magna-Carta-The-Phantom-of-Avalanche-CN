# 对话、居中、音量与存档地点修正

2026-10-13实际截图作为缺陷输入，不作为修正后验收截图。未启动游戏；原安装、存档、开发名单和SOFTMAX品牌保持原字节。

## Verified：原生字体

原MCAlpha SHA-256 `79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f`；汉化模块 `5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。14/22像素一位栅格阈值化后再放大不能恢复笔画。

`0x5201fb39`逐像素写BGRA，`0x5201f86f`绘制四向黑边后在(0,1)画前景，`0x5201f5ad`测宽。REA证据依次为`ev_1eb17b365091313f26aceb6d58e5dc14ca48bf1f0d208db79322a1b37686742e`、`ev_dd47583765cbc5ef56a41e97a434c62ce9128a348368579655870c39c900eab2`、`ev_e94c1869f443c1edce72b549bb13042750de78f61f92beb30f115dc1658fd3d1`。颜色格式见`ev_546209a71b93d630f280522772ea4fc5edda657b48d3434984b5b324064665a1`。

自有profile对同一1,898私有码使用Noto Sans SC 500灰度覆盖及直通BGRA source-over，保留14/22步进、映射、四向黑边和颜色。ASCII、韩文、未知字形走原函数；磁盘商业DLL不改。完整模块SHA、PE32/I386/SizeOfImage和三个32字节上下文均核对；仅六字节完整位置无关序言进入trampoline。所有trampoline准备后才安装，失败恢复；不热更新已有游戏。自建夹具执行自有函数，检查灰度、步进、裁剪、回退、未知上下文拒绝和原序言恢复。

## Verified：图片

首套誓言299/300/301与303/304/305的768像素存储画布实际可见640，中文中心从384改320；原文清理仍覆盖完整768。第二套保留独立布局。0191音量黑条位于y64..83、89..108、114..133；清理和新标签均放在条内，从内部黑底取样，保护圆角、滑条及MAX。底部旧ATTENTION和残影用完整橙底模板清除，不再依赖零散残字点。

## Verified：保存地点链

Field加载器`0x52065f90`从文件偏移252读18字节至FieldInfo+0x110。`0x52068bfd`传入Level+0x10cc，名称即Level+0x11dc；保存器`0x5206fdac`在版本4后写该18字节。列表`0x520844b9`、`0x520b8572`读标签并组成`       %s (%d:%d)`。恢复伪代码的CFILE指针角色有误，调用参数另经实际指令核对。

证据为`ev_6a146f8ea8b36e452fb3dcd4995b5aaf88257eaed2facdb80a34db54f58e8cd2`、`ev_9b7268ff898e57db79eaabc65e78e05dc2f27c186d1108def049db37554db3b9`、`ev_4da05a10afb9d501dd5b87bbd7170d2a69f8ed8b5088d4ccbfec3432d5f9b602`、`ev_d238c7d3e090d99fcfd28b34cb2c3eccce62d8df87e83c1e1c61e4fd97b7df53`及`ev_6e0610f57dbcf37f73ec3e43fb62438844de6945f620d69f2296d465fde23750`。

21地点名、178份Field按完整SHA和18字节槽回写，最长8字/16字节加NUL，使用既有映射。ID、脚本和未知尾部保持原样；空名及两个调试标签保留。施瓦茨总部使用槽容量允许的简写，不改组织完整术语。新游戏加载中文场景槽后，原保存器生成中文标签及校验。既有存档不编辑、不迁移人物名、不重算校验；测宽与绘制同时转换完整旧地点标签及严格时间后缀，保留空格和时间，不替换相似对白。

## 构建

```powershell
python tools/build_field_labels.py --source SOURCE --plans locales/zh-CN/field-label-plans.json --font-package FULL_FONT_PACKAGE --output NEW_FIELDS
python tools/build_font_coverage.py --font FONT --font-sha256 LOCKED_FONT_SHA --font-package FULL_FONT_PACKAGE --labels locales/zh-CN/field-label-plans.json --module LOCALIZED_MODULE --module-sha256 LOCKED_MODULE_SHA --output NEW_COVERAGE
cmake -S src/runtime -B NEW_NATIVE -A Win32 -DLOCALE_ENGINE_SHA256=LOCKED_MODULE_SHA -DSYSTEM_MESSAGE_RULES_HEADER=ABSOLUTE_SYSTEM_HEADER -DNATIVE_FONT_DATA_HEADER=ABSOLUTE_COVERAGE_HEADER
cmake --build NEW_NATIVE --config Release --target workspace_profile workspace_launcher native_font_fixture
NEW_NATIVE/Release/native_font_fixture.exe
```

单图/组图继续使用原构建器。完整包813资源；已接受的launcher、免CD EXE及图形配置不变。升级工具先核对新旧包、已有候选及新增资源，再写入；失败撤回已尝试文件。独立回滚恢复原字节/属性并保留存档。灰度字形、标签、裁剪、图片布局及源保护已离线验证；修正后真实字幕、保存/读取及其他场景仍待游戏内观察，静态预览不作为全游戏验收。

前景绘制的原生y=1偏移要求最后一个源行留空；3,796个灰度单元逐一验证该空行，避免底笔画再次被边界裁去。
