# 1080 行渲染目标对照

## 前置验收

会话 session-20261012-140553-985，PID 18632，退出码 0。反馈为画面明显更清晰，日志确认 ResolutionScale=app(2)、激活处理和 FocusGuard。观察器保存 31 个采样并正常记录 target_ended，旧记录丢失问题未再发生于本次会话。
当前 2 倍组合保留在 render-game，下一组独立复制到 render1080-game。此反馈只确认所测场景清晰度改善，不证明全部 UI、场景、性能或 P1 验收通过。

## 单变量与缩放依据

新组仅将 ResolutionScale 从 app(2) 改为 `1920x1080(-1)`。原始游戏设置、显示比例、桌面输出、驱动、激活处理和 FocusGuard 不变，不设置 DisplayResolution，不调用系统显示模式切换。
已核对 narzoul/DDrawCompat 固定 commit `2c9a07fdf9308e2b0b117886a7e363b149ee1bc7` 的 [Adapter.cpp](https://github.com/narzoul/DDrawCompat/blob/2c9a07fdf9308e2b0b117886a7e363b149ee1bc7/DDrawCompat/D3dDdi/Adapter.cpp) 中 getScaleFactor/getScaledSize：目标先按显示比例收敛，负参数保留非整数倍率，正参数向上取整，最后受 GPU 纹理尺寸上限约束。
[官方参数说明](https://github.com/narzoul/DDrawCompat/wiki/Configuration#resolutionscale) 与该行为一致。

以 640×480、app 原比例为计算输入，1920×1080 目标盒收敛到 1440×1080，倍率为 2.25；正参数 1 会取整至 3 倍，得到 1920×1440。因此本轮明确采用 -1，不把 4:3 场景横向拉伸成 16:9。
tools/predict_render_size.py 输出数学预测，显式标记 measured=false、gpu_limits_checked=false。预测和客户区尺寸都不能当作实际渲染目标测量。
本组是兼容层渲染目标提升，不是引擎原生 1080p、真实宽屏视野或 UI/字体独立缩放。桌面输出仍按现有显示器；1920×1080 实际输出门槛保持未完成。

## 重建与回滚

```powershell
python tools/prepare_workspace.py --source build/runtime/render-game --target build/runtime/render1080-game --manifest build/render1080-evidence/game-copy-manifest.json
python tools/graphics_compat.py select-profile --workspace build/runtime/render1080-game --driver-version unpatched --profile render1080
python tools/predict_render_size.py --base 640 480 --target 1920 1080 --multiplier -1
python tools/graphics_compat.py select-profile --workspace build/runtime/render1080-game --driver-version unpatched --profile render2x
```

render1080 固定配置 SHA-256 `0c49061b62b51e4e4dc91458d8c09650d3233895528aea80fafff06ff6b64ea3`，加入 FocusGuard 白名单。新增单元测试核对 native 白名单与 Python 配置哈希完全一致，避免两处定义漂移或误接纳未知配置。
本地 Launch1080RenderTrial.cmd 选择新副本；LaunchRenderScaleTrial.cmd 仍启动已通过的 2 倍组合。退出后也可按最后一条恢复新副本到 2 倍，不改已通过副本和无层基线。

## 验证与待测项

80 项单元测试通过，涵盖 1080 行比例计算、正/负倍率差异、错误尺寸、配置往返和 native 白名单一致性。Win32 构建、8 项隔离检查和未知图形层拒绝通过，隔离回滚恢复 2 倍配置及旧源码。
本轮没有启动游戏。下一次读取同一存档，检查较 2 倍是否进一步清晰、角色和地形是否稳定，重点检查菜单/鼠标点击、文本边缘、视频比例和卡顿；再检查 Alt+Tab 并正常退出。仍需多场景和时长验收，不以一次截图或倍率日志代替全过程。
