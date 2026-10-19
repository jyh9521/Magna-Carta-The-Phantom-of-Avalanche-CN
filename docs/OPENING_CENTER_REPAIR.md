# 开场誓言：分辨率无关的中心定位

2026-10-19，玩家报告 2880×1800（16:10）新游戏开头文字偏离屏幕中心。

## Verified：实际资源与坐标

`MCAlpha.dll` SHA256 `5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427`。
REA `ev_01113c74ba422ccb306c5b9d61fcdc52d9c7dfc8a55f1d2ffe6837c9f604609e` 的
`FUN_5204d7b9` 在 RVA `4e370` 把每个装饰节点的最终向量交给 `4d3f0`；
此前 `title_layout.cpp` 只对 209/210 标题背景居中，开场文字走原始固定坐标。

实际 `FrameData/0237.fdi` 使用 299..310，其中 299/300/301 与 303/304/305
是首套六行正文；`0236.fdi` 使用 311..316。翻译 `image-group-plans.json` 的合图
不是运行时拼图定义：尤其第二套计划包含 308..310，不能用其存储画布中点定位。

对当前已安装中文图块按 FDI 实际位置拼接，亮度大于 160 的可见正文边界：

| FDI | 正文边界（右下排他） | 中心 |
| --- | --- | --- |
| 237 | (79,147)..(559,450) | (319,298.5) |
| 236 | (155,107)..(612,351) | (383.5,229) |

复现：`python tools/audit_opening_layout.py --source runtime/data --layout 236 --layout 237`。
工具只读取原文件，报告 FDI/BGR 原始 SHA256，不生成或修改商业资源。
这些中心是本版中文图块的 source-locked 排版元数据，存放于
`locales/zh-CN/opening-layout.json`，与通用 C++ 分离。以后重排该文字或增加其他语言时，
必须重新测量。`tools/build_opening_layout.py` 检查元数据列出的全部 FDI/BGR 哈希，
按实际图块重新测量边界和中心，拒绝未知资源、缺失哈希、错误中心及版本变化；
验证全部通过才生成 `runtime/build-inputs/opening_layout_data.h`。

## 修复

仅对当前 locale 生成表中的 FDI 全部子节点加同一偏移：
`dx = currentCanvasWidth / 2 - inkCenterX`；
`dy = currentCanvasHeight / 2 - inkCenterY`。
使用引擎实际 `f1b48/f1b4c`，宽屏时优先读 `wideUiCanvasWidth()`。
不按 2880 或 16:10 写死，不改变比例、Z、淡入淡出、透明度或非开场节点。
逻辑中点经全屏拉伸或居中保持比例输出，仍对应物理屏幕中点。
通用代码通过 `OPENING_LAYOUT_DATA_HEADER` 引入 `constexpr` 表，未指定该编译参数时
使用空表，不启用任何语言的开场居中；不会默认为中文或套用另一 locale 的中心。

构建：

```powershell
python tools/build_opening_layout.py --source runtime/data --metadata locales/zh-CN/opening-layout.json --output runtime/build-inputs/opening_layout_data.h
cmake -S src/runtime -B build/native -A Win32 "-DOPENING_LAYOUT_DATA_HEADER=$((Resolve-Path runtime/build-inputs/opening_layout_data.h).Path.Replace('\','/'))"
cmake --build build/native --config Release --target workspace_profile title_layout_fixture
```

与现有字库 `NATIVE_FONT_DATA_HEADER` 等参数一起配置，不清除其他构建参数。

## 验证与验收边界

`title_layout_fixture --opening-center-check` 在原实现红例输出
`content_center=319,298.5 expected=426.5,300`（退出 1）；修正后同一调用
输出 `content_center=426.5,300 expected=426.5,300`（退出 0）。
正常夹具 1,027 项覆盖最终 x86 setter、236/237、640..1280 画布宽、480/600/720
画布高、多块连续性、五档物理输出宽（包括 2880）、其他图块不变和精确回滚。
`--opening-rollback-check` 在独立自有 PE 映像撤销钩子后恢复原 `child=0,0,7`。
这证明坐标路径而非真实游戏截图；实际新游戏首屏、过渡及笔记本全屏输出仍需玩家复验。
