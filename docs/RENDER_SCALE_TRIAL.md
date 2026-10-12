# 渲染尺寸提升首轮对照

## 已通过的前置项

2026-10-12 会话 session-20261012-135617-225，PID 65368，退出码 0。实际反馈连续 Alt+Tab 四五次正常；日志确认 AltTabFix=noactivateapp(0)、FullscreenMode=borderless、FocusGuard 安装及五次最小化抑制。无边框切换完成首轮验收，不扩展为 20 次切换、多显示器、DPI 或长期运行全项通过。
已通过组合保留在 build/runtime/window-game，正常无层基线仍在 unpatched-game。下一试验独立复制至 render-game，不在可用组合上直接提高渲染尺寸。

## 首轮仅修改一个字段

render2x 配置相对于已通过 activation 只改变 `ResolutionScale = app` 为 `ResolutionScale = app(2)`。保留原比例、桌面输出尺寸、失焦处理、设备选择、驱动和原 MCSetting。不调用显示模式修改接口，不强制桌面切换为 1920×1080。
[官方 ResolutionScale 说明](https://github.com/narzoul/DDrawCompat/wiki/Configuration#resolutionscale) 表明该设置调整 Direct3D 渲染内容的分辨率；整数倍是本轮保守探针，不等于游戏引擎原生高分辨率、宽屏视野或 UI/字体独立缩放。

MCSetting 的已保存值包含 640、480；在对应 640×480 渲染目标上，2 倍预期为 1280×960。实际目标尺寸及画面仍待运行验证；窗口客户区不是渲染目标，不能只看窗口大小认定提升成功。DisplayResolution 仍为桌面分辨率，当前主显示器曾记录 2880×1800。

选择 2 倍而非直接强制 1920×1080 的原因：先验证渲染尺寸变化是否破坏场景、UI、点击、动画或性能，同时保留 4:3 几何比例。1080p 输出目标未完成。下一组再研究 1440×1080 的 4:3 目标加 16:9 输出留边；引擎原生分辨率机制继续作为独立调查，不以兼容层替代全部目标。
MCAlpha 读取 52 字节 MCSetting 的路径及 renderer 字段已确认；分辨率字段到完整渲染、投影与 UI 的数据流仍需进一步核实，因此本轮不盲改设置中的宽高字段。

## 重建、测试与恢复

```powershell
python tools/prepare_workspace.py --source build/runtime/window-game --target build/runtime/render-game --manifest build/render-scale-evidence/game-copy-manifest.json
python tools/graphics_compat.py select-profile --workspace build/runtime/render-game --driver-version unpatched --profile render2x
python tools/graphics_compat.py select-profile --workspace build/runtime/render-game --driver-version unpatched --profile activation
```

render2x SHA-256 `ddfc51a2b79757204c67e41d840cca035e0f5b1a0794108905a65f6948a2ebfc`，已加入 FocusGuard 固定配置白名单，其他未知配置仍拒绝。本地 LaunchRenderScaleTrial.cmd 显式选择 render2x 再启动；LaunchBorderlessTrial.cmd 保持已通过 activation 组合。
本轮不启动游戏。下一次手动读取同一存档，检查角色/地形、菜单、鼠标点击、字幕边界、音画、卡顿，再切出切回并正常退出。静态配置与离屏样本不作为真实渲染尺寸或画面验收。

## 窗口观察器退出竞争修复

通过会话的游戏退出码为 0，但旧观察器报告 Target identity changed，未写出 JSON。旧分支混合了映像查询失败和真实身份变化，退出竞争可触发该错误；该会话没有保存足以区分两者的 API 结果，不将具体原因标记为已确认。已将进程句柄保持到采样结束，查询退出状态后再核对映像；正常退出、活跃进程查询失败和身份变化分别记录并停止。采样前后退出不抛弃已有记录，不对身份异常的目标继续采样。
新增模拟 API 回归实际走过 observe 的采样和退出路径，验证一次采样保留、target_ended 结果、单次 OpenProcess 和句柄关闭。该样本不运行游戏，旧会话丢失的采样不重建、不伪造。

74 项单元测试通过，含 render2x 单字段往返和退出竞争；隐藏窗口样本、8 项隔离回归及未知图形层拒绝通过。新渲染组合尚未实际验收。

后续会话 session-20261012-140553-985 确认 app(2)、退出码 0，反馈为清晰度明显提升；观察器完整保存 31 个采样并正常结束。所测场景完成首轮清晰度反馈验收。2 倍副本保留，下一项为 [独立 1080 行渲染目标](RENDER_1080_TRIAL.md)，不将本次结果扩展为全部 UI、性能或 P1 通过。
