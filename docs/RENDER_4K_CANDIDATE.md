# 2160行渲染与增强变量隔离候选

## 状态与边界

2026-10-13：已验证配置字节、版本预检和独立夹具恢复。未启动游戏，未修改现用副本、桌面显示设置、汉化资源或存档。手柄本轮挂起。

本模块仅负责DDrawCompat配置，投影/摄像机与游戏计时由独立模块处理。`wide4k`与`combined`只生成集成草稿，配置工具拒绝直接安装，不能把水平拉伸当成真宽屏。`fps60`只是60FPS上限实验，不能解除游戏自身30FPS限制，也不会自动修正计时。

## 上游语义与假设

来源：[DDrawCompat官方配置说明](https://github.com/narzoul/DDrawCompat/wiki/Configuration)，2026-10-13核对，所用运行DLL仍固定为v0.7.1、SHA256 `f75f0ac48d2782f225c483dc2f1142303a513e8dd8a60793891ade89f64755ea`。

- `ResolutionScale`调整Direct3D渲染分辨率；负倍率避免正倍率向整数上取整。
- `DisplayAspectRatio=app`保持游戏比例；`16:9`只是输出比例，不修改游戏投影。
- `FpsLimiter=flipend(60)`在呈现后等待，依赖fullscreen page flipping；作用是上限，不是提高低帧率。
- 进程配置加载后仍可能被Overlay配置覆盖。预检拒绝副本内其他已知配置；系统/用户级配置与GPU能力需要运行日志核对，静态工具不写它们。

高置信预测：对于4:3游戏缓冲，`3840x2160(-1)`配合`app`比例得到2880x2160，而不是3840x2160真宽屏。实际目标尺寸、硬件路径及显存上限必须看游戏日志/捕获；低分辨率原始纹理和视频不会因此获得新细节。

## 配置矩阵

全部配置保留原有`FullscreenMode=borderless`、`LogLevel=info`、`AltTabFix=noactivateapp(0)`；不改变鼠标处理、UI、语言、存档。这里不将既有AltTab设置认定为修复。

|模式|相对基准唯一变化|用途|
|---|---|---|
|baseline|无变化|现用1080行控制组|
|render4k|ResolutionScale→3840x2160(-1)|2160行4:3渲染|
|wide4k|相对render4k：DisplayAspectRatio→16:9|投影适配后集成草稿|
|fps60|基准加FpsLimiter=flipend(60)|单独呈现上限实验|
|combined|相对wide4k再加FpsLimiter=flipend(60)|投影、计时两模块集成草稿|

配置哈希：

```text
baseline  0c49061b62b51e4e4dc91458d8c09650d3233895528aea80fafff06ff6b64ea3
render4k  ece87e97b2333081e5ef1fda202aa479c8fe14e9aac2fbae4df8adfea0519975
wide4k    558b2404afbc166d13b87dd182cfebc2cd1e0c9add5a52e82287d9b762fa5223
fps60     1a16654d038fe4ab2ba34db1e6ab5c495750a67eb9d66025ba4a236d0e58cb18
combined  6360e39cac131e79393d160ba340d23aa75278038ffe022b60173a3fbf010149
```

精确字节由源码`PROFILES`可重现；离线bundle的`manifest.json`再次记录各INI的SHA256。

## 重现与独立恢复

在项目根目录运行（输出目录必须尚不存在）：

```powershell
python tools/render_candidate.py preflight --source build/disc-gate-game
python tools/render_candidate.py generate --source build/disc-gate-game --output build/render-4k-configs
python -m unittest discover -s tests -p test_render_candidate.py -v
```

预检锁定现用无盘EXE、汉化MCAlpha、原版驱动、DDrawCompat DLL与基准配置的哈希，同时验证原始图形安装manifest。仅生成5份INI及报告，不复制完整商业资源。

应用时先通过`tools/prepare_workspace.py`建立全量独立副本（例如`build/render-4k-game`）及全文件复制证据；源与目标不得相互嵌套，不接受链接。随后：

```powershell
python tools/render_candidate.py apply --source build/disc-gate-game --workspace build/render-4k-game --profile render4k
python tools/render_candidate.py rollback --workspace build/render-4k-game
```

独立副本配置恢复后SHA256应为上列baseline值，`.render-candidate.json`消失，游戏文件/存档不变。若配置、DLL或manifest被其他操作修改，恢复停下并保留现场，不覆盖编辑。`graphics_compat.py`卸载或换配置之前必须先执行本模块rollback；该模块不修改原始图形安装manifest。

## 玩家验收（在集成入口完成后进行）

1. 先用baseline进入同一存档、同一镜头，截图并保存日志；退出游戏。
2. 用render4k重复相同位置，比较模型边缘和远景；确认日志渲染目标尺寸。通过标准：画面比例一致、人物不变胖、3D细节更清晰、UI不裁切、鼠标点击位置一致、视频与字幕正常。
3. 真宽屏单独验收左右新增场景、圆形/人物比例、HUD位置、点击与过场。左右视野增加而非只变胖才算通过；必须由投影模块提供实证。
4. 60FPS单独比较相同移动距离/耗时、战斗节奏、动画、音视频与读取；同时记录呈现和逻辑节奏。只有上限配置不算解锁成功。
5. 最后组合测试并进行多次切出/切回、存读档、重启。异常反馈包含模式、场景、日志、同机基准/候选截图与复现动作。

本工具不启动游戏，实际入口由集成模块交付；候选成功构建不是实玩验收。
